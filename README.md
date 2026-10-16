# Personal AI Command Center

A private control panel for **your own AI workers**. Only you can get in, only you can give orders, and every worker follows your rules.

Runs on Cloudflare Workers, using Workers AI, Workflows and Durable Objects.

## How it keeps workers yours

| Protection | What it does |
| --- | --- |
| **Owner lock** | Every API call needs your secret `OWNER_TOKEN`. If no token is set, everything stays locked. The live feed uses one-time 30-second tickets, so your token is never put in a URL. |
| **Your rules first** | Your global rules plus each worker's own rules become the worker's system prompt. Workers are told they serve only you, and that text inside a task (emails, web pages) is data, not orders. |
| **Blocked words** | Checked in code, not just requested from the AI. A task or result that contains a blocked word is stopped and never shown as output. |
| **Approval gate** | Workers set to "needs approval" pause until you approve or reject the result. |
| **Kill switch** | One click stops all running tasks and refuses new ones until you resume. |
| **Per-worker on/off** | Switch off any single worker. |
| **Audit log** | Every change, order, result and decision is recorded with a timestamp. |

## How a task runs

```
check orders  →  do the work (AI)  →  re-check rules  →  your review  →  done
   (kill switch,     (your rules as      (kill switch,     (approve /
    worker on,        system prompt)      blocked words     reject)
    blocked words)                        in the result)
```

Each task is a durable [Workflow](https://developers.cloudflare.com/workflows/), so it can wait up to 7 days for your review without losing its place.

## Setup

```bash
npm install
```

### Run locally

1. Copy `.dev.vars.example` to `.dev.vars` and set your own `OWNER_TOKEN` (16+ characters, e.g. from `openssl rand -hex 24`).
2. Log in to Cloudflare once with `npx wrangler login`. Workers AI always runs on Cloudflare, even in local dev.
3. Start it:

```bash
npm run dev
```

Open `http://localhost:5173` and unlock with your token.

### Deploy

```bash
npx wrangler secret put OWNER_TOKEN   # paste your private token
npm run deploy
```

Keep your token secret: anyone who has it can control your workers. To change it, run `wrangler secret put OWNER_TOKEN` again.

### Change the AI model

Set `AI_MODEL` in `wrangler.jsonc` to any [Workers AI text-generation model](https://developers.cloudflare.com/workers-ai/models/).

## Using it

1. **Your rules**: set your name, your global rules and any blocked words.
2. **Your AI workers**: create workers (for example "Researcher" or "Email drafter"), each with a role and its own rules.
3. **Give an order**: pick a worker and describe the task.
4. **Tasks**: watch it run live, then approve or reject the result.

## Tests

```bash
npm test
```

The tests cover the owner lock, the rules engine, the approval flow, blocked words, switched-off workers and AI failures. The AI step is mocked, so no Cloudflare login is needed to run them.

## Project layout

- `worker/auth.ts`: owner token check
- `worker/rules.ts`: system prompt builder and blocked-word checks
- `worker/command-center.ts`: Durable Object that stores settings, workers, tasks and the audit log, and serves the live feed
- `worker/agent-workflow.ts`: the workflow that runs one task
- `worker/index.ts`: API routes
- `src/`: React dashboard
