#!/usr/bin/env python3
"""The decision classifier under test, vendored verbatim so the eval is reproducible.

SOURCE OF TRUTH: github.com/tonydzi/agent-approval-gate -> approval_gate.py
                 (function `suggest_class`, table `_HINTS`, map `CLASS_NAMES`)
PINNED AT      : commit 34ed02931226bacaaf90a5c392fe662818b4ca5e (2026-10-08)

Why a copy and not an import: the gate is a CLI with a config file and a sqlite journal.
The classifier is the only part an eval needs, and a 40-line copy keeps the eval runnable
with zero setup. The copy is a liability, so it ships with a drift check:

    python3 evals/classifier.py --check-drift

fetches the upstream file and compares the two tables. With no network it says so out loud
instead of printing a green verdict it cannot justify.
"""
from __future__ import annotations

import sys

SELF_CLASSES = ("A", "B", "C")   # agent decides these
ASK_CLASSES = ("D", "E")         # these may interrupt a human
CLASS_NAMES = {
    "A": "internal / reversible",
    "B": "own content into own channels",
    "C": "short outbound to a third party, on-topic",
    "D": "needs human hands (2FA / UAC / password / physical)",
    "E": "serious (money / irreversible delete / secrets to third parties / legal / mass-send)",
}

_HINTS = (
    ("E", ("wire", "transfer", "payment", "invoice", "refund", "purchase", "buy ",
           "usdt", "btc", "credit card", "$")),
    ("E", ("delete", "rm -rf", "drop table", "wipe", "erase", "purge", "empty trash",
           "force push", "revoke")),
    ("E", ("api key", "secret", "password", "credential", "token to", "private key",
           "share access")),
    ("E", ("contract", "sign", "agree to terms", "nda", "legal", "commit to pay")),
    ("E", ("mass", "bulk send", "everyone", "all users", "broadcast to", "mailing list")),
    ("D", ("2fa", "otp", "one-time code", "uac", "captcha", "passkey", "scan the qr",
           "physical", "plug in", "reboot the")),
    ("B", ("publish to our", "post to our", "our blog", "our channel", "changelog")),
    ("C", ("reply to", "email ", "dm ", "message ", "comment on", "answer the")),
    ("A", ("refactor", "rename", "run tests", "reindex", "cache", "local", "dry-run",
           "backup", "lint", "format")),
)

# The default verdict when no rule matches. Named so the mutation suite can flip it.
DEFAULT_CLASS = "E"


def suggest_class(text):
    """Heuristic first guess. Deliberately dumb and deliberately biased upward."""
    t = (text or "").lower()
    for klass, words in _HINTS:
        for w in words:
            if w in t:
                return klass, "matched %r -> %s" % (w, klass)
    return DEFAULT_CLASS, "no confident match -> defaulting to %s" % DEFAULT_CLASS


def routes_to_human(klass):
    return klass in ASK_CLASSES


UPSTREAM = ("https://raw.githubusercontent.com/tonydzi/agent-approval-gate/"
            "34ed02931226bacaaf90a5c392fe662818b4ca5e/approval_gate.py")


def check_drift():
    """Compare the vendored tables against upstream. Say 'cannot judge' when offline."""
    try:
        import urllib.request
        with urllib.request.urlopen(UPSTREAM, timeout=20) as r:
            up = r.read().decode("utf-8", "replace")
    except Exception as ex:
        print("DRIFT: cannot judge (upstream unreachable: %s)" % ex)
        print("       the vendored copy was NOT verified in this run.")
        return 2
    missing = [w for _, words in _HINTS for w in words if repr(w)[1:-1] not in up]
    if missing:
        print("DRIFT: %d vendored pattern(s) absent upstream: %s" % (len(missing), missing[:8]))
        return 1
    print("DRIFT: none — all %d vendored patterns present upstream at the pinned commit."
          % sum(len(w) for _, w in _HINTS))
    return 0


if __name__ == "__main__":
    if "--check-drift" in sys.argv:
        sys.exit(check_drift())
    for arg in sys.argv[1:]:
        k, why = suggest_class(arg)
        print("%s  %-5s %s  (%s)" % ("ASK " if routes_to_human(k) else "self", k, why,
                                     CLASS_NAMES[k]))
