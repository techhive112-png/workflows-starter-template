/**
 * GitHub tools. Workers may only touch repos the owner listed in their
 * settings, and they never change code directly: a change becomes a pull
 * request only after the owner presses Approve.
 */

import { normalizeRepo } from "./rules";

export interface CodeFile {
	path: string;
	/** New file content. Omit together with delete: true to remove a file. */
	content?: string;
	delete?: boolean;
}

export interface CodeProposal {
	repo: string;
	title: string;
	description: string;
	files: CodeFile[];
}

const MAX_FILES = 20;
const MAX_FILE_BYTES = 200_000;
const MAX_READ = 12_000;

export function checkRepo(value: unknown, allowed: string[]): string {
	const repo = typeof value === "string" ? normalizeRepo(value) : null;
	if (!repo) throw new Error(`Not a GitHub repo name: ${String(value)}`);
	if (!allowed.includes(repo)) {
		throw new Error(
			`The owner has not allowed ${repo}. Allowed repos: ${allowed.join(", ") || "(none)"}`,
		);
	}
	return repo;
}

function checkPath(value: unknown): string {
	if (typeof value !== "string") throw new Error("A file path is required");
	const path = value.trim().replace(/^\/+|\/+$/g, "");
	const parts = path.split("/");
	if (path && parts.some((p) => p === "" || p === "." || p === "..")) {
		throw new Error(`Invalid path: ${value}`);
	}
	if (parts[0] === ".git") throw new Error("The .git folder is off limits");
	return path;
}

/** Validate a proposal the AI produced before it is shown to the owner. */
export function checkProposal(raw: unknown, allowed: string[]): CodeProposal {
	const input = (raw && typeof raw === "object" ? raw : {}) as Record<
		string,
		unknown
	>;
	const repo = checkRepo(input.repo, allowed);
	const files = Array.isArray(input.files) ? input.files : [];
	if (!files.length) throw new Error("The code change has no files");
	if (files.length > MAX_FILES) {
		throw new Error(`Too many files (max ${MAX_FILES})`);
	}
	return {
		repo,
		title: String(input.title ?? "Changes from AI worker").slice(0, 120),
		description: String(input.description ?? "").slice(0, 4000),
		files: files.map((f): CodeFile => {
			const file = (f ?? {}) as Record<string, unknown>;
			const path = checkPath(file.path);
			if (!path) throw new Error("Each file needs a path");
			if (file.delete === true) return { path, delete: true };
			if (typeof file.content !== "string") {
				throw new Error(`File ${path} has no content`);
			}
			if (new TextEncoder().encode(file.content).byteLength > MAX_FILE_BYTES) {
				throw new Error(`File ${path} is too big`);
			}
			return { path, content: file.content };
		}),
	};
}

async function gh<T>(
	env: Env,
	path: string,
	init: RequestInit = {},
): Promise<T> {
	if (!env.GITHUB_TOKEN) {
		throw new Error("GitHub is not set up yet (GITHUB_TOKEN is missing).");
	}
	const res = await fetch(`https://api.github.com${path}`, {
		...init,
		headers: {
			Authorization: `Bearer ${env.GITHUB_TOKEN}`,
			Accept: "application/vnd.github+json",
			"X-GitHub-Api-Version": "2022-11-28",
			"User-Agent": "personal-ai-command-center",
			...(init.body ? { "Content-Type": "application/json" } : {}),
		},
		signal: AbortSignal.timeout(30_000),
	});
	if (!res.ok) {
		const detail = (await res.text()).slice(0, 300);
		throw new GitHubError(res.status, `GitHub HTTP ${res.status}: ${detail}`);
	}
	return (res.status === 204 ? null : await res.json()) as T;
}

class GitHubError extends Error {
	status: number;

	constructor(status: number, message: string) {
		super(message);
		this.status = status;
	}
}

const encodePath = (path: string) =>
	path.split("/").map(encodeURIComponent).join("/");

type ContentEntry = {
	type: string;
	path: string;
	sha: string;
	size: number;
	content?: string;
};

