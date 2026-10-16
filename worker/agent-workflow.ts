import { WorkflowEntrypoint, WorkflowStep } from "cloudflare:workers";
import type { WorkflowEvent } from "cloudflare:workers";
import { NonRetryableError } from "cloudflare:workflows";
import type { TaskContext } from "./command-center";
import { type Settings, buildSystemPrompt, findViolations } from "./rules";

/** There is exactly one Command Center, and it belongs to the owner. */
export const OWNER_CENTER = "owner";

export const DEFAULT_MODEL = "@cf/meta/llama-3.3-70b-instruct-fp8-fast";

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
			fields: { output?: string | null; note?: string | null } = {},
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
		try {
			output = await step.do(
				"do the work",
				{
					retries: { limit: 2, delay: "5 seconds", backoff: "exponential" },
					timeout: "2 minutes",
				},
				async () => {
					const model = (this.env.AI_MODEL || DEFAULT_MODEL) as keyof AiModels;
					const result = await this.env.AI.run(model, {
						messages: [
							{ role: "system", content: buildSystemPrompt(settings, worker) },
							{ role: "user", content: task.instruction },
						],
						max_tokens: 1024,
					});
					return readResponse(result);
				},
			);
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
		const outputViolations = findViolations(output, latest.blockedTerms);
		if (outputViolations.length) {
			return finish("block result", "blocked", {
				note: `Result contained blocked terms (${outputViolations.join(", ")}) and was withheld.`,
			});
		}

		if (!worker.requireApproval) {
			return finish("deliver result", "completed", { output });
		}

		// 4. Nothing leaves without the owner's sign-off
		await step.do("submit for review", async () => {
			await center.updateTask(taskId, { status: "awaiting_approval", output });
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

		return finish(
			"record decision",
			decision.approved ? "approved" : "rejected",
			{ note: decision.note?.slice(0, 500) || null },
			"owner",
		);
	}
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
