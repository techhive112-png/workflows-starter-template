import { DurableObject } from "cloudflare:workers";
import {
	type AgentWorker,
	type Settings,
	DEFAULT_SETTINGS,
	cleanList,
} from "./rules";

export type TaskStatus =
	| "queued"
	| "running"
	| "awaiting_approval"
	| "approved"
	| "completed"
	| "rejected"
	| "blocked"
	| "failed"
	| "cancelled";

export const ACTIVE_STATUSES: TaskStatus[] = [
	"queued",
	"running",
	"awaiting_approval",
];

export interface Task {
	id: string;
	workerId: string;
	workerName: string;
	instruction: string;
	status: TaskStatus;
	output: string | null;
	note: string | null;
	createdAt: number;
	updatedAt: number;
}

export type AuditEntry = {
	id: number;
	at: number;
	actor: string;
	action: string;
	detail: string;
};

export interface TaskContext {
	task: Task;
	worker: AgentWorker | null;
	settings: Settings;
}

export interface CommandCenterState {
	settings: Settings;
	workers: AgentWorker[];
	tasks: Task[];
	audit: AuditEntry[];
}

export interface WorkerInput {
	name?: unknown;
	role?: unknown;
	rules?: unknown;
	enabled?: unknown;
	requireApproval?: unknown;
}

const TASK_LIMIT = 100;
const AUDIT_LIMIT = 200;
const TICKET_TTL_MS = 30_000;

/**
 * CommandCenterDO - the single source of truth for one owner.
 *
 * Holds settings (rules, kill switch), the AI workers, their tasks and an
 * audit log in SQLite. Pushes the full state to the owner's browser over a
 * hibernatable WebSocket whenever anything changes.
 */
export class CommandCenterDO extends DurableObject<Env> {
	private sql: SqlStorage;

	constructor(ctx: DurableObjectState, env: Env) {
		super(ctx, env);
		this.sql = ctx.storage.sql;

		this.sql.exec(`
			CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
			CREATE TABLE IF NOT EXISTS workers (
				id TEXT PRIMARY KEY,
				name TEXT NOT NULL,
				role TEXT NOT NULL,
				rules TEXT NOT NULL,
				enabled INTEGER NOT NULL,
				require_approval INTEGER NOT NULL,
				created_at INTEGER NOT NULL
			);
			CREATE TABLE IF NOT EXISTS tasks (
				id TEXT PRIMARY KEY,
				worker_id TEXT NOT NULL,
				worker_name TEXT NOT NULL,
				instruction TEXT NOT NULL,
				status TEXT NOT NULL,
				output TEXT,
				note TEXT,
				created_at INTEGER NOT NULL,
				updated_at INTEGER NOT NULL
			);
			CREATE TABLE IF NOT EXISTS audit (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				at INTEGER NOT NULL,
				actor TEXT NOT NULL,
				action TEXT NOT NULL,
				detail TEXT NOT NULL
			);
			CREATE TABLE IF NOT EXISTS tickets (ticket TEXT PRIMARY KEY, expires_at INTEGER NOT NULL);
		`);
	}

	// ---------------------------------------------------------------------
	// WebSocket (real-time updates for the owner's dashboard)
	// ---------------------------------------------------------------------

	async fetch(request: Request): Promise<Response> {
		if (request.headers.get("Upgrade") !== "websocket") {
			return new Response("Expected WebSocket", { status: 400 });
		}

		// The browser cannot send an Authorization header on a WebSocket, so the
		// owner first trades their token for a one-time, 30-second ticket.
		const ticket = new URL(request.url).searchParams.get("ticket") ?? "";
		if (!this.redeemTicket(ticket)) {
			return new Response("Invalid or expired ticket", { status: 401 });
		}

		const pair = new WebSocketPair();
		const [client, server] = Object.values(pair);
		this.ctx.acceptWebSocket(server);
		server.send(JSON.stringify({ type: "state", state: this.getState() }));
		return new Response(null, { status: 101, webSocket: client });
	}

	async webSocketMessage(ws: WebSocket): Promise<void> {
		ws.send(JSON.stringify({ type: "state", state: this.getState() }));
	}

	async webSocketClose(ws: WebSocket, code: number, reason: string) {
		ws.close(code, reason);
	}

	async issueTicket(): Promise<string> {
		const now = Date.now();
		this.sql.exec("DELETE FROM tickets WHERE expires_at < ?", now);
		const ticket = crypto.randomUUID();
		this.sql.exec(
			"INSERT INTO tickets (ticket, expires_at) VALUES (?, ?)",
			ticket,
			now + TICKET_TTL_MS,
		);
		return ticket;
	}

	private redeemTicket(ticket: string): boolean {
		if (!ticket) return false;
		const rows = this.sql
			.exec<{
				expires_at: number;
			}>("SELECT expires_at FROM tickets WHERE ticket = ?", ticket)
			.toArray();
		this.sql.exec("DELETE FROM tickets WHERE ticket = ?", ticket);
		return rows.length === 1 && rows[0].expires_at >= Date.now();
	}

