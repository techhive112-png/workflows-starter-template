/**
 * Shared types for the Command Center dashboard (mirrors worker/command-center.ts)
 */

export interface Settings {
	ownerName: string;
	killSwitch: boolean;
	globalRules: string[];
	blockedTerms: string[];
}

export interface AgentWorker {
	id: string;
	name: string;
	role: string;
	rules: string[];
	enabled: boolean;
	requireApproval: boolean;
	createdAt: number;
}

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

export interface AuditEntry {
	id: number;
	at: number;
	actor: string;
	action: string;
	detail: string;
}

export interface CommandCenterState {
	settings: Settings;
	workers: AgentWorker[];
	tasks: Task[];
	audit: AuditEntry[];
}

export const ACTIVE_STATUSES: TaskStatus[] = [
	"queued",
	"running",
	"awaiting_approval",
];
