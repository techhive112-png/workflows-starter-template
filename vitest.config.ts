import { cloudflareTest } from "@cloudflare/vitest-pool-workers";
import { defineConfig } from "vitest/config";

// Must match OWNER_TOKEN in test/command-center.test.ts
const TEST_OWNER_TOKEN = "test-owner-token-1234567890";

export default defineConfig({
	plugins: [
		cloudflareTest({
			wrangler: { configPath: "./wrangler.jsonc" },
			// Tests mock the AI step, so no Cloudflare login is needed
			remoteBindings: false,
			miniflare: {
				bindings: { OWNER_TOKEN: TEST_OWNER_TOKEN },
			},
		}),
	],
});
