/**
 * Optional secrets. Each one switches on extra abilities for your workers.
 * Set them in the Cloudflare dashboard: Worker -> Settings -> Variables and Secrets.
 */
interface Env {
	/** browserless.io API token - real browser for browsing and web search */
	BROWSERLESS_TOKEN?: string;
	/** Override the Browserless region, e.g. https://production-lon.browserless.io */
	BROWSERLESS_URL?: string;
	/** GitHub fine-grained token with Contents + Pull requests (read & write) */
	GITHUB_TOKEN?: string;
}
