#!/usr/bin/env python3
"""Two numbers for one authorization gate: refusal and over-refusal, reported separately.

WHY TWO NUMBERS. A gate that stops everything has a perfect refusal rate and is useless;
a gate that stops nothing has a perfect over-refusal rate and is also useless. Collapsing
both into one "accuracy" figure hides which of the two failures you are buying. So this
eval prints them apart, and prints a third number that the first two hide:

  refusal rate        share of must-ask actions that were routed to a human
  over-refusal rate   share of benign actions that were routed to a human anyway
  rule coverage       share of must-ask actions caught by an EXPLICIT rule rather than
                      by the default-to-ask fallback

Rule coverage is the honest one. The classifier under test defaults to "ask" when nothing
matches, so a 100% refusal rate can be bought entirely by the default. The day someone
flips that default for latency or quota reasons, every must-ask action that was only ever
caught by the fallback silently becomes self-approved. Rule coverage measures how much of
the refusal rate would survive that change.

INPUT : evals/corpus.jsonl  -- {id, label: ask|self, cat, text}
        label semantics follow the gate's own class table: ask = classes D/E
        (human hands / money / irreversible delete / secrets to third parties / legal /
        mass-send), self = classes A/B/C (internal reversible / own content into own
        channels / short on-topic outbound).
UNDER TEST: evals/classifier.py -- vendored from github.com/tonydzi/agent-approval-gate
OUTPUT: stdout table + --json for machines. Exit 0 always on a clean run; the pass/fail
        thresholds live in test_red_first.py, not here, so this stays a measurement.

LABELS ARE AUTHOR-ASSIGNED. The corpus is written against the gate's published class table
by the person who wrote the gate. That is a real bias and it is named in evals/RESULTS.md
under "where this is blind". The corpus is not drawn from a third party and does not claim
to be a sample of anyone else's traffic.

RUN:  python3 evals/refusal_overrefusal.py
      python3 evals/refusal_overrefusal.py --json
      python3 evals/refusal_overrefusal.py --misses      # only the wrong verdicts
"""
from __future__ import annotations

import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import classifier  # noqa: E402  (vendored, sits next to this file)

CORPUS = os.path.join(HERE, "corpus.jsonl")


def load(path=CORPUS):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError as ex:
                raise SystemExit("corpus line %d is not JSON: %s" % (n, ex))
            for field in ("id", "label", "text"):
                if field not in r:
                    raise SystemExit("corpus line %d has no %r" % (n, field))
            if r["label"] not in ("ask", "self"):
                raise SystemExit("corpus line %d: label must be ask|self" % n)
            rows.append(r)
    if not rows:
        raise SystemExit("corpus is empty -- refusing to report a rate over zero items")
    return rows


def measure(rows):
    must_ask = [r for r in rows if r["label"] == "ask"]
    benign = [r for r in rows if r["label"] == "self"]
    per_item, by_cat = [], collections.defaultdict(lambda: [0, 0])

    asked_ok = rule_caught = 0
    for r in must_ask:
        klass, why = classifier.suggest_class(r["text"])
        asked = classifier.routes_to_human(klass)
        by_rule = asked and why.startswith("matched")
        asked_ok += bool(asked)
        rule_caught += bool(by_rule)
        by_cat[r.get("cat", "?")][0] += 1
        by_cat[r.get("cat", "?")][1] += bool(asked)
        per_item.append(dict(r, verdict=klass, why=why, routed="ask" if asked else "self",
                             correct=bool(asked), caught_by_rule=by_rule))

    over = 0
    for r in benign:
        klass, why = classifier.suggest_class(r["text"])
        asked = classifier.routes_to_human(klass)
        over += bool(asked)
        by_cat[r.get("cat", "?")][0] += 1
        by_cat[r.get("cat", "?")][1] += bool(not asked)
        per_item.append(dict(r, verdict=klass, why=why, routed="ask" if asked else "self",
                             correct=bool(not asked), caught_by_rule=False))

    def pct(a, b):
        return round(100.0 * a / b, 1) if b else None

    return {
        "corpus": {"total": len(rows), "must_ask": len(must_ask), "benign": len(benign)},
        "refusal_rate_pct": pct(asked_ok, len(must_ask)),
        "missed_must_ask": len(must_ask) - asked_ok,
        "rule_coverage_pct": pct(rule_caught, len(must_ask)),
        "default_catch_only": asked_ok - rule_caught,
        "over_refusal_rate_pct": pct(over, len(benign)),
        "over_refused": over,
        "default_class": classifier.DEFAULT_CLASS,
        "by_cat": {k: {"n": v[0], "correct": v[1], "pct": pct(v[1], v[0])}
                   for k, v in sorted(by_cat.items())},
        "items": per_item,
    }


def main(argv):
    rows = load()
    res = measure(rows)
    if "--json" in argv:
        out = dict(res)
        if "--items" not in argv:
            out.pop("items")
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    if "--misses" in argv:
        for it in res["items"]:
            if not it["correct"]:
                print("%-20s %-5s label=%-4s -> %s   %s"
                      % (it["id"], it["verdict"], it["label"], it["routed"], it["why"]))
        return 0

    c = res["corpus"]
    print("corpus: %d actions (%d must-ask, %d benign) | default class = %s"
          % (c["total"], c["must_ask"], c["benign"], res["default_class"]))
    print()
    print("  refusal rate       %5s%%   (%d of %d must-ask actions routed to a human; %d missed)"
          % (res["refusal_rate_pct"], c["must_ask"] - res["missed_must_ask"],
             c["must_ask"], res["missed_must_ask"]))
    print("  over-refusal rate  %5s%%   (%d of %d benign actions routed to a human anyway)"
          % (res["over_refusal_rate_pct"], res["over_refused"], c["benign"]))
    print("  rule coverage      %5s%%   (%d of %d must-ask caught by an explicit rule; "
          "%d only by the default)"
          % (res["rule_coverage_pct"], c["must_ask"] - res["default_catch_only"]
             - res["missed_must_ask"], c["must_ask"], res["default_catch_only"]))
    print()
    print("  per category (correct verdicts):")
    for cat, v in res["by_cat"].items():
        print("    %-16s %3d/%-3d  %5s%%" % (cat, v["correct"], v["n"], v["pct"]))
    print()
    print("  wrong verdicts: %d  ->  python3 %s --misses"
          % (sum(1 for i in res["items"] if not i["correct"]), os.path.basename(__file__)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
