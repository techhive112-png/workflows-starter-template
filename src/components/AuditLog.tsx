import type { AuditEntry } from "../types";
import { Card } from "./ui";

export function AuditLog({ entries }: { entries: AuditEntry[] }) {
	return (
		<Card title="Audit log" subtitle="Everything that happened, newest first.">
			{entries.length === 0 ? (
				<p className="text-sm text-neutral-500 dark:text-neutral-400">
					Nothing yet.
				</p>
			) : (
				<ol className="space-y-2 max-h-96 overflow-auto pr-1">
					{entries.map((e) => (
						<li key={e.id} className="text-xs leading-relaxed">
							<span className="text-neutral-400 tabular-nums">
								{new Date(e.at).toLocaleString()}
							</span>{" "}
							<span className="font-medium text-neutral-700 dark:text-neutral-200">
								{e.actor}
							</span>{" "}
							<span className="text-neutral-600 dark:text-neutral-300">
								{e.action}
							</span>
							<div className="text-neutral-500 dark:text-neutral-400 break-words">
								{e.detail}
							</div>
						</li>
					))}
				</ol>
			)}
		</Card>
	);
}
