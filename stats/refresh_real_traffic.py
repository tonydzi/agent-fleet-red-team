#!/usr/bin/env python3
"""Regenerate stats/real-traffic.json from the authorization gate's own counter.

WHY IT IS A SEPARATE SCRIPT. Every other number in this repository can be recomputed
anywhere: the evals are deterministic, the GitHub figures are public, the fleet routine
counts come from a synced registry. The production gate figure cannot — it lives in the
sqlite journal of the node that holds the gate. So the weekly routine on any other node
*carries it over with its date* instead of inventing it, and this script is what the gate
node runs to refresh it.

RUN (on the node that holds the gate journal):
    python3 approval_gate.py metrics 90 | python3 stats/refresh_real_traffic.py --window 90
    # or, with the fleet's own wrapper:
    python3 approval.py stats 90       | python3 stats/refresh_real_traffic.py --window 90

It REFUSES to write when a field is missing. A partially parsed report would publish a
silent zero, and a zero is indistinguishable from "safe" on a dashboard.

    --dry-run   parse and print, write nothing
    --node NAME label for the measuring node (default: "gate node"; do not pass a hostname,
                this file is public)
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent / "real-traffic.json"

READING = [
    "Counts in by_category are FLOORS, not totals: the category field is optional at the "
    "call site, so whatever sits in the catch-all bucket is uncategorised traffic rather "
    "than a safety result.",
    "Asks cut by the open-request cap are deliberate backpressure, but a cut ask is work "
    "the agent did not do, not work it did safely.",
    "Asks that expired unanswered are the sharpest number here: they are questions that "
    "reached a human and never got a decision.",
]


def parse(text):
    """Pull the figures out of the gate's report. Returns (data, missing_fields)."""
    out, missing = {}, []

    m = re.search(r"(?:gate firings|human_touches[^:]*)\D{0,40}?(\d+)\s*(?:over\s*(\d+)\s*d)?",
                  text, re.I)
    if m:
        out["tier2_firings"] = int(m.group(1))
        if m.group(2):
            out["window_days"] = int(m.group(2))
    else:
        missing.append("tier2_firings")

    m = re.search(r"([\d.]+)\s*/\s*day", text, re.I)
    if m:
        out["per_day_avg"] = float(m.group(1))
    m = re.search(r"([\d.]+)\s*/\s*active-day", text, re.I)
    if m:
        out["per_active_day_avg"] = float(m.group(1))

    m = re.search(r"by category:\s*(.+)", text, re.I)
    if m:
        cats = {}
        for part in m.group(1).split(","):
            kv = part.strip().split("=")
            if len(kv) == 2 and kv[1].strip().isdigit():
                cats[kv[0].strip()] = int(kv[1].strip())
        if cats:
            out["by_category"] = cats
        else:
            missing.append("by_category")
    else:
        missing.append("by_category")

    # Backpressure line: "cut by the cap" then "expired unanswered". Language-agnostic on
    # purpose, because the wrapper that prints it is not necessarily in English.
    #
    # The first version of this read the first two integers on the line and got BOTH wrong
    # on the first real report: "backpressure за 90d: срезано капом 146 · протухло по 14д 0"
    # yielded 90 and 146 instead of 146 and 0, i.e. it published a window length as a count.
    # Durations are therefore dropped first: any number glued to a day marker is a window,
    # not a measurement.
    line = re.search(r"backpressure[^\n]*", text, re.I)
    if line:
        cleaned = re.sub(r"\d+\s*(?:d\b|д\b|days?\b|дн\w*)", " ", line.group(0), flags=re.I)
        nums = re.findall(r"\d+", cleaned)
        if len(nums) >= 2:
            out["cut_by_open_cap"], out["expired_unanswered"] = int(nums[0]), int(nums[1])
        else:
            missing.append("cut_by_open_cap / expired_unanswered (line found, %d numbers "
                           "left after dropping durations)" % len(nums))
    else:
        missing.append("cut_by_open_cap / expired_unanswered (no backpressure line)")

    return out, missing


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", type=int, default=None,
                    help="window in days, if the report does not state it")
    ap.add_argument("--node", default="gate node")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    text = sys.stdin.read()
    if not text.strip():
        print("nothing on stdin -- pipe the gate's metrics report in", file=sys.stderr)
        return 2

    data, missing = parse(text)
    if a.window and "window_days" not in data:
        data["window_days"] = a.window
    if "window_days" not in data:
        missing.append("window_days")

    if missing:
        print("REFUSING to write: could not parse %s" % ", ".join(missing), file=sys.stderr)
        print("parsed so far: %s" % json.dumps(data, ensure_ascii=False), file=sys.stderr)
        return 1

    cats = data.get("by_category", {})
    biggest = max(cats, key=cats.get) if cats else None
    doc = {
        "_what": ("Production authorization-gate firings from the fleet's own journal. "
                  "Measured on the node that holds the journal; every other node reads this "
                  "file rather than guessing. Regenerate with stats/refresh_real_traffic.py."),
        "_how": "the gate's own counter (metrics/stats subcommand) over the stated window",
        "measured_on": datetime.date.today().isoformat(),
        "measured_by_node": a.node,
    }
    doc.update(data)
    reading = list(READING)
    if biggest and cats[biggest] > 0.5 * data["tier2_firings"]:
        reading.insert(0, "%d of %d firings (%.0f%%) landed in the '%s' bucket, so the "
                          "per-category counts below are floors, not totals."
                       % (cats[biggest], data["tier2_firings"],
                          100.0 * cats[biggest] / data["tier2_firings"], biggest))
    doc["_reading_it_honestly"] = reading

    rendered = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
    if a.dry_run:
        print(rendered)
        return 0
    OUT.write_text(rendered, encoding="utf-8")
    print("wrote %s: %d firings over %dd, %d expired unanswered"
          % (OUT.name, doc["tier2_firings"], doc["window_days"], doc["expired_unanswered"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
