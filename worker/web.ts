/**
 * Web tools: read a page, search the web, use a real browser (Browserless).
 *
 * The browser runs a fixed script written here. The AI only supplies data
 * (a URL and simple steps), never code, so it cannot run anything else.
 */

const MAX_TEXT = 6000;
const DEFAULT_BROWSERLESS_URL = "https://production-sfo.browserless.io";

export interface BrowserStep {
	click?: string;
	type?: { selector: string; text: string };
	press?: string;
	wait?: number;
}

export function checkUrl(value: unknown): string {
	if (typeof value !== "string") throw new Error("A URL is required");
	let url: URL;
	try {
		url = new URL(value.trim());
	} catch {
		throw new Error(`Not a valid URL: ${value}`);
	}
	if (url.protocol !== "https:" && url.protocol !== "http:") {
		throw new Error("Only http and https links are allowed");
	}
	return url.toString();
}

/** Turns HTML into readable plain text. */
export function htmlToText(html: string): string {
	return html
		.replace(/<(script|style|noscript|svg|head)[\s\S]*?<\/\1>/gi, " ")
		.replace(/<br\s*\/?>/gi, "\n")
		.replace(/<\/(p|div|li|h[1-6]|tr|section|article)>/gi, "\n")
		.replace(/<[^>]+>/g, " ")
		.replace(/&nbsp;/g, " ")
		.replace(/&amp;/g, "&")
		.replace(/&lt;/g, "<")
		.replace(/&gt;/g, ">")
		.replace(/&quot;/g, '"')
		.replace(/&#39;/g, "'")
		.replace(/[ \t]+/g, " ")
		.replace(/\n\s*\n+/g, "\n")
		.trim();
}

/** Fetch a page directly (fast, no JavaScript). */
export async function readPage(rawUrl: unknown): Promise<string> {
	const url = checkUrl(rawUrl);
	const res = await fetch(url, {
		headers: {
			"User-Agent": "Mozilla/5.0 (compatible; PersonalAICommandCenter/1.0)",
			Accept: "text/html,text/plain,application/json;q=0.9,*/*;q=0.5",
		},
		redirect: "follow",
		signal: AbortSignal.timeout(20_000),
	});
	if (!res.ok) throw new Error(`The page answered with HTTP ${res.status}`);
	const type = res.headers.get("Content-Type") ?? "";
	const body = await res.text();
	const text = type.includes("html") ? htmlToText(body) : body;
	return `Page: ${res.url}\n\n${text.slice(0, MAX_TEXT)}`;
}

const BROWSE_SCRIPT = `export default async ({ page, context }) => {
  const log = [];
  await page.goto(context.url, { waitUntil: "networkidle2", timeout: 30000 });
  for (const s of context.steps) {
    try {
      if (s.click) { await page.click(s.click); log.push("clicked " + s.click); }
      else if (s.type) { await page.type(s.type.selector, s.type.text); log.push("typed into " + s.type.selector); }
      else if (s.press) { await page.keyboard.press(s.press); log.push("pressed " + s.press); }
      else if (s.wait) { await new Promise((r) => setTimeout(r, s.wait)); }
      await new Promise((r) => setTimeout(r, 500));
    } catch (e) { log.push("step failed: " + e.message); }
  }
  const text = await page.evaluate(() => document.body ? document.body.innerText : "");
  return { data: { url: page.url(), title: await page.title(), text: text.slice(0, ${MAX_TEXT}), log }, type: "application/json" };
};`;

const SEARCH_SCRIPT = `export default async ({ page, context }) => {
  const q = encodeURIComponent(context.query);
  await page.goto("https://html.duckduckgo.com/html/?q=" + q, { waitUntil: "domcontentloaded", timeout: 30000 });
  let results = await page.$$eval(".result", (nodes) => nodes.slice(0, 8).map((n) => {
    const a = n.querySelector(".result__a");
    const s = n.querySelector(".result__snippet");
    return { title: a ? a.textContent.trim() : "", url: a ? a.href : "", snippet: s ? s.textContent.trim() : "" };
  }));
  if (!results.length) {
    await page.goto("https://www.bing.com/search?q=" + q, { waitUntil: "domcontentloaded", timeout: 30000 });
    results = await page.$$eval("li.b_algo", (nodes) => nodes.slice(0, 8).map((n) => {
      const a = n.querySelector("h2 a");
      const s = n.querySelector(".b_caption p");
      return { title: a ? a.textContent.trim() : "", url: a ? a.href : "", snippet: s ? s.textContent.trim() : "" };
    }));
  }
  return { data: { results }, type: "application/json" };
};`;

async function runBrowser<T>(
	env: Env,
	code: string,
	context: Record<string, unknown>,
): Promise<T> {
	if (!env.BROWSERLESS_TOKEN) {
		throw new Error(
			"The browser is not set up yet (BROWSERLESS_TOKEN is missing).",
		);
	}
	const base = (env.BROWSERLESS_URL || DEFAULT_BROWSERLESS_URL).replace(
		/\/+$/,
		"",
	);
	const endpoint = `${base}/function?token=${encodeURIComponent(env.BROWSERLESS_TOKEN)}`;
	const res = await fetch(endpoint, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({ code, context }),
		signal: AbortSignal.timeout(60_000),
	});
	if (!res.ok) {
		const detail = (await res.text()).slice(0, 300);
		throw new Error(`Browser error (HTTP ${res.status}): ${detail}`);
	}
	const body = (await res.json()) as { data?: T } & T;
	return (body.data ?? body) as T;
}

