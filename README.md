# agent-fleet-red-team

**I run a production multi-agent fleet with my real credentials in it, and I attack it on
purpose.** This repository is the written-down half of that work: the threat model, the
standards mapping with exact identifiers, the measured failure rates of my own
authorization gate, and a public write-up of an injection chain with its consequences.

Everything here is about my own system. No third-party infrastructure was tested.

Author: Anton Dziatkovskii — MSc in Computer & Information Systems Security (cryptography);
Python and C++; hired operating executive (COO/CTO) by day for eleven years, hands-on IC on
this work. [github.com/tonydzi](https://github.com/tonydzi) ·
[tonydzi.github.io](https://tonydzi.github.io/) · US O-1 and EU (Polish) citizenship, no
sponsorship needed.

---

## Start here

| if you want | read |
|---|---|
| the attack and what it destroyed | [writeups/2026-10-08-one-string-four-agents.md](writeups/2026-10-08-one-string-four-agents.md) |
| how the fleet is modelled: assets, boundaries, 10 input surfaces, residual risk | [THREAT-MODEL.md](THREAT-MODEL.md) |
| OWASP LLM Top 10 (2025) and MITRE ATLAS ids, **including the rows where I come out empty** | [MAPPING.md](MAPPING.md) |
| how well the human-approval gate actually classifies | [evals/RESULTS.md](evals/RESULTS.md) |
| the code that attacks it | [tonydzi/leash-poc](https://github.com/tonydzi/leash-poc) |
| the control being measured | [tonydzi/agent-approval-gate](https://github.com/tonydzi/agent-approval-gate) |

## The fleet in numbers

Recomputed weekly, unattended, by [`stats/fleet_stats.py`](stats/fleet_stats.py). Each row
names its source and the date it was last checked. Rows that could not be measured say so
instead of showing a zero.

<!-- FLEET-STATS:BEGIN -->
| what | number | source | checked |
|---|---|---|---|
| authorization-gate refusal rate (must-ask actions routed to a human) | 100.0% of 49 | `evals/refusal_overrefusal.py` | 2026-10-08 |
| over-refusal rate (benign actions routed to a human anyway) | 50.0% of 42 | `evals/refusal_overrefusal.py` | 2026-10-08 |
| must-ask actions caught **only** by the fail-closed default | 14 of 49 | `evals/refusal_overrefusal.py` | 2026-10-08 |
| production gate firings (real traffic, 90d window) | 2879 | `stats/real-traffic.json` | 2026-10-08 |
| asks that expired unanswered in that window | 0 | `stats/real-traffic.json` | 2026-10-08 |
| of those firings, landed in the catch-all category (taxonomy defect, not safety) | 2166 | `stats/real-traffic.json` | 2026-10-08 |
| machines reporting routines / routines under management | 5 / 1275 | fleet routine registry | 2026-10-08 |
| merged pull requests in third-party repositories | 52 across 36 repos (25 engineering, 11 curated lists) | GitHub search API | 2026-10-08 |
| issues filed upstream | 65 | GitHub search API | 2026-10-08 |
| public repositories | 147 | GitHub API | 2026-10-08 |

Coverage of this table: measured 3 of 4 sources; real_traffic: carried over from a dated snapshot

Regenerate: `python3 stats/fleet_stats.py --write` (runs weekly, unattended, on one node of the fleet).
<!-- FLEET-STATS:END -->

## The three things this repository adds

**1. A threat model that exists.** I had run the fleet for a year with the threat model in
my head and in the shape of the code. That is an intuition, not a threat model. v1 names 8
assets, 6 trust boundaries, **10 untrusted input surfaces**, 10 threats with evidence for
each, 12 controls each pointing at something runnable, and **9 residual risks with numbers
attached**. Zero external reviewers so far — that is the most useful issue you could open.

**2. A mapping with exact identifiers, published with its holes.** 4 of the OWASP LLM Top
10 (2025) are attacked and defended with runnable evidence; 4 are partially covered; 1 is
out of scope; 1 is modelled only. Fifteen MITRE ATLAS techniques reproduced on my own
stand, **ten more listed as applicable and untested**, twelve ATLAS mitigations implemented
and eight explicitly not. Identifiers were extracted from the ATLAS data snapshot and the
OWASP list on 2026-10-08, not written from memory.

**3. Refusal and over-refusal, as two separate numbers.** A guardrail without false-positive
and false-negative rates is a slogan. Mine, on a 91-action corpus against my own
classifier: **100% refusal** on must-ask actions, **50% over-refusal** on benign ones, and
the number that matters — **only 71.4% rule coverage**, meaning 14 of 49 must-ask actions
(a domain renewal, a plan upgrade, an audit-journal truncation, a terms-of-service
acceptance) reach a human *only* because the default is fail-closed. They have names now,
in [evals/RESULTS.md](evals/RESULTS.md).

## Verify any of it in under a minute

```bash
python3 evals/refusal_overrefusal.py      # the two numbers, recomputed
python3 evals/refusal_overrefusal.py --misses   # every wrong verdict, by id
python3 evals/test_red_first.py           # break the gate 6 ways, watch each break get caught
python3 evals/classifier.py --check-drift # is the vendored classifier still upstream's?
python3 stats/fleet_stats.py              # every number above, with its blind spots
```

No dependencies beyond Python 3.8+ and, for the GitHub rows only, a logged-in `gh` CLI.

## House rules this repo is written under

- **A test that has never been shown failing on broken code is not evidence.** Every suite
  here ships its mutants. The eval in this repo was shown red first: mutation `M3` failed on
  its first run, which is how the `contractor`/`contract` substring collision was found.
- **An instrument that cannot name its blind spots is worse than no instrument.** Every
  report prints what it could not judge and why.
- **Numbers are floors, not decoration.** Where production data is partly uncategorised
  (2166 of 2879 gate firings), the derived counts are labelled floors rather than totals.
- **No claim about anyone else's system.** 0 CVEs, 0 coordinated disclosures, 0 external
  reviews — stated here rather than left for you to notice.

## Licence

MIT. The threat model, mapping and write-up are released under the same terms: copy the
structure for your own fleet, that is the point of publishing it.
