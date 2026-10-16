import { useState } from "react";
import type { AgentWorker } from "../types";
import { linesToList } from "../utils";
import { Button, Card, Toggle, inputClass } from "./ui";

export interface WorkerDraft {
	name: string;
	role: string;
	rules: string[];
	requireApproval: boolean;
	enabled?: boolean;
}

export function WorkersPanel({
	workers,
	onCreate,
	onUpdate,
	onDelete,
}: {
	workers: AgentWorker[];
	onCreate: (draft: WorkerDraft) => Promise<void>;
	onUpdate: (id: string, patch: Partial<WorkerDraft>) => Promise<void>;
	onDelete: (id: string) => Promise<void>;
}) {
	const [editing, setEditing] = useState<string | "new" | null>(null);

	return (
		<Card
			title="Your AI workers"
			subtitle="Each worker has a role and its own rules on top of yours."
			action={
				editing !== "new" && (
					<Button variant="secondary" onClick={() => setEditing("new")}>
						+ New worker
					</Button>
				)
			}
		>
			<div className="space-y-3">
				{editing === "new" && (
					<WorkerForm
						onCancel={() => setEditing(null)}
						onSubmit={async (draft) => {
							await onCreate(draft);
							setEditing(null);
						}}
					/>
				)}

				{workers.length === 0 && editing !== "new" && (
					<p className="text-sm text-neutral-500 dark:text-neutral-400">
						No workers yet. Create your first one — for example “Researcher” or
						“Email drafter”.
					</p>
				)}

				{workers.map((w) =>
					editing === w.id ? (
						<WorkerForm
							key={w.id}
							initial={w}
							onCancel={() => setEditing(null)}
							onSubmit={async (draft) => {
								await onUpdate(w.id, draft);
								setEditing(null);
							}}
						/>
					) : (
						<div
							key={w.id}
							className="rounded-lg border border-neutral-200 dark:border-neutral-800 p-3"
						>
							<div className="flex flex-wrap items-center justify-between gap-2">
								<div className="flex items-center gap-2 min-w-0">
									<span
										className={`h-2 w-2 rounded-full shrink-0 ${w.enabled ? "bg-emerald-500" : "bg-neutral-400"}`}
									/>
									<span className="font-medium text-sm text-neutral-900 dark:text-neutral-100 truncate">
										{w.name}
									</span>
									{w.requireApproval && (
										<span className="text-[10px] uppercase tracking-wide rounded bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300 px-1.5 py-0.5">
											needs approval
										</span>
									)}
								</div>
								<div className="flex items-center gap-1 shrink-0">
									<Toggle
										checked={w.enabled}
										label={w.enabled ? "On" : "Off"}
										onChange={(enabled) => onUpdate(w.id, { enabled })}
									/>
									<Button variant="ghost" onClick={() => setEditing(w.id)}>
										Edit
									</Button>
									<Button
										variant="ghost"
										onClick={() => {
											if (confirm(`Delete ${w.name}?`)) onDelete(w.id);
										}}
									>
										Delete
									</Button>
								</div>
							</div>
							{w.role && (
								<p className="text-xs text-neutral-600 dark:text-neutral-400 mt-2">
									{w.role}
								</p>
							)}
							{w.rules.length > 0 && (
								<ul className="mt-2 text-xs text-neutral-500 dark:text-neutral-400 list-disc pl-4 space-y-0.5">
									{w.rules.map((r, i) => (
										<li key={i}>{r}</li>
									))}
								</ul>
							)}
						</div>
					),
				)}
			</div>
		</Card>
	);
}

function WorkerForm({
	initial,
	onSubmit,
	onCancel,
}: {
	initial?: AgentWorker;
	onSubmit: (draft: WorkerDraft) => Promise<void>;
	onCancel: () => void;
}) {
	const [name, setName] = useState(initial?.name ?? "");
	const [role, setRole] = useState(initial?.role ?? "");
	const [rules, setRules] = useState(initial?.rules.join("\n") ?? "");
	const [requireApproval, setRequireApproval] = useState(
		initial?.requireApproval ?? true,
	);
	const [busy, setBusy] = useState(false);

	const submit = async (e: React.FormEvent) => {
		e.preventDefault();
		setBusy(true);
		try {
			await onSubmit({
				name,
				role,
				rules: linesToList(rules),
				requireApproval,
			});
		} finally {
			setBusy(false);
		}
	};

	return (
		<form
			onSubmit={submit}
			className="rounded-lg border border-orange-300/60 dark:border-orange-500/30 bg-orange-50/40 dark:bg-orange-500/5 p-3 space-y-2"
		>
			<input
				className={inputClass}
				placeholder="Name, e.g. Researcher"
				value={name}
				autoFocus
				onChange={(e) => setName(e.target.value)}
			/>
			<textarea
				className={`${inputClass} min-h-16`}
				placeholder="Role: what this worker does for you"
				value={role}
				onChange={(e) => setRole(e.target.value)}
			/>
			<textarea
				className={`${inputClass} min-h-16 font-mono text-xs`}
				placeholder={
					"Worker rules — one per line\nAlways answer in English\nKeep answers under 200 words"
				}
				value={rules}
				onChange={(e) => setRules(e.target.value)}
			/>
			<div className="flex items-center justify-between pt-1">
				<Toggle
					checked={requireApproval}
					onChange={setRequireApproval}
					label="I must approve every result"
				/>
				<div className="flex gap-2">
					<Button type="button" variant="ghost" onClick={onCancel}>
						Cancel
					</Button>
					<Button type="submit" disabled={!name.trim() || busy}>
						{initial ? "Save" : "Create"}
					</Button>
				</div>
			</div>
		</form>
	);
}
