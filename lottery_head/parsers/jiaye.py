from __future__ import annotations

import re

from ..validation import ZODIAC_CLASS
from .common import unique_extracted_records

_OPEN_CHARS = "【[〖『「〔《〈(（‖〓"
_CLOSE_CHARS = "】]〗』」〕》〉)）‖〓"
_OPEN = re.escape(_OPEN_CHARS)
_CLOSE = re.escape(_CLOSE_CHARS)

# 一个括号片段：[【...】]，内容允许夹带生肖（家禽+猴鼠 这种只取“家禽”）。
_BRACKET_SEGMENT_RE = re.compile(rf"[{_OPEN}]([^{_CLOSE}]{{0,40}})[{_CLOSE}]")
# 片段内的类别词：完整类别词才认；单字 家/野 只认整格就是「家」「野」的情况
# （【六合之家】【野马归途】这种是标题，不是答案）。
_CLASS_IN_SEGMENT_RE = re.compile(r"家禽|家畜|家肖|野兽|野獸|野肖")
_CJK_ONLY_RE = re.compile(r"[^\u4e00-\u9fff]")
# 裸写的类别词，只在没有任何括号片段时兜底。
_BARE_TOKEN_RE = re.compile(r"家禽|家畜|野兽|野獸|野肖|家肖")

_CLASS_WORD = {
    "家禽": "家",
    "家畜": "家",
    "家肖": "家",
    "野兽": "野",
    "野獸": "野",
    "野肖": "野",
    "家": "家",
    "野": "野",
}

_PERIOD_RE = re.compile(r"(?<!\d)(\d{2,3})期")
# 开奖位标记：真正的数据行一定带「开:0000准」，没有它的多是把期号写进广告标题。
_OPEN_MARK_RE = re.compile(r"[开開]")
_ZODIAC_RE = re.compile(r"[鼠牛馬马虎虎兔龙龍蛇猴鸡雞狗猪豬羊]")

# 栏目标题：本身就同时含“家禽”“野兽”，必须先剔除，否则被当成两个答案。
_HEADER_RE = re.compile(
    r"野兽\s*[与和及]?\s*(?:家禽|家畜)\s*稳?"
    r"|(?:家禽|家畜)\s*[与和及]?\s*野兽\s*稳?"
    r"|家野\s*[⑵2]肖|家野\s*两肖"
)
# 分类定义表：家禽:牛马羊鸡狗猪 / 野兽----鼠虎兔龙蛇猴。
_LEGEND_RE = re.compile(
    r"^\s*(?:家禽|家畜|野兽|野獸|野肖|家肖)\s*[:：\-—=＝]{1,4}[^\n]*[鼠牛馬马虎虎兔龙龍蛇猴鸡雞狗猪豬羊]"
)

def _strip_headers(text: str) -> str:
    return _HEADER_RE.sub(" ", text)

# 栏目名在页面上有几种写法，配置里只能写一种，命中任意一种都算本文档的栏目标记。
_MARKER_ALIASES = (
    "家野",
    "家禽野兽",
    "野兽家禽",
    "家畜野兽",
    "野兽家畜",
    "家禽",
    "野兽",
)


def _has_marker(text: str, marker: str) -> bool:
    if not marker:
        return True
    if marker in text:
        return True
    # 只有家野家族的栏目名才放宽到同义写法，其他字段仍严格匹配。
    if marker in _MARKER_ALIASES:
        return any(alias in text for alias in _MARKER_ALIASES)
    return False


def _is_legend_row(row: str) -> bool:
    return bool(_LEGEND_RE.match(row))


def jiaye_labels(text: str) -> list[str]:
    """Return every 家/野 label found in text, in order of appearance.

    括号里跟着生肖（家禽+猴鼠、野兽+牛马）不影响判定：生肖只是陪衬，
    只看类别词本身就是家还是野。
    """
    cleaned = _strip_headers(text)
    labels: list[str] = []
    for segment in _BRACKET_SEGMENT_RE.finditer(cleaned):
        inner = segment.group(1)
        core = _CJK_ONLY_RE.sub("", inner)
        if core in ("家", "野"):
            labels.append(core)
            continue
        for match in _CLASS_IN_SEGMENT_RE.finditer(inner):
            labels.append(_CLASS_WORD[match.group(0)])
    if not labels:
        for match in _BARE_TOKEN_RE.finditer(cleaned):
            labels.append(_CLASS_WORD[match.group(0)])
    return labels


def single_jiaye_label(text: str) -> str:
    """一个块里必须只指向同一个类别，同时出现家与野才返回空串。"""
    labels = set(jiaye_labels(text))
    if len(labels) == 1:
        return labels.pop()
    return ""


def _row_is_noise(row: str) -> bool:
    return _is_legend_row(row) or not row.strip()


def _blocks(text: str, max_rows: int = 9) -> list[list[str]]:
    rows = [row.strip() for row in text.splitlines() if not _row_is_noise(row)]
    blocks: list[list[str]] = []
    current: list[str] | None = None
    for row in rows:
        if _PERIOD_RE.search(row):
            if current:
                blocks.append(current)
            current = [row]
            continue
        if current is not None and len(current) < max_rows:
            current.append(row)
    if current:
        blocks.append(current)
    return blocks


def _segments(compact: str) -> list[tuple[str, str]]:
    """把压平成一行的正文按“期号”切成 (期数, 该期文本) 片段。"""
    cleaned = _strip_headers(compact)
    segments: list[tuple[str, str]] = []
    matches = list(_PERIOD_RE.finditer(cleaned))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(cleaned)
        segments.append((f"{match.group(1)}期", cleaned[match.start():end]))
    return segments


def parse_jiaye_block_records(
    text: str,
    field: str = "",
    target_period: str = "",
) -> list[dict[str, str]]:
    """按“期号开头 + 同块内类别标记”的方式抽取家野记录。

    期号与类别值经常分行显示（「316期:」/「【家禽野兽】」/「【家禽】开:？00准」），
    因此先把相邻若干行合并成块再判断。
    """
    records: list[dict[str, str]] = []
    marker = _strip_headers((field or "").strip())
    for rows in _blocks(text):
        joined = " ".join(rows)
        period = f"{_PERIOD_RE.search(rows[0]).group(1)}期"
        if target_period and period != target_period:
            continue
        if not _has_marker(joined, marker):
            continue
        label = single_jiaye_label(joined)
        if not label:
            continue
        records.append({"period": period, "value": label, "raw_line": joined[:200]})
    return unique_extracted_records(records)


def parse_jiaye_inline_records(
    compact: str,
    field: str = "",
    target_period: str = "",
) -> list[dict[str, str]]:
    """压平正文里逐段匹配：期号到下一个期号之间必须只出现一个类别。"""
    records: list[dict[str, str]] = []
    marker = _strip_headers((field or "").strip())
    for period, segment in _segments(compact):
        if target_period and period != target_period:
            continue
        if not _has_marker(segment, marker):
            continue
        label = single_jiaye_label(segment)
        if not label:
            continue
        records.append({"period": period, "value": label, "raw_line": segment[:200]})
    return unique_extracted_records(records)


def parse_jiaye_plain_records(
    text: str,
    target_period: str = "",
) -> list[dict[str, str]]:
    """页面上没有固定字段名：只要求块内类别唯一。"""
    return parse_jiaye_block_records(text, "", target_period)