/** Read a file, or list a folder, in an allowed repo. */
export async function readRepo(
	env: Env,
	allowed: string[],
	rawRepo: unknown,
	rawPath: unknown,
): Promise<string> {
	const repo = checkRepo(rawRepo, allowed);
	const path = checkPath(rawPath ?? "");
	const entry = await gh<ContentEntry | ContentEntry[]>(
		env,
		`/repos/${repo}/contents/${encodePath(path)}`,
	);
	if (Array.isArray(entry)) {
		const list = entry
			.map((e) => `${e.type === "dir" ? "📁" : "📄"} ${e.path}`)
			.join("\n");
		return `Folder ${repo}/${path || ""}:\n${list}`;
	}
	if (entry.content === undefined) {
		return `${entry.path} is too large to read (${entry.size} bytes).`;
	}
	const text = decodeBase64(entry.content);
	const cut =
		text.length > MAX_READ ? `\n... (cut, ${text.length} chars total)` : "";
	return `File ${repo}/${entry.path}:\n${text.slice(0, MAX_READ)}${cut}`;
}

/** Turn an approved proposal into a branch, commits and a pull request. */
export async function openPullRequest(
	env: Env,
	allowed: string[],
	proposal: CodeProposal,
	branchName: string,
): Promise<string> {
	const repo = checkRepo(proposal.repo, allowed);
	const info = await gh<{ default_branch: string }>(env, `/repos/${repo}`);
	const base = info.default_branch;
	const ref = await gh<{ object: { sha: string } }>(
		env,
		`/repos/${repo}/git/ref/heads/${encodePath(base)}`,
	);

	try {
		await gh(env, `/repos/${repo}/git/refs`, {
			method: "POST",
			body: JSON.stringify({
				ref: `refs/heads/${branchName}`,
				sha: ref.object.sha,
			}),
		});
	} catch (err) {
		// 422 = branch already exists (a retry of this same step) - keep going
		if (!(err instanceof GitHubError && err.status === 422)) throw err;
	}

	for (const file of proposal.files) {
		const url = `/repos/${repo}/contents/${encodePath(file.path)}`;
		const existing = await gh<ContentEntry>(
			env,
			`${url}?ref=${encodeURIComponent(branchName)}`,
		).catch((err) => {
			if (err instanceof GitHubError && err.status === 404) return null;
			throw err;
		});

		if (file.delete) {
			if (!existing) continue;
			await gh(env, url, {
				method: "DELETE",
				body: JSON.stringify({
					message: `Delete ${file.path}`,
					sha: existing.sha,
					branch: branchName,
				}),
			});
			continue;
		}

		const content = encodeBase64(file.content ?? "");
		if (existing?.content?.replace(/\n/g, "") === content) continue;
		await gh(env, url, {
			method: "PUT",
			body: JSON.stringify({
				message: `${existing ? "Update" : "Add"} ${file.path}`,
				content,
				branch: branchName,
				...(existing ? { sha: existing.sha } : {}),
			}),
		});
	}

	const open = await gh<{ html_url: string }[]>(
		env,
		`/repos/${repo}/pulls?head=${encodeURIComponent(`${repo.split("/")[0]}:${branchName}`)}&state=open`,
	);
	if (open.length) return open[0].html_url;

	const pr = await gh<{ html_url: string }>(env, `/repos/${repo}/pulls`, {
		method: "POST",
		body: JSON.stringify({
			title: proposal.title,
			head: branchName,
			base,
			body: `${proposal.description}\n\n---\n_Prepared by an AI worker in your Command Center and approved by you._`,
		}),
	});
	return pr.html_url;
}

function encodeBase64(text: string): string {
	const bytes = new TextEncoder().encode(text);
	let binary = "";
	for (let i = 0; i < bytes.length; i += 0x8000) {
		binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
	}
	return btoa(binary);
}

function decodeBase64(b64: string): string {
	const binary = atob(b64.replace(/\n/g, ""));
	const bytes = Uint8Array.from(binary, (c) => c.charCodeAt(0));
	return new TextDecoder().decode(bytes);
}
