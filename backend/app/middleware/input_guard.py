"""Centralized input validation and sanitization for security-sensitive user inputs."""

import logging
import re

from app.middleware.error_handler import ValidationError

logger = logging.getLogger(__name__)

# --- Constants ---

MAX_CHAT_MESSAGE_LENGTH = 4000
MAX_COLLECTION_NAME_LENGTH = 100
MAX_FILENAME_LENGTH = 255

COLLECTION_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")

# SQL injection patterns in raw user text (chat messages).
# Structured patterns — require context (e.g. `;` prefix) so normal English isn't blocked.
_SQL_INJECTION_PATTERNS = [
    re.compile(r";\s*(DROP|ALTER|INSERT|UPDATE|DELETE|TRUNCATE|CREATE|GRANT|REVOKE)\b", re.IGNORECASE),
    re.compile(r"UNION\s+(ALL\s+)?SELECT\b", re.IGNORECASE),
    re.compile(r"'\s*OR\s+'[^']*'\s*=\s*'", re.IGNORECASE),
    re.compile(r"'\s*;\s*--", re.IGNORECASE),
    re.compile(r"/\*.*?\*/", re.DOTALL),
]

# Prompt injection patterns: attempts to override LLM system instructions.
_PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|above|prior)\s+(instructions?|prompts?|rules?)", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous|above|prior)\s+(instructions?|prompts?|rules?)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+", re.IGNORECASE),
    re.compile(r"new\s+instructions?:", re.IGNORECASE),
    re.compile(r"system\s*:\s*", re.IGNORECASE),
    re.compile(r"\[SYSTEM\]", re.IGNORECASE),
    re.compile(r"<\|?(system|im_start)\|?>", re.IGNORECASE),
    re.compile(r"IMPORTANT:\s*ignore", re.IGNORECASE),
    re.compile(r"override\s+(all\s+)?instructions?", re.IGNORECASE),
    re.compile(r"forget\s+(everything|all|prior|previous)", re.IGNORECASE),
    re.compile(r"act\s+as\s+(if\s+)?(you\s+are|a\s+different)", re.IGNORECASE),
    re.compile(r"do\s+not\s+follow\s+(your|the|any)\s+(rules?|instructions?)", re.IGNORECASE),
]

# Dangerous invisible/control characters to strip.
_DANGEROUS_CHARS_RE = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f"
    r"\u200b-\u200f\u2028-\u202f\u2060\ufeff]"
)


# --- Public API ---


def validate_chat_message(message: str) -> str:
    """Validate and sanitize a user chat message."""
    if len(message) > MAX_CHAT_MESSAGE_LENGTH:
        raise ValidationError(f"Message too long (max {MAX_CHAT_MESSAGE_LENGTH} characters)")

    message = _strip_dangerous_chars(message)
    if not message.strip():
        raise ValidationError("Message cannot be empty")

    _check_sql_injection(message, context="chat message")
    _check_prompt_injection(message, context="chat message")
    return message


def validate_collection_name(name: str) -> str:
    """Validate a collection name against the strict allowlist pattern."""
    name = name.strip()
    if not name or len(name) > MAX_COLLECTION_NAME_LENGTH:
        raise ValidationError(f"Collection name must be 1-{MAX_COLLECTION_NAME_LENGTH} characters")
    if not COLLECTION_NAME_RE.match(name):
        raise ValidationError(
            "Collection name must start with a lowercase letter "
            "and contain only lowercase letters, digits, and underscores"
        )
    return name


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename for safe use in metadata descriptions."""
    if not filename:
        return "unnamed_file"
    # Strip path components
    filename = filename.replace("\\", "/").rsplit("/", 1)[-1]
    # Remove dangerous/invisible characters
    filename = _DANGEROUS_CHARS_RE.sub("", filename)
    # Keep only safe chars
    filename = re.sub(r"[^\w.\-\s]", "_", filename)
    # Collapse multiple underscores/spaces
    filename = re.sub(r"[_\s]+", "_", filename).strip("_")
    if len(filename) > MAX_FILENAME_LENGTH:
        filename = filename[:MAX_FILENAME_LENGTH]
    return filename or "unnamed_file"


def sanitize_text_for_prompt(text: str, max_length: int = 500) -> str:
    """Sanitize user-controlled text before embedding in LLM prompts."""
    text = _strip_dangerous_chars(text)
    text = text.replace("<", "&lt;").replace(">", "&gt;")
    if len(text) > max_length:
        text = text[:max_length] + "..."
    return text


# --- Private helpers ---


def _strip_dangerous_chars(text: str) -> str:
    return _DANGEROUS_CHARS_RE.sub("", text)


def _check_sql_injection(text: str, context: str = "input") -> None:
    for pattern in _SQL_INJECTION_PATTERNS:
        if pattern.search(text):
            logger.warning("SQL injection pattern detected in %s: %r", context, text[:200])
            raise ValidationError("Input contains suspicious SQL patterns")


def _check_prompt_injection(text: str, context: str = "input") -> None:
    for pattern in _PROMPT_INJECTION_PATTERNS:
        if pattern.search(text):
            logger.warning("Prompt injection pattern detected in %s: %r", context, text[:200])
            raise ValidationError("Input contains suspicious instruction override patterns")
