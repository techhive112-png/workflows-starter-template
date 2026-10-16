import { useState } from "react";
import { api } from "../api";
import { Button, inputClass } from "./ui";

export function Login({ onLogin }: { onLogin: (token: string) => void }) {
	const [token, setToken] = useState("");
	const [error, setError] = useState<string | null>(null);
	const [busy, setBusy] = useState(false);

	const submit = async (e: React.FormEvent) => {
		e.preventDefault();
		setBusy(true);
		setError(null);
		try {
			await api(token, "/api/state");
			onLogin(token);
		} catch (err) {
			setError(err instanceof Error ? err.message : "Could not sign in");
		} finally {
			setBusy(false);
		}
	};

	return (
		<div className="min-h-screen flex items-center justify-center px-4">
			<form
				onSubmit={submit}
				className="w-full max-w-sm rounded-xl bg-white/90 dark:bg-neutral-900/90 ring-glass shadow-float p-6 relative z-10"
			>
				<div className="text-2xl mb-2">🔐</div>
				<h1 className="text-lg font-semibold text-neutral-900 dark:text-neutral-100">
					Personal AI Command Center
				</h1>
				<p className="text-sm text-neutral-500 dark:text-neutral-400 mt-1 mb-5">
					Owner only. Your AI workers answer to you and nobody else.
				</p>
				<input
					type="password"
					autoFocus
					autoComplete="current-password"
					placeholder="Owner token"
					value={token}
					onChange={(e) => setToken(e.target.value)}
					className={inputClass}
				/>
				{error && <p className="text-sm text-red-600 mt-2">{error}</p>}
				<Button
					type="submit"
					className="w-full mt-4 py-2"
					disabled={!token || busy}
				>
					{busy ? "Checking…" : "Unlock"}
				</Button>
			</form>
		</div>
	);
}
