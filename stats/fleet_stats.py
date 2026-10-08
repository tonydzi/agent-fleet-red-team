#!/usr/bin/env python3
"""Recompute every number this repository claims, and say which ones it could not check.

This exists because a README with hand-typed numbers rots in a week and nobody can tell
when it started lying. So the numbers are computed, dated, and each source carries its own
verdict: measured now, carried over from a dated snapshot, or NOT AVAILABLE on this machine.
A report that cannot name its blind spots is worse than no report.

SOURCES
  github        live, via the `gh` CLI against the public API. 0 tokens, no auth secrets
                needed beyond a logged-in gh. Counts public repos, merged pull requests in
                third-party repositories (split into engineering repos and curated-list
                repos, because they are not the same claim), upstream issues, stars.
  evals         runs evals/refusal_overrefusal.py in-process. Deterministic, same answer on
                every machine, so this number never depends on who ran it.
  fleet         routine counts per node, read from the fleet's own routine registry.
                Needs env FLEET_BUS pointing at the registry directory. Unset -> the report
                says "not available on this node" instead of printing a zero.
  real_traffic  production authorization-gate firings. Measured on the node that holds the
                gate journal and written to stats/real-traffic.json with a date. This
                script never invents it; it reports the figure and how old it is.

RUN
  python3 stats/fleet_stats.py                 # print the report
  python3 stats/fleet_stats.py --write         # also update fleet-stats.json, FLEET.md,
                                               # and the numbers block inside README.md
  python3 stats/fleet_stats.py --no-github     # offline: skip the network source

EXIT 0 on a clean run even when sources are missing: a missing source is a reported fact,
not a crash. Exit 2 only if --write cannot write.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_JSON = ROOT / "stats" / "fleet-stats.json"
OUT_MD = ROOT / "stats" / "FLEET.md"
README = ROOT / "README.md"
SNAPSHOT = ROOT / "stats" / "real-traffic.json"

LOGIN = "tonydzi"
OWN = ["tonydzi", "Palo-Alto-AI-Research-Lab"]
FLAGSHIPS = ["leash-poc", "agent-approval-gate", "agent-fleet-red-team",
             "verbatim-citation-gate", "agent-control-plane-casebook", "claw-consensus"]
# A pull request that adds a link to a curated list is a real contribution and a different
# claim from one that changes code. Keeping them in one number would overstate the second.
LIST_REPO_RX = re.compile(r"awesome|curated|-list$|^list-", re.I)

BEGIN = "<!-- FLEET-STATS:BEGIN -->"
END = "<!-- FLEET-STATS:END -->"


def today():
    return _dt.date.today().isoformat()


def anon(name):
    """Stable pseudonym for a node.

    The counts are the publishable fact; the machine names are not. Real hostnames and
    fleet keys in a public file are free reconnaissance, and the threat model deliberately
    talks about node ROLES instead. The digest is stable across weeks, so per-node series
    still line up, and it carries no hostname.
    """
    import hashlib
    h = hashlib.sha256(("fleet-node:" + str(name)).encode("utf-8")).hexdigest()[:6]
    return "node-" + h


def gh_json(*args, timeout=120):
    """One `gh` call -> parsed JSON, or None. Never raises."""
    try:
        p = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired) as ex:
        return None, "gh unavailable: %s" % type(ex).__name__
    if p.returncode != 0:
        return None, (p.stderr or "").strip().splitlines()[-1:] or ["gh exit %d" % p.returncode]
    try:
        return json.loads(p.stdout or "null"), None
    except json.JSONDecodeError:
        return p.stdout.strip(), None


def gh_lines(*args, timeout=300):
    try:
        p = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired) as ex:
        return None, "gh unavailable: %s" % type(ex).__name__
    if p.returncode != 0:
        return None, "gh exit %d" % p.returncode
    return [l for l in (p.stdout or "").splitlines() if l.strip()], None


def source_github():
    excl = " ".join("-user:%s -org:%s" % (o, o) for o in OWN)
    out = {"verdict": "measured", "asof": today(), "notes": []}

    user, err = gh_json("api", "users/%s" % LOGIN, "--jq",
                        "{public_repos,followers}")
    if err or not isinstance(user, dict):
        return {"verdict": "not available", "asof": today(),
                "why": "gh could not read the public profile (%s)" % (err,)}
    out["public_repos"] = user.get("public_repos")
    out["followers"] = user.get("followers")

    prs, err = gh_json("api", "-X", "GET", "search/issues", "-f",
                       "q=is:pr author:%s is:merged %s" % (LOGIN, excl), "--jq",
                       ".total_count")
    out["upstream_prs_merged"] = prs if not err else None
    if err:
        out["notes"].append("merged-PR count unavailable: %s" % (err,))

    iss, err = gh_json("api", "-X", "GET", "search/issues", "-f",
                       "q=is:issue author:%s %s" % (LOGIN, excl), "--jq", ".total_count")
    out["upstream_issues"] = iss if not err else None

    repos, err = gh_lines("api", "-X", "GET", "search/issues", "-f",
                          "q=is:pr author:%s is:merged %s" % (LOGIN, excl),
                          "-f", "per_page=100", "--paginate", "--jq",
                          ".items[].repository_url")
    if repos is None:
        out["notes"].append("repo breakdown unavailable: %s" % (err,))
        out["upstream_repos"] = None
    else:
        names = sorted({r.split("/repos/")[-1] for r in repos})
        eng = [n for n in names if not LIST_REPO_RX.search(n.split("/")[-1])]
        out["upstream_repos"] = len(names)
        out["upstream_repos_engineering"] = len(eng)
        out["upstream_repos_curated_lists"] = len(names) - len(eng)
        out["upstream_repo_names"] = names

    stars = {}
    for r in FLAGSHIPS:
        v, e = gh_json("api", "repos/%s/%s" % (LOGIN, r), "--jq", ".stargazers_count")
        stars[r] = v if not e else None
    out["flagship_stars"] = stars
    return out


def source_evals():
    sys.path.insert(0, str(ROOT / "evals"))
    try:
        import refusal_overrefusal as R
    except Exception as ex:
        return {"verdict": "not available", "why": "eval not importable: %s" % ex}
    try:
        res = R.measure(R.load())
    except SystemExit as ex:
        return {"verdict": "not available", "why": "eval refused to run: %s" % ex}
    return {
        "verdict": "measured", "asof": today(),
        "corpus_actions": res["corpus"]["total"],
        "must_ask": res["corpus"]["must_ask"],
        "benign": res["corpus"]["benign"],
        "refusal_rate_pct": res["refusal_rate_pct"],
        "over_refusal_rate_pct": res["over_refusal_rate_pct"],
        "rule_coverage_pct": res["rule_coverage_pct"],
        "must_ask_caught_only_by_default": res["default_catch_only"],
        "missed_must_ask": res["missed_must_ask"],
    }


def source_fleet():
    bus = os.environ.get("FLEET_BUS", "").strip()
    if not bus:
        return {"verdict": "not available",
                "why": "FLEET_BUS is unset on this machine, so routine counts were not read"}
    d = Path(bus)
    if not d.is_dir():
        return {"verdict": "not available", "why": "FLEET_BUS=%s is not a directory" % bus}
    nodes, total, oldest = {}, 0, None
    for f in sorted(d.glob("*.jsonl")):
        if ".bak" in f.name:
            continue
        try:
            with f.open(encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not row.get("_meta"):
                        continue
                    node, cnt = row.get("node"), row.get("count")
                    at = (row.get("collected_at") or "")[:10]
                    nodes[anon(node)] = {"routines": cnt, "collected": at}
                    total += int(cnt or 0)
                    oldest = at if (oldest is None or (at and at < oldest)) else oldest
                    break
        except OSError:
            continue
    if not nodes:
        return {"verdict": "not available",
                "why": "no routine-registry snapshots found under %s" % bus}
    return {"verdict": "measured", "asof": today(), "nodes_reporting": len(nodes),
            "routines_total": total, "oldest_snapshot": oldest, "per_node": nodes}


def source_real_traffic():
    if not SNAPSHOT.exists():
        return {"verdict": "not available",
                "why": "stats/real-traffic.json absent; production gate figures are not guessed"}
    try:
        d = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as ex:
        return {"verdict": "not available", "why": "snapshot unreadable: %s" % ex}
    age = None
    try:
        age = (_dt.date.today() - _dt.date.fromisoformat(d.get("measured_on", ""))).days
    except ValueError:
        pass
    d["verdict"] = "carried over from a dated snapshot"
    d["age_days"] = age
    if age is not None and age > 45:
        d["stale"] = True
    return d


def collect(do_github=True):
    data = {
        "generated_on": today(),
        "generated_by": "stats/fleet_stats.py",
        "machine": anon(os.environ.get("FLEET_NODE")
                        or os.environ.get("COMPUTERNAME")
                        or (os.uname().nodename if hasattr(os, "uname") else "unknown")),
        "github": source_github() if do_github
        else {"verdict": "not available", "why": "--no-github"},
        "evals": source_evals(),
        "fleet": source_fleet(),
        "real_traffic": source_real_traffic(),
    }
    checked = [k for k in ("github", "evals", "fleet", "real_traffic")
               if data[k].get("verdict") == "measured"]
    data["coverage"] = {
        "sources_total": 4,
        "sources_measured": len(checked),
        "measured": checked,
        "line": "measured %d of 4 sources; %s" % (
            len(checked),
            ", ".join("%s: %s" % (k, data[k].get("why") or data[k].get("verdict"))
                      for k in ("github", "evals", "fleet", "real_traffic")
                      if data[k].get("verdict") != "measured") or "none missing"),
    }
    return data


def render_block(d):
    g, e, f, rt = d["github"], d["evals"], d["fleet"], d["real_traffic"]
    L = ["| what | number | source | checked |", "|---|---|---|---|"]

    def row(what, num, src, when):
        L.append("| %s | %s | %s | %s |" % (what, num, src, when))

    if e.get("verdict") == "measured":
        row("authorization-gate refusal rate (must-ask actions routed to a human)",
            "%s%% of %d" % (e["refusal_rate_pct"], e["must_ask"]),
            "`evals/refusal_overrefusal.py`", e["asof"])
        row("over-refusal rate (benign actions routed to a human anyway)",
            "%s%% of %d" % (e["over_refusal_rate_pct"], e["benign"]),
            "`evals/refusal_overrefusal.py`", e["asof"])
        row("must-ask actions caught **only** by the fail-closed default",
            "%d of %d" % (e["must_ask_caught_only_by_default"], e["must_ask"]),
            "`evals/refusal_overrefusal.py`", e["asof"])
    else:
        row("gate evals", "not available", e.get("why", ""), d["generated_on"])

    if rt.get("verdict", "").startswith("carried"):
        row("production gate firings (real traffic, %sd window)" % rt.get("window_days", "?"),
            "%s" % rt.get("tier2_firings", "?"), "`stats/real-traffic.json`",
            rt.get("measured_on", "?") + (" (stale)" if rt.get("stale") else ""))
        row("asks that expired unanswered in that window",
            "%s" % rt.get("expired_unanswered", "?"),
            "`stats/real-traffic.json`", rt.get("measured_on", "?"))
        row("of those firings, landed in the catch-all category (taxonomy defect, not safety)",
            "%s" % (rt.get("by_category", {}).get("other", "?")),
            "`stats/real-traffic.json`", rt.get("measured_on", "?"))
    if f.get("verdict") == "measured":
        row("machines reporting routines / routines under management",
            "%d / %d" % (f["nodes_reporting"], f["routines_total"]),
            "fleet routine registry", f["asof"])
    else:
        row("routines under management", "not available on this machine", f.get("why", ""),
            d["generated_on"])
    if g.get("verdict") == "measured":
        row("merged pull requests in third-party repositories",
            "%s across %s repos (%s engineering, %s curated lists)"
            % (g.get("upstream_prs_merged"), g.get("upstream_repos"),
               g.get("upstream_repos_engineering"), g.get("upstream_repos_curated_lists")),
            "GitHub search API", g["asof"])
        row("issues filed upstream", "%s" % g.get("upstream_issues"),
            "GitHub search API", g["asof"])
        row("public repositories", "%s" % g.get("public_repos"), "GitHub API", g["asof"])
    else:
        row("GitHub figures", "not available", g.get("why", ""), d["generated_on"])

    L.append("")
    L.append("Coverage of this table: %s" % d["coverage"]["line"])
    L.append("")
    L.append("Regenerate: `python3 stats/fleet_stats.py --write` "
             "(runs weekly, unattended, on one node of the fleet).")
    return "\n".join(L)


def write_outputs(d):
    OUT_JSON.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    block = render_block(d)
    OUT_MD.write_text(
        "# The fleet in numbers\n\n"
        "Generated by `stats/fleet_stats.py` on %s (node: %s). Do not hand-edit.\n\n%s\n"
        % (d["generated_on"], d["machine"], block), encoding="utf-8")
    if README.exists():
        txt = README.read_text(encoding="utf-8")
        if BEGIN in txt and END in txt:
            pre, rest = txt.split(BEGIN, 1)
            _, post = rest.split(END, 1)
            README.write_text(pre + BEGIN + "\n" + block + "\n" + END + post,
                              encoding="utf-8")
        else:
            print("note: README has no FLEET-STATS markers; left untouched")


def main(argv):
    d = collect(do_github="--no-github" not in argv)
    print(render_block(d))
    if "--write" in argv:
        try:
            write_outputs(d)
        except OSError as ex:
            print("could not write outputs: %s" % ex, file=sys.stderr)
            return 2
        print("\nwrote %s, %s%s" % (OUT_JSON.name, OUT_MD.name,
                                    ", README block" if README.exists() else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