	// ---------------------------------------------------------------------
	// Reads
	// ---------------------------------------------------------------------

	getState(): CommandCenterState {
		return {
			settings: this.getSettings(),
			workers: this.listWorkers(),
			tasks: this.sql
				.exec<TaskRow>(
					"SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?",
					TASK_LIMIT,
				)
				.toArray()
				.map(toTask),
			audit: this.sql
				.exec<AuditEntry>(
					"SELECT * FROM audit ORDER BY id DESC LIMIT ?",
					AUDIT_LIMIT,
				)
				.toArray(),
		};
	}

	getSettings(): Settings {
		const rows = this.sql
			.exec<{ key: string; value: string }>("SELECT key, value FROM settings")
			.toArray();
		const stored = Object.fromEntries(
			rows.map((r) => [r.key, JSON.parse(r.value)]),
		);
		return { ...DEFAULT_SETTINGS, ...stored };
	}

	getTaskContext(taskId: string): TaskContext | null {
		const task = this.getTask(taskId);
		if (!task) return null;
		return {
			task,
			worker: this.getWorker(task.workerId),
			settings: this.getSettings(),
		};
	}

	getTask(id: string): Task | null {
		const rows = this.sql
			.exec<TaskRow>("SELECT * FROM tasks WHERE id = ?", id)
			.toArray();
		return rows.length ? toTask(rows[0]) : null;
	}

	activeTaskIds(): string[] {
		return this.sql
			.exec<{ id: string }>(
				`SELECT id FROM tasks WHERE status IN (${ACTIVE_STATUSES.map(() => "?").join(",")})`,
				...ACTIVE_STATUSES,
			)
			.toArray()
			.map((r) => r.id);
	}

	// ---------------------------------------------------------------------
	// Writes (all are logged in the audit trail)
	// ---------------------------------------------------------------------

	updateSettings(patch: Partial<Record<keyof Settings, unknown>>): Settings {
		const next = this.getSettings();
		const changed: string[] = [];

		if (typeof patch.ownerName === "string" && patch.ownerName.trim()) {
			next.ownerName = patch.ownerName.trim().slice(0, 80);
			changed.push("owner name");
		}
		if (typeof patch.killSwitch === "boolean") {
			next.killSwitch = patch.killSwitch;
			changed.push(patch.killSwitch ? "kill switch ON" : "kill switch OFF");
		}
		if (patch.globalRules !== undefined) {
			next.globalRules = cleanList(patch.globalRules);
			changed.push("global rules");
		}
		if (patch.blockedTerms !== undefined) {
			next.blockedTerms = cleanList(patch.blockedTerms, 200);
			changed.push("blocked terms");
		}

		for (const [key, value] of Object.entries(next)) {
			this.sql.exec(
				"INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
				key,
				JSON.stringify(value),
			);
		}
		if (changed.length) this.log("owner", "settings", changed.join(", "));
		this.broadcast();
		return next;
	}

	createWorker(input: WorkerInput): AgentWorker {
		const name = typeof input.name === "string" ? input.name.trim() : "";
		if (!name) throw new Error("Worker name is required");

		const worker: AgentWorker = {
			id: crypto.randomUUID(),
			name: name.slice(0, 60),
			role:
				typeof input.role === "string" ? input.role.trim().slice(0, 2000) : "",
			rules: cleanList(input.rules),
			enabled: input.enabled !== false,
			requireApproval: input.requireApproval !== false,
			createdAt: Date.now(),
		};
		this.saveWorker(worker);
		this.log("owner", "worker created", worker.name);
		this.broadcast();
		return worker;
	}

	updateWorker(id: string, input: WorkerInput): AgentWorker {
		const worker = this.getWorker(id);
		if (!worker) throw new Error("Worker not found");

		if (typeof input.name === "string" && input.name.trim()) {
			worker.name = input.name.trim().slice(0, 60);
		}
		if (typeof input.role === "string")
			worker.role = input.role.trim().slice(0, 2000);
		if (input.rules !== undefined) worker.rules = cleanList(input.rules);
		if (typeof input.enabled === "boolean") worker.enabled = input.enabled;
		if (typeof input.requireApproval === "boolean") {
			worker.requireApproval = input.requireApproval;
		}

		this.saveWorker(worker);
		this.log("owner", "worker updated", worker.name);
		this.broadcast();
		return worker;
	}

	deleteWorker(id: string): void {
		const worker = this.getWorker(id);
		if (!worker) return;
		this.sql.exec("DELETE FROM workers WHERE id = ?", id);
		this.log("owner", "worker deleted", worker.name);
		this.broadcast();
	}

	createTask(workerId: string, instruction: string): Task {
		const worker = this.getWorker(workerId);
		if (!worker) throw new Error("Worker not found");

		const now = Date.now();
		const task: Task = {
			id: crypto.randomUUID(),
			workerId,
			workerName: worker.name,
			instruction: instruction.slice(0, 8000),
			status: "queued",
			output: null,
			note: null,
			createdAt: now,
			updatedAt: now,
		};
		this.sql.exec(
			"INSERT INTO tasks (id, worker_id, worker_name, instruction, status, output, note, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
			task.id,
			task.workerId,
			task.workerName,
			task.instruction,
			task.status,
			null,
			null,
			now,
			now,
		);
		this.log(
			"owner",
			"task assigned",
			`${worker.name}: ${preview(instruction)}`,
		);
		this.broadcast();
		return task;
	}

