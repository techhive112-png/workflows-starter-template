import { useEffect, useState } from "react";
import { api, ApiError, loadToken, saveToken } from "./api";
import { BackgroundDots } from "./components/BackgroundDots";
import { AuditLog } from "./components/AuditLog";
import { Login } from "./components/Login";
import { RulesPanel } from "./components/RulesPanel";
import { TaskComposer, TaskFeed } from "./components/TasksPanel";
import { WorkersPanel } from "./components/WorkersPanel";
import { Button } from "./components/ui";
import { useCommandCenter } from "./hooks/useCommandCenter";

function App() {
	const [token, setToken] = useState<string | null>(loadToken);

	const login = (t: string) => {
		saveToken(t);
		setToken(t);
	};
	const logout = () => {
		saveToken(null);
		setToken(null);
	};

	return (
		<div className="min-h-screen bg-neutral-50/30 dark:bg-neutral-950 relative">
			<div className="absolute inset-0 text-neutral-200/50 dark:text-neutral-700/40 overflow-hidden pointer-events-none">
				<BackgroundDots />
			</div>
			{token ? (
				<Dashboard token={token} onLogout={logout} />
			) : (
				<Login onLogin={login} />
			)}
		</div>
	);
}

function Dashboard({
	token,
	onLogout,
}: {
	token: string;
	onLogout: () => void;
}) {
	const { state, connected, unauthorized } = useCommandCenter(token);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		if (unauthorized) onLogout();
	}, [unauthorized, onLogout]);

	const call = async (path: string, method: string, body?: unknown) => {
		setError(null);
		try {
			await api(token, path, method, body);
		} catch (err) {
			if (err instanceof ApiError && err.status === 401) onLogout();
			setError(err instanceof Error ? err.message : "Something went wrong");
			throw err;
		}
	};
	// UI handlers swallow the error after showing it
	const run = (path: string, method: string, body?: unknown) =>
		call(path, method, body).catch(() => {});

	if (!state) {
		return (
			<div className="min-h-screen flex items-center justify-center text-sm text-neutral-500 relative z-10">
				Connecting to your Command Center…
			</div>
		);
	}

	const { settings, workers, tasks, audit, capabilities } = state;
	const pending = tasks.filter((t) => t.status === "awaiting_approval").length;

	return (
		<div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 py-6">
			<header className="flex flex-wrap items-center justify-between gap-3 mb-6">
				<div>
					<h1 className="text-lg font-semibold text-neutral-900 dark:text-neutral-100">
						{settings.ownerName}'s AI Command Center
					</h1>
					<p className="text-xs text-neutral-500 dark:text-neutral-400 flex items-center gap-1.5">
						<span
							className={`h-1.5 w-1.5 rounded-full ${connected ? "bg-emerald-500" : "bg-neutral-400"}`}
						/>
						{connected ? "Live" : "Reconnecting…"} · {workers.length} worker
						{workers.length === 1 ? "" : "s"}
						{pending > 0 && ` · ${pending} waiting for your review`}
					</p>
				</div>
				<div className="flex items-center gap-2">
					<Button
						variant={settings.killSwitch ? "primary" : "danger"}
						onClick={() => {
							if (
								settings.killSwitch ||
								confirm(
									"Stop ALL workers now? Running tasks will be cancelled.",
								)
							) {
								run("/api/settings", "PUT", {
									killSwitch: !settings.killSwitch,
								});
							}
						}}
					>
						{settings.killSwitch ? "▶ Resume workers" : "■ Kill switch"}
					</Button>
					<Button variant="ghost" onClick={onLogout}>
						Lock
					</Button>
				</div>
			</header>

			{settings.killSwitch && (
				<div className="mb-4 rounded-lg bg-red-600 text-white text-sm px-4 py-2.5">
					Kill switch is ON. No worker can run until you resume them.
				</div>
			)}
			{error && (
				<div className="mb-4 rounded-lg bg-red-50 dark:bg-red-500/10 text-red-700 dark:text-red-300 text-sm px-4 py-2.5 flex justify-between gap-3">
					<span>{error}</span>
					<button onClick={() => setError(null)} aria-label="Dismiss">
						×
					</button>
				</div>
			)}

			<div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
				<div className="space-y-4 min-w-0">
					<TaskComposer
						workers={workers}
						killSwitch={settings.killSwitch}
						onAssign={(workerId, instruction) =>
							call("/api/tasks", "POST", { workerId, instruction })
						}
					/>
					<WorkersPanel
						workers={workers}
						capabilities={capabilities}
						onCreate={(draft) => call("/api/workers", "POST", draft)}
						onUpdate={(id, patch) => call(`/api/workers/${id}`, "PUT", patch)}
						onDelete={(id) => run(`/api/workers/${id}`, "DELETE")}
					/>
					<RulesPanel
						settings={settings}
						onSave={(patch) => call("/api/settings", "PUT", patch)}
					/>
				</div>
				<div className="space-y-4 min-w-0">
					<TaskFeed
						tasks={tasks}
						onDecide={(id, approved, note) =>
							run(`/api/tasks/${id}/decision`, "POST", { approved, note })
						}
						onCancel={(id) => run(`/api/tasks/${id}/cancel`, "POST")}
						onClear={() => run("/api/tasks", "DELETE")}
					/>
					<AuditLog entries={audit} />
				</div>
			</div>
		</div>
	);
}

export default App;
