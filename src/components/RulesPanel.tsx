import { useEffect, useState } from "react";
import type { Settings } from "../types";
import { linesToList } from "../utils";
import { Button, Card, inputClass } from "./ui";

export function RulesPanel({
	settings,
	onSave,
}: {
	settings: Settings;
	onSave: (patch: Partial<Settings>) => Promise<void>;
}) {
	const [ownerName, setOwnerName] = useState(settings.ownerName);
	const [rules, setRules] = useState(settings.globalRules.join("\n"));
	const [blocked, setBlocked] = useState(settings.blockedTerms.join("\n"));
	const [saving, setSaving] = useState(false);

	useEffect(() => {
		setOwnerName(settings.ownerName);
		setRules(settings.globalRules.join("\n"));
		setBlocked(settings.blockedTerms.join("\n"));
	}, [settings.ownerName, settings.globalRules, settings.blockedTerms]);

	const dirty =
		ownerName !== settings.ownerName ||
		rules !== settings.globalRules.join("\n") ||
		blocked !== settings.blockedTerms.join("\n");

	const save = async () => {
		setSaving(true);
		try {
			await onSave({
				ownerName,
				globalRules: linesToList(rules),
				blockedTerms: linesToList(blocked),
			});
		} finally {
			setSaving(false);
		}
	};

	return (
		<Card
			title="Your rules"
			subtitle="Every worker must follow these, above their own rules."
			action={
				<Button onClick={save} disabled={!dirty || saving}>
					{saving ? "Saving…" : "Save"}
				</Button>
			}
		>
			<label className="block text-xs font-medium text-neutral-600 dark:text-neutral-300 mb-1">
				Your name (workers serve only this person)
			</label>
			<input
				className={inputClass}
				value={ownerName}
				onChange={(e) => setOwnerName(e.target.value)}
			/>

			<label className="block text-xs font-medium text-neutral-600 dark:text-neutral-300 mt-4 mb-1">
				Rules — one per line
			</label>
			<textarea
				className={`${inputClass} min-h-36 font-mono text-xs`}
				value={rules}
				onChange={(e) => setRules(e.target.value)}
			/>

			<label className="block text-xs font-medium text-neutral-600 dark:text-neutral-300 mt-4 mb-1">
				Blocked words — one per line
			</label>
			<textarea
				className={`${inputClass} min-h-20 font-mono text-xs`}
				placeholder={"password\nbank account"}
				value={blocked}
				onChange={(e) => setBlocked(e.target.value)}
			/>
			<p className="text-xs text-neutral-500 dark:text-neutral-400 mt-1">
				Checked in code, not just asked of the AI: tasks or results containing
				these are blocked.
			</p>
		</Card>
	);
}