/** Open a page in a real browser; optionally click and type first. */
export async function browse(
	env: Env,
	rawUrl: unknown,
	rawSteps: unknown,
	allowActions: boolean,
): Promise<string> {
	const url = checkUrl(rawUrl);
	const steps = cleanSteps(rawSteps);
	if (steps.length && !allowActions) {
		throw new Error(
			"This worker may only look at pages, not click or type. The owner can allow it in the worker settings.",
		);
	}
	const result = await runBrowser<{
		url: string;
		title: string;
		text: string;
		log: string[];
	}>(env, BROWSE_SCRIPT, { url, steps });
	return [
		`Page: ${result.url}`,
		`Title: ${result.title}`,
		result.log?.length ? `Actions: ${result.log.join("; ")}` : "",
		"",
		result.text,
	]
		.filter((line) => line !== "")
		.join("\n");
}

export async function webSearch(env: Env, rawQuery: unknown): Promise<string> {
	const query = typeof rawQuery === "string" ? rawQuery.trim() : "";
	if (!query) throw new Error("A search query is required");
	const { results } = await runBrowser<{
		results: { title: string; url: string; snippet: string }[];
	}>(env, SEARCH_SCRIPT, { query: query.slice(0, 300) });
	if (!results?.length) return `No results for "${query}".`;
	return results
		.filter((r) => r.url)
		.map((r, i) => `${i + 1}. ${r.title}\n   ${r.url}\n   ${r.snippet}`)
		.join("\n");
}

function cleanSteps(value: unknown): BrowserStep[] {
	if (!Array.isArray(value)) return [];
	return value.slice(0, 10).flatMap((s): BrowserStep[] => {
		if (!s || typeof s !== "object") return [];
		const step = s as Record<string, unknown>;
		if (typeof step.click === "string") return [{ click: step.click }];
		if (typeof step.press === "string") return [{ press: step.press }];
		if (typeof step.wait === "number") {
			return [{ wait: Math.max(0, Math.min(step.wait, 5000)) }];
		}
		const type = step.type as Record<string, unknown> | undefined;
		if (
			type &&
			typeof type.selector === "string" &&
			typeof type.text === "string"
		) {
			return [
				{ type: { selector: type.selector, text: type.text.slice(0, 500) } },
			];
		}
		return [];
	});
}
