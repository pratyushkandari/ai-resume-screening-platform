"""Small text helpers for user-entered fields."""

import re

_SCRIPT_STYLE = re.compile(r"<(script|style)\b.*?>.*?</\1\s*>", re.IGNORECASE | re.DOTALL)
# Only real tags (<b>, </p>, <br/>, <a href=...>), so text such as "<50k and >20k" survives.
_TAG = re.compile(r"</?[A-Za-z][A-Za-z0-9-]*(?:\s[^<>]*)?/?>")
_SPACES = re.compile(r"[ \t]+")


def clean_text(value: str) -> str:
    """Strip HTML tags/scripts and collapse runs of spaces.

    React escapes output anyway; this keeps stored names and job text tidy.
    """
    if not value:
        return ""
    value = _TAG.sub("", _SCRIPT_STYLE.sub("", value))
    return "\n".join(_SPACES.sub(" ", line).strip() for line in value.strip().splitlines()).strip()