	/**
	 * Update a task. Safe to call more than once with the same values (the
	 * workflow may retry) - the audit log only records actual status changes.
	 */
	updateTask(
		id: string,
		patch: {
			status?: TaskStatus;
			output?: string | null;
			note?: string | null;
		},
		actor = "system",
	): Task | null {
		const task = this.getTask(id);
		if (!task) return null;

		const statusChanged = patch.status && patch.status !== task.status;
		const next: Task = {
			...task,
			...(patch.status ? { status: patch.status } : {}),
			...(patch.output !== undefined ? { output: patch.output } : {}),
			...(patch.note !== undefined ? { note: patch.note } : {}),
			updatedAt: Date.now(),
		};
		this.sql.exec(
			"UPDATE tasks SET status = ?, output = ?, note = ?, updated_at = ? WHERE id = ?",
			next.status,
			next.output,
			next.note,
			next.updatedAt,
			id,
		);
		if (statusChanged) {
			this.log(
				actor,
				`task ${next.status.replace("_", " ")}`,
				`${task.workerName}: ${preview(task.instruction)}${next.note ? ` — ${next.note}` : ""}`,
			);
		}
		this.broadcast();
		return next;
	}

	clearFinishedTasks(): void {
		this.sql.exec(
			`DELETE FROM tasks WHERE status NOT IN (${ACTIVE_STATUSES.map(() => "?").join(",")})`,
			...ACTIVE_STATUSES,
		);
		this.log("owner", "history cleared", "finished tasks removed");
		this.broadcast();
	}

	// ---------------------------------------------------------------------
	// Internals
	// ---------------------------------------------------------------------

	private listWorkers(): AgentWorker[] {
		return this.sql
			.exec<WorkerRow>("SELECT * FROM workers ORDER BY created_at ASC")
			.toArray()
			.map(toWorker);
	}

	private getWorker(id: string): AgentWorker | null {
		const rows = this.sql
			.exec<WorkerRow>("SELECT * FROM workers WHERE id = ?", id)
			.toArray();
		return rows.length ? toWorker(rows[0]) : null;
	}

	private saveWorker(w: AgentWorker): void {
		this.sql.exec(
			`INSERT INTO workers (id, name, role, rules, enabled, require_approval, created_at)
			 VALUES (?, ?, ?, ?, ?, ?, ?)
			 ON CONFLICT(id) DO UPDATE SET name = excluded.name, role = excluded.role,
			   rules = excluded.rules, enabled = excluded.enabled,
			   require_approval = excluded.require_approval`,
			w.id,
			w.name,
			w.role,
			JSON.stringify(w.rules),
			w.enabled ? 1 : 0,
			w.requireApproval ? 1 : 0,
			w.createdAt,
		);
	}

	private log(actor: string, action: string, detail: string): void {
		this.sql.exec(
			"INSERT INTO audit (at, actor, action, detail) VALUES (?, ?, ?, ?)",
			Date.now(),
			actor,
			action,
			detail,
		);
		this.sql.exec(
			"DELETE FROM audit WHERE id NOT IN (SELECT id FROM audit ORDER BY id DESC LIMIT ?)",
			AUDIT_LIMIT,
		);
	}

	private broadcast(): void {
		const json = JSON.stringify({ type: "state", state: this.getState() });
		for (const socket of this.ctx.getWebSockets()) {
			try {
				socket.send(json);
			} catch {
				// Ignore errors for disconnected sockets
			}
		}
	}
}

type WorkerRow = {
	id: string;
	name: string;
	role: string;
	rules: string;
	enabled: number;
	require_approval: number;
	created_at: number;
};

type TaskRow = {
	id: string;
	worker_id: string;
	worker_name: string;
	instruction: string;
	status: TaskStatus;
	output: string | null;
	note: string | null;
	created_at: number;
	updated_at: number;
};

function toWorker(r: WorkerRow): AgentWorker {
	return {
		id: r.id,
		name: r.name,
		role: r.role,
		rules: JSON.parse(r.rules),
		enabled: r.enabled === 1,
		requireApproval: r.require_approval === 1,
		createdAt: r.created_at,
	};
}

function toTask(r: TaskRow): Task {
	return {
		id: r.id,
		workerId: r.worker_id,
		workerName: r.worker_name,
		instruction: r.instruction,
		status: r.status,
		output: r.output,
		note: r.note,
		createdAt: r.created_at,
		updatedAt: r.updated_at,
	};
}

function preview(text: string): string {
	const oneLine = text.replace(/\s+/g, " ").trim();
	return oneLine.length > 80 ? `${oneLine.slice(0, 77)}...` : oneLine;
}
