import { env, introspectWorkflowInstance } from "cloudflare:test";
import { exports } from "cloudflare:workers";
import { describe, it, expect } from "vitest";
import {
	buildSystemPrompt,
	findViolations,
	DEFAULT_SETTINGS,
} from "../worker/rules";
import { OWNER_CENTER } from "../worker/agent-workflow";

// Must match the OWNER_TOKEN binding in vitest.config.ts
const OWNER_TOKEN = "test-owner-token-1234567890";

const center = () =>
	env.COMMAND_CENTER.get(env.COMMAND_CENTER.idFromName(OWNER_CENTER));

const api = (path: string, init: RequestInit = {}, token = OWNER_TOKEN) =>
	exports.default.fetch(
		new Request(`https://example.com${path}`, {
			...init,
			headers: {
				"Content-Type": "application/json",
				...(token ? { Authorization: `Bearer ${token}` } : {}),
			},
		}),
	);

describe("owner lock", () => {
	it("rejects requests without the owner token", async () => {
		const res = await api("/api/state", {}, "");
		expect(res.status).toBe(401);
	});

	it("rejects a wrong token", async () => {
		const res = await api("/api/state", {}, "someone-else-guessing-1234");
		expect(res.status).toBe(401);
	});

	it("lets the owner in", async () => {
		const res = await api("/api/state");
		expect(res.status).toBe(200);
		const state = (await res.json()) as { settings: { killSwitch: boolean } };
		expect(state.settings.killSwitch).toBe(false);
	});

	it("refuses the live feed without a valid ticket", async () => {
		const res = await exports.default.fetch(
			new Request("https://example.com/ws?ticket=made-up", {
				headers: { Upgrade: "websocket" },
			}),
		);
		expect(res.status).toBe(401);
	});

	it("refuses new tasks while the kill switch is on", async () => {
		const worker = await center().createWorker({ name: "Writer" });
		await api("/api/settings", {
			method: "PUT",
			body: JSON.stringify({ killSwitch: true }),
		});
		const res = await api("/api/tasks", {
			method: "POST",
			body: JSON.stringify({
				workerId: worker.id,
				instruction: "Write a poem",
			}),
		});
		expect(res.status).toBe(409);
		await center().updateSettings({ killSwitch: false });
	});
});

describe("rules", () => {
	it("puts the owner and all rules into the system prompt", () => {
		const prompt = buildSystemPrompt(
			{ ...DEFAULT_SETTINGS, ownerName: "Sam", globalRules: ["Be brief."] },
			{
				id: "1",
				name: "Scout",
				role: "Research assistant",
				rules: ["Cite sources."],
				enabled: true,
				requireApproval: true,
				createdAt: 0,
			},
		);
		expect(prompt).toContain("serves exactly one person: Sam");
		expect(prompt).toContain("1. Be brief.");
		expect(prompt).toContain("1. Cite sources.");
	});

	it("finds blocked terms regardless of case", () => {
		expect(
			findViolations("Send my PASSWORD now", ["password", "bank"]),
		).toEqual(["password"]);
		expect(findViolations("all good", ["password"])).toEqual([]);
	});
});

describe("AgentTaskWorkflow", () => {
	it("waits for the owner's approval before finishing", async () => {
		const worker = await center().createWorker({
			name: "Helper",
			requireApproval: true,
		});
		const task = await center().createTask(worker.id, "Draft a thank-you note");

		await using instance = await introspectWorkflowInstance(
			env.AGENT_TASK,
			task.id,
		);
		await instance.modify(async (m) => {
			await m.mockStepResult({ name: "do the work" }, "Thank you so much!");
			await m.mockEvent({
				type: "owner-decision",
				payload: { approved: true },
			});
		});

		await env.AGENT_TASK.create({ id: task.id, params: { taskId: task.id } });
		await instance.waitForStatus("complete");

		const done = await center().getTask(task.id);
		expect(done?.status).toBe("approved");
		expect(done?.output).toBe("Thank you so much!");
	});

	it("blocks tasks for a switched-off worker", async () => {
		const worker = await center().createWorker({
			name: "Sleeper",
			enabled: false,
		});
		const task = await center().createTask(worker.id, "Do something");

		await using instance = await introspectWorkflowInstance(
			env.AGENT_TASK,
			task.id,
		);
		await env.AGENT_TASK.create({ id: task.id, params: { taskId: task.id } });
		await instance.waitForStatus("complete");

		expect((await center().getTask(task.id))?.status).toBe("blocked");
	});

	it("withholds results that contain blocked terms", async () => {
		await center().updateSettings({ blockedTerms: ["secret code"] });
		const worker = await center().createWorker({
			name: "Talker",
			requireApproval: false,
		});
		const task = await center().createTask(worker.id, "Say hi");

		await using instance = await introspectWorkflowInstance(
			env.AGENT_TASK,
			task.id,
		);
		await instance.modify(async (m) => {
			await m.mockStepResult({ name: "do the work" }, "The secret code is 42");
		});
		await env.AGENT_TASK.create({ id: task.id, params: { taskId: task.id } });
		await instance.waitForStatus("complete");

		const done = await center().getTask(task.id);
		expect(done?.status).toBe("blocked");
		expect(done?.output).toBeNull();
	});
});

describe("AgentTaskWorkflow failures", () => {
	it("marks the task failed when the AI keeps erroring", async () => {
		const worker = await center().createWorker({ name: "Flaky" });
		const task = await center().createTask(worker.id, "Summarise my week");

		await using instance = await introspectWorkflowInstance(
			env.AGENT_TASK,
			task.id,
		);
		await instance.modify(async (m) => {
			await m.disableRetryDelays();
			await m.mockStepError(
				{ name: "do the work" },
				new Error("model offline"),
				3,
			);
		});
		await env.AGENT_TASK.create({ id: task.id, params: { taskId: task.id } });
		await instance.waitForStatus("complete");

		const done = await center().getTask(task.id);
		expect(done?.status).toBe("failed");
		expect(done?.note).toContain("model offline");
	});
});
