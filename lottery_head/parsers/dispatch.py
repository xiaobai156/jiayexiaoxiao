from __future__ import annotations

from .jiaye import (
    parse_jiaye_block_records,
    parse_jiaye_inline_records,
    parse_jiaye_plain_records,
)


# 字段名本身就是锚点，标记默认取 field。
FIELD_MARKER_HINTS = {
    "jiaye_block",
    "jiaye_inline",
}


KNOWN_PARSE_HINTS = {
    "jiaye_block",
    "jiaye_inline",
    "jiaye_plain",
}


DEDICATED_PARSE_HINTS = frozenset(KNOWN_PARSE_HINTS)


def has_dedicated_parser(hint: str) -> bool:
    return hint in DEDICATED_PARSE_HINTS


def resolve_marker(field: str, hint: str) -> str:
    return field if hint in FIELD_MARKER_HINTS else hint or field


def dispatch_specialized_head_records(
    *,
    fragment_html: str,
    text: str,
    compact: str,
    field: str,
    hint: str,
    target_period: str,
    anchor_marker: str,
    marker: str,
) -> tuple[bool, list[dict[str, str]]]:
    """家野值解析：三类提示全部走专用解析，证据不足一律不产记录。"""
    if hint == "jiaye_inline":
        return True, parse_jiaye_inline_records(compact, field, target_period)
    if hint == "jiaye_block":
        return True, parse_jiaye_block_records(text, field, target_period)
    if hint == "jiaye_plain":
        return True, parse_jiaye_plain_records(text, target_period)
    return False, []
