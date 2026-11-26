"""Shared text-redaction helpers.

Strips ID-like tokens, emails, and file paths from free text before it
reaches a log entry or any other place a human might read it. Ported
from google-workspace-mcp's redaction module (same rationale: feedback
free-text fields can embed an identifier, email, or local path that has
no business leaving the machine).
"""

import re

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[A-Za-z]{2,}")
_PATH_RE = re.compile(r"(?:[A-Za-z]:)?(?:[\\/][\w.\-]+){2,}")
_LONG_TOKEN_RE = re.compile(r"\b[A-Za-z0-9_-]{20,}\b")


def redact(text: str | None, *, preserve: frozenset[str] | None = None) -> str | None:
    """Strip ID-like tokens, emails, and file paths from `text`.

    Only structural facts should survive: tool name, HTTP status,
    exception type, sanitized message -- never raw request args or
    document/case-law content.

    `preserve`: exact tokens that must survive the long-ID-token pass
    unredacted even though they match its length/shape (e.g. real MCP
    tool names, which are indistinguishable from a random ID by regex
    shape alone once they exceed the length threshold).
    """
    if not text:
        return text
    preserve = preserve or frozenset()
    text = _EMAIL_RE.sub("[redacted-email]", text)
    text = _PATH_RE.sub("[redacted-path]", text)
    text = _LONG_TOKEN_RE.sub(
        lambda m: m.group(0) if m.group(0) in preserve else "[redacted-id]", text
    )
    return text
