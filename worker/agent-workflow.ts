import { WorkflowEntrypoint, WorkflowStep } from "cloudflare:workers";
import type { WorkflowEvent } from "cloudflare:workers";
import { NonRetryableError } from "cloudflare:workflows";
import {
	buildToolInstructions,
	describeAction,
	parseAction,
	runTool,
} from "./agent";
import type { TaskContext } from "./command-center";
import { type CodeProposal, checkProposal, openPullRequest } from "./github";
import {
	type AgentWorker,
	type Settings,
	buildSystemPrompt,
	findViolations,
	hasAnySkill,
} from "./rules";

/** There is exactly one Command Center, and it belongs to the owner. */
export const OWNER_CENTER = "owner";

export const DEFAULT_MODEL = "@cf/meta/llama-3.3-70b-instruct-fp8-fast";
export const CODER_MODEL = "@cf/qwen/qwen2.5-coder-32b-instruct";

/** Most tool calls a worker may make for one task */
export const MAX_TURNS = 8;

type ChatMessage = { role: "system" | "user" | "assistant"; content: string };

export interface AgentTaskParams {
	taskId: string;
}

export interface OwnerDecision {
	approved: boolean;
	note?: string;
}

/**
 * AgentTaskWorkflow - one durable run of an AI worker doing one task.
 *
 *   check orders -> do the work -> re-check rules -> owner review -> done
 *
 * Every write back to the Command Center happens inside a step, so if the
 * workflow is replayed (after a pause or restart) nothing is done twice.
 */
export class AgentTaskWorkflow extends WorkflowEntrypoint<
	Env,
	AgentTaskParams
