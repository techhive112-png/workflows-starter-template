"""`spectakeoff key`: store the user's Anthropic API key once, so --llm works without
environment variables. The key is typed/pasted into a hidden prompt, checked, and kept in a
file only the user can read. It is never printed, logged or written to a workbook."""
from __future__ import annotations

import os
import re
import stat
from pathlib import Path

KEY_FILE = Path(os.environ.get("SPECTAKEOFF_HOME", Path.home() / ".config" / "spectakeoff")) / "api_key"


def normalise(raw: str) -> str:
    """Undo what editors do to a pasted key: spaces, quotes, newlines, 'Sk-' autocapitalisation."""
    k = re.sub(r"\s+", "", raw).strip("\"'`")
    k = k.replace("‑", "-").replace("–", "-").replace("—", "-")
    return "s" + k[1:] if k[:3] == "Sk-" else k


def problem(key: str) -> str:
    """Latvian explanation of why the key cannot be a Console API key, or '' if the form is fine."""
    if not key:
        return "Atslēga ir tukša."
    if not key.startswith("sk-ant-"):
        return "Tā nav Anthropic atslēga (tai jāsākas ar sk-ant-api03-)."
    if not key.startswith("sk-ant-api"):
        return (f"Šī ir '{key[:10]}…' tipa atslēga, nevis API atslēga. Izveido to vietnē "
                "console.anthropic.com → API Keys → Create Key; tai jāsākas ar sk-ant-api03-.")
    return ""


def load() -> str:
    """Environment variable first, then the saved key."""
    env = os.environ.get("ANTHROPIC_API_KEY", "")
    if env:
        return env
    try:
        return KEY_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def save(key: str) -> Path:
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(KEY_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, stat.S_IRUSR | stat.S_IWUSR)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(key)
    os.chmod(KEY_FILE, stat.S_IRUSR | stat.S_IWUSR)
    return KEY_FILE


def remove() -> bool:
    try:
        KEY_FILE.unlink()
        return True
    except FileNotFoundError:
        return False


def verify(key: str, client=None) -> str:
    """One 1-token request (fractions of a cent). Returns '' if the key works, else the reason."""
    import anthropic

    try:
        c = client or anthropic.Anthropic(api_key=key, base_url="https://api.anthropic.com")
        c.messages.create(model="claude-haiku-5-5", max_tokens=1, messages=[{"role": "user", "content": "OK"}])
        return ""
    except anthropic.AuthenticationError:
        return "Anthropic noraidīja atslēgu (nederīga, izdzēsta vai beidzies termiņš)."
    except anthropic.PermissionDeniedError:
        return "Atslēgai nav atļaujas (pārbaudi kredītu un limitus Console → Billing)."
    except anthropic.APIError as exc:
        return f"Neizdevās pārbaudīt: {type(exc).__name__}"
