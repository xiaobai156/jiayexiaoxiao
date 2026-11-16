# -*- coding: utf-8 -*-
"""从近10期缓存重建指定期的成功 TXT（不联网、不抓取）。身份按规范化 identity 匹配。"""
from __future__ import annotations

import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lottery_head.cache_payload import _identity_payload
from lottery_head.cache_validation import read_validated_cache
from lottery_head.config import load_rules
from lottery_head.models import HeadRecord
from lottery_head.output_text import format_success_txt
from lottery_head.settings import RECENT_10_CACHE_PATH, SUMMARY_DIR

USAGE = "用法：python scripts/rebuild_period_txt.py {期数}期 [--yes]"

if len(sys.argv) < 2:
    print(USAGE)
    raise SystemExit(2)
PERIOD = sys.argv[1].strip()
if not PERIOD:
    print(USAGE)
    raise SystemExit(2)
CONFIRM = "--yes" in sys.argv[2:]

rules = load_rules()
snap = read_validated_cache(RECENT_10_CACHE_PATH, rules)
if PERIOD not in snap["periods"]:
    print(f"停止：{PERIOD} 不在缓存窗口 {snap['periods']}")
    raise SystemExit(2)


def key_of(identity: dict) -> tuple:
    return (
        identity["section"].strip(),
        identity["url"].strip(),
        identity["position"].strip(),
        identity["parse_hint"].strip(),
    )


by_key = {key_of(e["identity"]): e for e in snap["sites"]}
records: list[HeadRecord] = []
unmatched: list[str] = []
no_value: list[str] = []
for rule in rules:
    e = by_key.get(key_of(_identity_payload(rule)))
    if e is None:
        unmatched.append(rule.section)
        continue
    value = e["values"].get(PERIOD)
    if not value:
        no_value.append(rule.section)
        continue
    prov = e["provenance"].get(PERIOD, {})
    records.append(
        HeadRecord(
            url=rule.url,
            position=rule.position,
            section=rule.section,
            field=rule.field,
            period=PERIOD,
            value=value,
            raw_line=prov.get("raw_line", ""),
            status="success",
            error="",
            original_position=e["positions"].get(PERIOD, 0),
            source_route=prov.get("route", ""),
            source_url=prov.get("source_url", ""),
            parse_hint=rule.parse_hint,
        )
    )

text = format_success_txt(records, PERIOD)

# 先把表头和排行核完，任何时候都不允许"写坏了再发现"。
lines = text.splitlines()
markers = [i for i, line in enumerate(lines) if line.startswith("内容\t次数\t排名")]
if len(markers) != 1:
    print(f"停止：生成的 TXT 排行表头异常（命中 {len(markers)} 处），未写任何文件")
    raise SystemExit(1)
mi = markers[0]
station_lines = [line for line in lines[:mi] if line.strip()]
values = [line.split(" ")[0] for line in station_lines]
rank = {r.split("\t")[0]: int(r.split("\t")[1]) for r in lines[mi + 1:] if r.strip()}
if dict(Counter(values)) != rank:
    print("停止：站点值与排行统计不一致，未写任何文件")
    raise SystemExit(1)

out = Path(SUMMARY_DIR) / f"{PERIOD}-家野.txt"
before = out.read_bytes() if out.exists() else None
payload = text.encode("utf-8")
if before != payload:
    old_lines = set(before.decode("utf-8-sig", "ignore").splitlines()) if before else set()
    new_lines = set(text.splitlines())
    added = len(new_lines - old_lines)
    removed = len(old_lines - new_lines)
    print(f"预览：{out}")
    print(f"  现有 {len(old_lines)} 行 → 新 {len(new_lines)} 行（+{added} / -{removed}），站点行 {len(station_lines)} 条")
    print(f"  排行 {rank} | 合计 {sum(rank.values())}")
    if not CONFIRM:
        print("未写入。确认覆盖请加 --yes 重跑。")
        raise SystemExit(1)

if before != payload:
    tmp = out.with_name(f".{out.name}.tmp")
    tmp.write_bytes(payload)
    os.replace(tmp, out)

print(f"缓存 {len(snap['sites'])} 站 | {PERIOD} 取值 {len(records)} 站")
print(f"未匹配 {len(unmatched)}: {unmatched}")
print(f"该期无值 {len(no_value)}: {no_value}")
print(f"写出: {out} | {out.stat().st_size}B | 站点行 {len(station_lines)}")
print(f"排行: {rank} | 合计 {sum(rank.values())} | 逐项一致 True")
print("首3行:", station_lines[:3])
print("末3行:", station_lines[-3:])
