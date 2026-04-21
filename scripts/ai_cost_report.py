"""Aggregate AI cost/latency from Railway log output.

Usage (pipe logs via stdin)::

    railway logs --deployment | python scripts/ai_cost_report.py

Or against a saved file::

    python scripts/ai_cost_report.py --file railway.log

Reads every line, picks out the ones emitted by
``app.ai.observability.log_ai_call`` (matched by the literal ``ai_call``
token followed by a JSON object), and rolls them up by family and by
day. Output is a small human-readable table plus a JSON footer for
downstream piping.

Each input line looks like::

    2026-04-20 22:11:03,812 INFO scout.ai.observability: ai_call {"trace_id":"..","input_tokens":1234,..}

so the parser splits on the literal ``ai_call `` marker and decodes the
JSON remainder. Lines without the marker are ignored; malformed JSON is
counted and reported at the end so operators notice schema drift.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable


AI_CALL_RX = re.compile(r"ai_call\s+(?P<body>\{.*\})\s*$")


@dataclass
class Rollup:
    messages: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0

    def add(self, call: dict) -> None:
        self.messages += 1
        self.input_tokens += int(call.get("input_tokens") or 0)
        self.output_tokens += int(call.get("output_tokens") or 0)
        self.cost_usd += float(call.get("cost_usd") or 0.0)
        self.duration_ms += int(call.get("duration_ms") or 0)

    def as_dict(self) -> dict:
        return {
            "messages": self.messages,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": round(self.cost_usd, 6),
            "avg_duration_ms": (
                round(self.duration_ms / self.messages) if self.messages else 0
            ),
        }


@dataclass
class Report:
    by_family_day: dict[tuple[str, str], Rollup] = field(
        default_factory=lambda: defaultdict(Rollup)
    )
    by_tool: dict[str, Rollup] = field(default_factory=lambda: defaultdict(Rollup))
    total: Rollup = field(default_factory=Rollup)
    lines_seen: int = 0
    lines_matched: int = 0
    lines_malformed: int = 0


def parse_line(line: str) -> dict | None:
    m = AI_CALL_RX.search(line)
    if not m:
        return None
    try:
        return json.loads(m.group("body"))
    except json.JSONDecodeError:
        return {"__malformed__": True}


def day_of(ts: str | None) -> str:
    if not ts or not isinstance(ts, str) or len(ts) < 10:
        return "unknown"
    return ts[:10]


def build_report(lines: Iterable[str]) -> Report:
    report = Report()
    for line in lines:
        report.lines_seen += 1
        parsed = parse_line(line)
        if parsed is None:
            continue
        if parsed.get("__malformed__"):
            report.lines_malformed += 1
            continue
        report.lines_matched += 1
        family = parsed.get("family_id") or "unknown"
        day = day_of(parsed.get("event_ts"))
        report.by_family_day[(family, day)].add(parsed)
        tool = parsed.get("tool_name") or "(chat)"
        report.by_tool[tool].add(parsed)
        report.total.add(parsed)
    return report


def render(report: Report) -> str:
    lines: list[str] = []
    lines.append("=== AI Cost Report ===")
    lines.append(f"lines seen: {report.lines_seen}")
    lines.append(f"  matched: {report.lines_matched}")
    if report.lines_malformed:
        lines.append(f"  malformed: {report.lines_malformed}")
    lines.append("")
    lines.append("-- Total --")
    t = report.total.as_dict()
    lines.append(
        f"messages={t['messages']:>5}  input={t['input_tokens']:>8}  "
        f"output={t['output_tokens']:>8}  cost_usd=${t['cost_usd']:.4f}  "
        f"avg_ms={t['avg_duration_ms']:>5}"
    )
    lines.append("")

    if report.by_family_day:
        lines.append("-- By family + day (top 25 by cost) --")
        rows = sorted(
            report.by_family_day.items(),
            key=lambda kv: kv[1].cost_usd,
            reverse=True,
        )[:25]
        for (family, day), r in rows:
            d = r.as_dict()
            lines.append(
                f"  {day}  fam={family[:8]}…  "
                f"msgs={d['messages']:>4}  cost=${d['cost_usd']:.4f}  "
                f"in={d['input_tokens']:>7}  out={d['output_tokens']:>7}  "
                f"avg_ms={d['avg_duration_ms']:>5}"
            )
        lines.append("")

    if report.by_tool:
        lines.append("-- By tool --")
        rows = sorted(
            report.by_tool.items(),
            key=lambda kv: kv[1].cost_usd,
            reverse=True,
        )
        for tool, r in rows:
            d = r.as_dict()
            lines.append(
                f"  {tool:<28} msgs={d['messages']:>4}  cost=${d['cost_usd']:.4f}"
            )
        lines.append("")

    lines.append("-- JSON --")
    lines.append(
        json.dumps(
            {
                "total": report.total.as_dict(),
                "by_family_day": [
                    {"family_id": fam, "date": day, **r.as_dict()}
                    for (fam, day), r in report.by_family_day.items()
                ],
                "by_tool": [
                    {"tool_name": tool, **r.as_dict()}
                    for tool, r in report.by_tool.items()
                ],
                "lines_malformed": report.lines_malformed,
            },
            indent=2,
        )
    )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--file",
        help="Read log lines from this file instead of stdin",
    )
    args = ap.parse_args()

    if args.file:
        with open(args.file, "r", encoding="utf-8", errors="replace") as f:
            report = build_report(f)
    else:
        report = build_report(sys.stdin)

    print(render(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
