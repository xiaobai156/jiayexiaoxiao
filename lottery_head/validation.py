from __future__ import annotations

import re


_PERIOD_INPUT_RE = re.compile(r"^\s*([1-9]\d{0,2})\s*(?:期|qi)?\s*$", re.IGNORECASE)
_JIAYE_RE = re.compile(r"^(?:家|野)(?:肖|禽|兽|獸)?$")

JIAYE_VALUES: tuple[str, str] = ("家", "野")

# 生肖归类：家禽＝牛马羊鸡狗猪；野兽＝鼠虎兔龙蛇猴。
ZODIAC_CLASS = {
    "牛": "家",
    "马": "家",
    "馬": "家",
    "羊": "家",
    "鸡": "家",
    "雞": "家",
    "狗": "家",
    "猪": "家",
    "豬": "家",
    "鼠": "野",
    "虎": "野",
    "兔": "野",
    "龙": "野",
    "龍": "野",
    "蛇": "野",
    "猴": "野",
}


def parse_target_period(value: str) -> str:
    """Accept only a complete user-entered period, never a substring from other text."""
    match = _PERIOD_INPUT_RE.fullmatch(value or "")
    if not match:
        raise ValueError("期数格式无效，只能输入1至3位期数，例如201或201期")
    return f"{int(match.group(1))}期"


def validate_value(value: str) -> str:
    """家野值只能是「家」或「野」；带肖/禽/兽后缀时归一成单字。"""
    raw = re.sub(r"[\s【】\[\]〖〗『』「」()（）]", "", value or "")
    match = _JIAYE_RE.fullmatch(raw)
    if not match:
        raise ValueError("家野值必须是「家」或「野」")
    return raw[0]