> {
	async run(event: WorkflowEvent<AgentTaskParams>, step: WorkflowStep) {
		const { taskId } = event.payload;
		const center = this.env.COMMAND_CENTER.get(
			this.env.COMMAND_CENTER.idFromName(OWNER_CENTER),
		);

		const finish = async (
			name: string,
			status: "blocked" | "completed" | "approved" | "rejected" | "failed",
			fields: {
				output?: string | null;
				note?: string | null;
				proposal?: CodeProposal | null;
				resultUrl?: string | null;
			} = {},
			actor = "system",
		) => {
			await step.do(name, async () => {
				await center.updateTask(taskId, { status, ...fields }, actor);
			});
			return { status, note: fields.note ?? null };
		};

		// 1. Load the orders and check them against the owner's rules
		const orders = await step.do("check orders", async () => {
			const context = await center.getTaskContext(taskId);
			if (!context) throw new NonRetryableError("Task not found");
			return context as TaskContext;
		});
		const { task, worker, settings } = orders;

		if (settings.killSwitch) {
			return finish("block task", "blocked", {
				note: "Kill switch is on — all workers are stopped.",
			});
		}
		if (!worker) {
			return finish("block task", "blocked", { note: "Worker was deleted." });
		}
		if (!worker.enabled) {
			return finish("block task", "blocked", {
				note: `${worker.name} is switched off.`,
			});
		}
		const inputViolations = findViolations(
			task.instruction,
			settings.blockedTerms,
		);
		if (inputViolations.length) {
			return finish("block task", "blocked", {
				note: `Instruction contains blocked terms: ${inputViolations.join(", ")}`,
			});
		}

		// 2. Do the work with the owner's rules as the system prompt
		await step.do("mark running", async () => {
			await center.updateTask(taskId, { status: "running" });
		});

		let output: string;
		let proposal: CodeProposal | null = null;
		try {
			if (hasAnySkill(worker.skills)) {
				const result = await this.useTools(
					step,
					taskId,
					settings,
					worker,
					task.instruction,
				);
				if ("blocked" in result) {
					return finish("block task", "blocked", { note: result.blocked });
				}
				({ output, proposal } = result);
			} else {
				output = await step.do("do the work", AI_STEP, async () =>
					this.askAI(worker, [
						{ role: "system", content: buildSystemPrompt(settings, worker) },
						{ role: "user", content: task.instruction },
					]),
				);
			}
		} catch (err) {
			// Retries are used up - record it instead of leaving the task "running"
			const reason = err instanceof Error ? err.message : String(err);
			return finish("fail task", "failed", {
				note: `The AI could not finish: ${reason.slice(0, 300)}`,
			});
		}

		// 3. Re-check: the owner may have hit the kill switch while it was working,
		//    and the output itself must not break the blocked-terms rule.
		const latest = await step.do("re-check rules", async () => {
			return (await center.getSettings()) as Settings;
		});
		if (latest.killSwitch) {
			return finish("block result", "blocked", {
				note: "Kill switch was turned on — result discarded.",
			});
		}
		const outputViolations = findViolations(
			proposal ? `${output}\n${JSON.stringify(proposal)}` : output,
			latest.blockedTerms,
		);
		if (outputViolations.length) {
			return finish("block result", "blocked", {
				note: `Result contained blocked terms (${outputViolations.join(", ")}) and was withheld.`,
			});
		}

		// Code changes always need the owner's approval, whatever the worker setting
		if (!worker.requireApproval && !proposal) {
			return finish("deliver result", "completed", { output });
		}

		// 4. Nothing leaves without the owner's sign-off
		await step.do("submit for review", async () => {
			await center.updateTask(taskId, {
				status: "awaiting_approval",
				output,
				proposal,
			});
		});

		let decision: OwnerDecision;
		try {
			const reply = await step.waitForEvent<OwnerDecision>("owner review", {
				type: "owner-decision",
				timeout: "7 days",
			});
			decision = reply.payload;
		} catch {
			return finish("expire task", "failed", {
				note: "No decision from the owner within 7 days.",
			});
		}

		const note = decision.note?.slice(0, 500) || null;
		if (!decision.approved || !proposal) {
			return finish(
				"record decision",
				decision.approved ? "approved" : "rejected",
				{ note },
				"owner",
			);
		}

		// 5. Approved code change: only now does anything touch GitHub
		const approvedChange = proposal;
		let prUrl: string;
		try {
			prUrl = await step.do(
				"open pull request",
				{ retries: { limit: 2, delay: "10 seconds" }, timeout: "3 minutes" },
				async () => {
					const current = (await center.getSettings()) as Settings;
					return openPullRequest(
						this.env,
						current.githubRepos,
						approvedChange,
						branchName(approvedChange.title, taskId),
					);
				},
			);
		} catch (err) {
			const reason = err instanceof Error ? err.message : String(err);
			return finish("record decision", "failed", {
				note: `Approved, but the pull request could not be opened: ${reason.slice(0, 300)}`,
			});
		}
		return finish(
			"record decision",
			"approved",
			{ note: note ?? "Pull request opened.", resultUrl: prUrl },
			"owner",
		);
	}

	private async askAI(worker: AgentWorker, messages: ChatMessage[]) {
		const coder = worker.model === "coder";
		const model = (
			coder ? CODER_MODEL : this.env.AI_MODEL || DEFAULT_MODEL
		) as keyof AiModels;
		const result = await this.env.AI.run(model, {
			messages,
			max_tokens: coder ? 4096 : 2048,
		});
		return readResponse(result);
	}

	/**
	 * Tool loop: think -> use a tool -> look at the result -> repeat.
	 * Each turn is its own step, so a long task survives restarts.
	 */
	private async useTools(
		step: WorkflowStep,
		taskId: string,
		settings: Settings,
		worker: AgentWorker,
		instruction: string,
	): Promise<
		{ output: string; proposal: CodeProposal | null } | { blocked: string }
	> {
		const center = this.env.COMMAND_CENTER.get(
			this.env.COMMAND_CENTER.idFromName(OWNER_CENTER),
		);
		const messages: ChatMessage[] = [
			{
				role: "system",
				content:
					buildSystemPrompt(settings, worker) +
					"\n" +
					buildToolInstructions(worker, settings),
			},
			{ role: "user", content: instruction },
		];
		let logged = 0;

		for (let turn = 1; turn <= MAX_TURNS + 1; turn++) {
			if (turn > MAX_TURNS) {
				messages.push({
					role: "user",
					content: `You have used all ${MAX_TURNS} tool calls. Give your final answer now.`,
				});
			}
			const reply = await step.do(`think ${turn}`, AI_STEP, async () =>
				this.askAI(worker, messages),
			);
			messages.push({ role: "assistant", content: reply });

			const action = parseAction(reply);
			if (!action) {
				// Plain text with no JSON at all is taken as the answer
				if (!reply.includes("{") || turn > MAX_TURNS) {
					return { output: reply, proposal: null };
				}
				messages.push({
					role: "user",
					content:
						"That was not valid JSON. Reply with exactly one JSON object.",
				});
				continue;
			}
			if (action.tool === "final") {
				return { output: action.answer || reply, proposal: null };
			}
			if (action.tool === "propose_code_change") {
				if (!worker.skills.github) {
					messages.push({
						role: "user",
						content: "Observation:\nERROR: Not allowed: GitHub",
					});
					continue;
				}
				try {
					const proposal = checkProposal(action.proposal, settings.githubRepos);
					const files = proposal.files
						.map((f) => `- ${f.delete ? "delete" : "write"} ${f.path}`)
						.join("\n");
					return {
						output: `**${proposal.title}** (${proposal.repo})\n\n${proposal.description}\n\nFiles:\n${files}`,
						proposal,
					};
				} catch (err) {
					const reason = err instanceof Error ? err.message : String(err);
					messages.push({
						role: "user",
						content: `Observation:\nERROR: ${reason}`,
					});
					continue;
				}
			}
			if (turn > MAX_TURNS) break;

			const violations = findViolations(
				JSON.stringify(action.args),
				settings.blockedTerms,
			);
			const observation = violations.length
				? `ERROR: Blocked by the owner's rules (${violations.join(", ")}).`
				: await step.do(
						`tool ${turn}`,
						{ retries: { limit: 1, delay: "3 seconds" }, timeout: "2 minutes" },
						async () => {
							try {
								return await runTool(this.env, settings, worker, action);
							} catch (err) {
								return `ERROR: ${err instanceof Error ? err.message : String(err)}`;
							}
						},
					);

			const index = logged++;
			const stopped = await step.do(`log ${turn}`, async () => {
				await center.recordStep(taskId, index, {
					title: describeAction(action),
					detail: observation.slice(0, 600),
				});
				return ((await center.getSettings()) as Settings).killSwitch;
			});
			if (stopped)
				return { blocked: "Kill switch was turned on — work stopped." };

			messages.push({ role: "user", content: `Observation:\n${observation}` });
		}
		return { output: messages[messages.length - 1].content, proposal: null };
	}
}

const AI_STEP = {
	retries: { limit: 2, delay: "5 seconds", backoff: "exponential" },
	timeout: "3 minutes",
} as const;

function branchName(title: string, taskId: string): string {
	const slug = title
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, "-")
		.replace(/^-+|-+$/g, "")
		.slice(0, 40);
	return `ai/${slug || "change"}-${taskId.slice(0, 8)}`;
}

function readResponse(result: unknown): string {
	if (typeof result === "string") return result;
	if (result && typeof result === "object" && "response" in result) {
		const response = (result as { response: unknown }).response;
		if (typeof response === "string") return response.trim();
		if (response != null) return JSON.stringify(response);
	}
	throw new Error("The AI model returned no text");
}
