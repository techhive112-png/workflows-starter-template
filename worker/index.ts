import { checkOwner } from "./auth";
import { OWNER_CENTER, type OwnerDecision } from "./agent-workflow";

// Export the Workflow and Durable Object classes
export { AgentTaskWorkflow } from "./agent-workflow";
export { CommandCenterDO } from "./command-center";

/**
 * Personal AI Command Center - owner-only API.
 *
 * Every /api route requires `Authorization: Bearer <OWNER_TOKEN>`.
 *
 * - GET    /api/state                 Full dashboard state
 * - POST   /api/ws-ticket             One-time ticket for the live WebSocket
 * - PUT    /api/settings              Rules, blocked terms, kill switch, owner name
 * - POST   /api/workers               Create an AI worker
 * - PUT    /api/workers/:id           Update an AI worker
 * - DELETE /api/workers/:id           Delete an AI worker
 * - POST   /api/tasks                 Give a worker a task
 * - POST   /api/tasks/:id/decision    Approve or reject a worker's result
 * - POST   /api/tasks/:id/cancel      Stop a task
 * - DELETE /api/tasks                 Clear finished tasks
 * - GET    /ws?ticket=...             Live updates
 */
export default {
	async fetch(request: Request, env: Env): Promise<Response> {
		const url = new URL(request.url);
		const center = env.COMMAND_CENTER.get(
			env.COMMAND_CENTER.idFromName(OWNER_CENTER),
		);

		// The WebSocket is authorised by a one-time ticket checked in the DO
		if (url.pathname === "/ws") {
			if (request.headers.get("Upgrade") !== "websocket") {
				return new Response("Expected Upgrade: websocket", { status: 426 });
			}
			return center.fetch(request);
		}

		if (!url.pathname.startsWith("/api/")) {
			return json({ error: "Not Found" }, 404);
		}

		const auth = checkOwner(request, env);
		if (!auth.ok) return json({ error: auth.error }, auth.status);

		const parts = url.pathname.split("/").filter(Boolean).slice(1); // drop "api"
		const [resource, id, action] = parts;
		const method = request.method;

		try {
			if (resource === "state" && method === "GET") {
				return json(await center.getState());
			}

			if (resource === "ws-ticket" && method === "POST") {
				return json({ ticket: await center.issueTicket() });
			}

			if (resource === "settings" && method === "PUT") {
				const body = await readJson(request);
				const settings = await center.updateSettings(body);
				if (body.killSwitch === true) {
					await stopActiveTasks(env, center, "Stopped by kill switch.");
				}
				return json(settings);
			}

			if (resource === "workers") {
				if (!id && method === "POST") {
					return json(await center.createWorker(await readJson(request)), 201);
				}
				if (id && method === "PUT") {
					return json(await center.updateWorker(id, await readJson(request)));
				}
				if (id && method === "DELETE") {
					await center.deleteWorker(id);
					return json({ ok: true });
				}
			}

			if (resource === "tasks") {
				if (!id && method === "POST") {
					const body = await readJson(request);
					const workerId = String(body.workerId ?? "");
					const instruction = String(body.instruction ?? "").trim();
					if (!instruction)
						return json({ error: "Instruction is required" }, 400);

					const settings = await center.getSettings();
					if (settings.killSwitch) {
						return json(
							{ error: "Kill switch is on. Turn it off to assign tasks." },
							409,
						);
					}

					const task = await center.createTask(workerId, instruction);
					await env.AGENT_TASK.create({
						id: task.id,
						params: { taskId: task.id },
					});
					return json(task, 201);
				}

				if (!id && method === "DELETE") {
					await center.clearFinishedTasks();
					return json({ ok: true });
				}

				if (id && action === "decision" && method === "POST") {
					const task = await center.getTask(id);
					if (!task) return json({ error: "Task not found" }, 404);
					if (task.status !== "awaiting_approval") {
						return json({ error: "Task is not waiting for your review" }, 409);
					}
					const body = await readJson(request);
					const decision: OwnerDecision = {
						approved: body.approved === true,
						note: typeof body.note === "string" ? body.note : undefined,
					};
					const instance = await env.AGENT_TASK.get(id);
					await instance.sendEvent({
						type: "owner-decision",
						payload: decision,
					});
					return json({ ok: true });
				}

				if (id && action === "cancel" && method === "POST") {
					await terminate(env, id);
					const task = await center.updateTask(
						id,
						{ status: "cancelled", note: "Cancelled by owner." },
						"owner",
					);
					if (!task) return json({ error: "Task not found" }, 404);
					return json(task);
				}
			}

			return json({ error: "Not Found" }, 404);
		} catch (err) {
			const message = err instanceof Error ? err.message : "Request failed";
			const status = /not found/i.test(message) ? 404 : 400;
			return json({ error: message }, status);
		}
	},
} satisfies ExportedHandler<Env>;

async function stopActiveTasks(
	env: Env,
	center: DurableObjectStub<import("./command-center").CommandCenterDO>,
	note: string,
) {
	const ids = await center.activeTaskIds();
	for (const id of ids) {
		await terminate(env, id);
		await center.updateTask(id, { status: "cancelled", note }, "owner");
	}
}

async function terminate(env: Env, id: string) {
	try {
		const instance = await env.AGENT_TASK.get(id);
		await instance.terminate();
	} catch {
		// Already finished or never started
	}
}

async function readJson(request: Request): Promise<Record<string, unknown>> {
	try {
		const body = await request.json();
		return body && typeof body === "object"
			? (body as Record<string, unknown>)
			: {};
	} catch {
		return {};
	}
}

function json(data: unknown, status = 200): Response {
	return Response.json(data, {
		status,
		headers: { "Cache-Control": "no-store" },
	});
}
