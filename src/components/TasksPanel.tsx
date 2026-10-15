import { useState } from "react";
import type { AgentWorker, Task, TaskStatus } from "../types";
import { ACTIVE_STATUSES } from "../types";
import { timeAgo } from "../utils";
import { Button, Card, inputClass } from "./ui";

const statusStyle: Record<TaskStatus, string> = {
	queued:
		"bg-neutral-100 text-neutral-700 dark:bg-neutral-800 dark:text-neutral-300",
	running: "bg-sky-100 text-sky-800 dark:bg-sky-500/15 dark:text-sky-300",
	awaiting_approval:
		"bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300",
	approved:
		"bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300",
	completed:
		"bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300",
	rejected: "bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300",
	blocked: "bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300",
	failed: "bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300",
	cancelled:
		"bg-neutral-100 text-neutral-600 dark:bg-neutral-800 dark:text-neutral-400",
};

const statusLabel: Record<TaskStatus, string> = {
	queued: "Queued",
	running: "Working…",
	awaiting_approval: "Needs your review",
	approved: "Approved",
	completed: "Done",
	rejected: "Rejected",
	blocked: "Blocked by rules",
	failed: "Failed",
	cancelled: "Cancelled",
};

export function TaskComposer({
	workers,
	killSwitch,
	onAssign,
}: {
	workers: AgentWorker[];
	killSwitch: boolean;
	onAssign: (workerId: string, instruction: string) => Promise<void>;
}) {
	const available = workers.filter((w) => w.enabled);
	const [workerId, setWorkerId] = useState("");
	const [instruction, setInstruction] = useState("");
	const [busy, setBusy] = useState(false);

	const selected = available.find((w) => w.id === workerId) ?? available[0];

	const submit = async (e: React.FormEvent) => {
		e.preventDefault();
		if (!selected) return;
		setBusy(true);
		try {
			await onAssign(selected.id, instruction);
			setInstruction("");
		} finally {
			setBusy(false);
		}
	};

	return (
		<Card title="Give an order" subtitle="Only you can assign work.">
			<form onSubmit={submit} className="space-y-2">
				<select
					className={inputClass}
					value={selected?.id ?? ""}
					onChange={(e) => setWorkerId(e.target.value)}
					disabled={available.length === 0}
				>
					{available.length === 0 && <option>No active workers</option>}
					{available.map((w) => (
						<option key={w.id} value={w.id}>
							{w.name}
						</option>
					))}
				</select>
				<textarea
					className={`${inputClass} min-h-24`}
					placeholder="What should this worker do?"
					value={instruction}
					onChange={(e) => setInstruction(e.target.value)}
				/>
				<Button
					type="submit"
					className="w-full py-2"
					disabled={killSwitch || !selected || !instruction.trim() || busy}
				>
					{killSwitch ? "Kill switch is on" : busy ? "Sending…" : "Send order"}
				</Button>
			</form>
		</Card>
	);
}

export function TaskFeed({
	tasks,
	onDecide,
	onCancel,
	onClear,
}: {
	tasks: Task[];
	onDecide: (id: string, approved: boolean, note?: string) => Promise<void>;
	onCancel: (id: string) => Promise<void>;
	onClear: () => Promise<void>;
}) {
	const hasFinished = tasks.some((t) => !ACTIVE_STATUSES.includes(t.status));
	return (
		<Card
			title="Tasks"
			subtitle="Live. Results wait here for your sign-off."
			action={
				hasFinished && (
					<Button variant="ghost" onClick={onClear}>
						Clear finished
					</Button>
				)
			}
		>
			{tasks.length === 0 ? (
				<p className="text-sm text-neutral-500 dark:text-neutral-400">
					No tasks yet.
				</p>
			) : (
				<div className="space-y-3">
					{tasks.map((t) => (
						<TaskItem
							key={t.id}
							task={t}
							onDecide={onDecide}
							onCancel={onCancel}
						/>
					))}
				</div>
			)}
		</Card>
	);
}

