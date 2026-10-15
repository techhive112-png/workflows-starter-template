/**
 * Shared types for the Command Center dashboard (mirrors worker/command-center.ts)
 */

export interface Settings {
	ownerName: string;
	killSwitch: boolean;
	globalRules: string[];
	blockedTerms: string[];
	githubRepos: string[];
}

export interface Skills {
	readPages: boolean;
	webSearch: boolean;
	browser: boolean;
	browserActions: boolean;
	github: boolean;
}

export type WorkerModel = "general" | "coder";

export interface AgentWorker {
	id: string;
	name: string;
	role: string;
	rules: string[];
	enabled: boolean;
	requireApproval: boolean;
	skills: Skills;
	model: WorkerModel;
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
	steps: TaskStep[];
	proposal: CodeProposal | null;
	resultUrl: string | null;
	createdAt: number;
	updatedAt: number;
}

export interface TaskStep {
	at: number;
	title: string;
	detail: string;
}

export interface CodeProposal {
	repo: string;
	title: string;
	description: string;
	files: { path: string; content?: string; delete?: boolean }[];
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
	capabilities: { browser: boolean; github: boolean };
}

export const ACTIVE_STATUSES: TaskStatus[] = [
	"queued",
	"running",
	"awaiting_approval",
];
