"""Optional language-model pass for recall (`--llm`). Token-frugal by design:

* only sentences the rules did NOT extract, and only plausible ones (obligation word
  or list item + a document-ish noun), are sent - never whole pages;
* many numbered, truncated sentences per request; the model returns only the
  numbers of the "yes" lines (structured JSON), so output is a few tokens;
* answers are cached on disk by sentence hash, so reruns cost nothing;
* the evidence quote is always the original sentence - the model cannot add text.

Sends document text to the Anthropic API: off unless the user passes --llm.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_MODEL = "claude-opus-5-5"
PROMPT_VERSION = "1"
BATCH = 80
MAX_CHARS = 300

SYSTEM = (
    "You review sentences from construction specifications. A sentence is YES when it requires the "
    "contractor (or its supplier) to deliver, submit, provide or furnish a document or item for "
    "acceptance/closeout: warranties or guarantees, O&M manuals, as-built/record drawings, spare parts, "
    "extra materials, attic stock, special tools, training, test reports/results/data, certificates, "
    "certifications, COA/COC, compliance documentation, or items listed as contents of such a deliverable. "
    "NO for construction methods, material properties, payment, legal clarifications ('shall not relieve'), "
    "notes to the designer/engineer, headings, references, and things the owner gives the contractor. "
    "Reply with the numbers of the YES lines only."
)
SCHEMA = {"type": "object", "properties": {"yes": {"type": "array", "items": {"type": "integer"}}},
          "required": ["yes"], "additionalProperties": False}

_OBLIG = re.compile(r"\b(?:shall|must|will|provide|submit|furnish|deliver|include)\b", re.I)
_LIST = re.compile(r"^(?:[a-z]|[A-Z]|\d{1,2})[.)]\s|^\(\w{1,3}\)\s")
_NOUN = re.compile(r"report|certif|warrant|guarant|manual|record|test|data|document|cop(?:y|ies)|spare|"
                   r"stock|tool|training|instruction|drawing|submittal|\bCO[AC]\b|list|log|plan|statement", re.I)


def is_candidate(span: str) -> bool:
    return 20 <= len(span) <= 1200 and bool(_NOUN.search(span)) and bool(_OBLIG.search(span) or _LIST.match(span))


@dataclass
class LlmStats:
    sent: int = 0
    cached: int = 0
    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    found: int = 0
    errors: list[str] = field(default_factory=list)


class Classifier:
    def __init__(self, model: str = DEFAULT_MODEL, cache_path: Path | None = None, client=None):
        self.model = model
        self.cache_path = cache_path
        self.cache: dict[str, bool] = {}
        if cache_path and cache_path.exists():
            self.cache = json.loads(cache_path.read_text(encoding="utf-8"))
        self.client = client
        self.stats = LlmStats()

    def _key(self, text: str) -> str:
        return hashlib.sha256(f"{self.model}|{PROMPT_VERSION}|{text}".encode()).hexdigest()[:24]

    def _ask(self, texts: list[str]) -> set[int]:
        import anthropic

        if self.client is None:
            from spectakeoff.keystore import load

            self.client = anthropic.Anthropic(api_key=load() or None)
        lines = "\n".join(f"{i}. {' '.join(t.split())[:MAX_CHARS]}" for i, t in enumerate(texts, 1))
        resp = self.client.messages.create(
            model=self.model, max_tokens=4096,
            system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
            messages=[{"role": "user", "content": lines}],
        )
        self.stats.requests += 1
        self.stats.input_tokens += resp.usage.input_tokens + (resp.usage.cache_read_input_tokens or 0)
        self.stats.output_tokens += resp.usage.output_tokens
        if resp.stop_reason == "refusal":
            raise RuntimeError("model refused the batch")
        text = next((b.text for b in resp.content if b.type == "text"), None)
        if text is None:
            raise RuntimeError(f"no text block (stop_reason={resp.stop_reason})")
        return {i for i in json.loads(text)["yes"] if 1 <= i <= len(texts)}

    def classify(self, texts: list[str]) -> list[bool]:
        import anthropic

        out: list[bool | None] = [self.cache.get(self._key(t)) for t in texts]
        self.stats.cached += sum(o is not None for o in out)
        todo = [i for i, o in enumerate(out) if o is None]
        for start in range(0, len(todo), BATCH):
            idx = todo[start:start + BATCH]
            try:
                yes = self._ask([texts[i] for i in idx])
            except (anthropic.APIError, RuntimeError, ValueError, KeyError) as exc:
                self.stats.errors.append(f"{type(exc).__name__}: {exc}"[:200])
                continue          # leave unanswered; rules-only result stands for these
            self.stats.sent += len(idx)
            for n, i in enumerate(idx, 1):
                out[i] = n in yes
                self.cache[self._key(texts[i])] = out[i]
        if self.cache_path:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps(self.cache), encoding="utf-8")
        result = [bool(o) for o in out]
        self.stats.found += sum(result)
        return result