function TaskItem({
	task,
	onDecide,
	onCancel,
}: {
	task: Task;
	onDecide: (id: string, approved: boolean, note?: string) => Promise<void>;
	onCancel: (id: string) => Promise<void>;
}) {
	const [note, setNote] = useState("");
	const active = ACTIVE_STATUSES.includes(task.status);

	return (
		<article className="rounded-lg border border-neutral-200 dark:border-neutral-800 p-3">
			<header className="flex items-center justify-between gap-2 text-xs">
				<span className="font-medium text-neutral-900 dark:text-neutral-100">
					{task.workerName}
				</span>
				<div className="flex items-center gap-2">
					<span className="text-neutral-400">{timeAgo(task.createdAt)}</span>
					<span
						className={`rounded px-1.5 py-0.5 font-medium ${statusStyle[task.status]}`}
					>
						{statusLabel[task.status]}
					</span>
				</div>
			</header>
			<p className="text-sm text-neutral-700 dark:text-neutral-300 mt-2 whitespace-pre-wrap">
				{task.instruction}
			</p>
			{task.steps.length > 0 && (
				<details className="mt-2 text-xs" open={task.status === "running"}>
					<summary className="cursor-pointer text-neutral-500 dark:text-neutral-400">
						What it did ({task.steps.length} step
						{task.steps.length === 1 ? "" : "s"})
					</summary>
					<ol className="mt-1 space-y-1.5 pl-1">
						{task.steps.map((s, i) => (
							<li key={i}>
								<span className="font-medium text-neutral-700 dark:text-neutral-200">
									{i + 1}. {s.title}
								</span>
								<div className="text-neutral-500 dark:text-neutral-400 whitespace-pre-wrap break-words line-clamp-3">
									{s.detail}
								</div>
							</li>
						))}
					</ol>
				</details>
			)}
			{task.output && (
				<div className="mt-2 rounded-md bg-neutral-50 dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 p-2.5 text-sm text-neutral-800 dark:text-neutral-200 whitespace-pre-wrap max-h-80 overflow-auto">
					{task.output}
				</div>
			)}
			{task.proposal && (
				<div className="mt-2 rounded-md border border-violet-300/60 dark:border-violet-500/30 bg-violet-50/50 dark:bg-violet-500/5 p-2.5 text-xs">
					<p className="font-medium text-violet-900 dark:text-violet-200">
						Code change for {task.proposal.repo}
					</p>
					{task.proposal.files.map((f) => (
						<details key={f.path} className="mt-1">
							<summary className="cursor-pointer font-mono text-neutral-700 dark:text-neutral-300">
								{f.delete ? "🗑 delete" : "✏️"} {f.path}
							</summary>
							{!f.delete && (
								<pre className="mt-1 max-h-72 overflow-auto rounded bg-neutral-900 text-neutral-100 p-2 text-[11px] leading-snug">
									{f.content}
								</pre>
							)}
						</details>
					))}
				</div>
			)}
			{task.resultUrl && (
				<a
					href={task.resultUrl}
					target="_blank"
					rel="noopener noreferrer"
					className="mt-2 inline-block text-sm font-medium text-violet-700 dark:text-violet-300 underline"
				>
					Open pull request →
				</a>
			)}
			{task.note && (
				<p className="text-xs text-neutral-500 dark:text-neutral-400 mt-2">
					{task.note}
				</p>
			)}

			{task.status === "awaiting_approval" && (
				<div className="mt-3 flex flex-col sm:flex-row gap-2">
					<input
						className={inputClass}
						placeholder="Optional note"
						value={note}
						onChange={(e) => setNote(e.target.value)}
					/>
					<div className="flex gap-2 shrink-0">
						<Button onClick={() => onDecide(task.id, true, note)}>
							{task.proposal ? "Approve & open PR" : "Approve"}
						</Button>
						<Button
							variant="secondary"
							onClick={() => onDecide(task.id, false, note)}
						>
							Reject
						</Button>
					</div>
				</div>
			)}
			{active && task.status !== "awaiting_approval" && (
				<div className="mt-2">
					<Button variant="ghost" onClick={() => onCancel(task.id)}>
						Stop this task
					</Button>
				</div>
			)}
		</article>
	);
}
