# Standards mapping: this fleet against OWASP LLM Top 10 (2025) and MITRE ATLAS

Status: v1, 2026-10-08.

Knowing a list is not a skill. Mapping your own running system onto one, with exact
identifiers, and then publishing the rows where you come out empty — that is the useful
half. This file does the second thing.

**Provenance of the identifiers.** MITRE ATLAS ids and names were extracted on 2026-10-08
from `dist/ATLAS.yaml` in [mitre-atlas/atlas-data](https://github.com/mitre-atlas/atlas-data)
(170 techniques and sub-techniques, 35 mitigations, 16 tactics in that snapshot). OWASP ids
and titles were read the same day from the published
[OWASP Top 10 for LLM Applications 2025](https://genai.owasp.org/llm-top-10/). No id in this
file was written from memory; if one is wrong, the snapshot is the thing to re-pull.

Cross-references: system description, surfaces and controls live in
[THREAT-MODEL.md](THREAT-MODEL.md); the measured numbers live in
[evals/RESULTS.md](evals/RESULTS.md).

---

## 1. OWASP Top 10 for LLM Applications 2025 — where this fleet actually stands

| id | risk | status in this fleet | evidence |
|---|---|---|---|
| **LLM01:2025** | Prompt Injection | **attacked and defended, reproducibly.** Indirect injection through a tool description and through three more surfaces; contained by an authorization boundary rather than by instruction-level pleading | `poc/run_poc.py`, `replay/run_replay.py` in [leash-poc](https://github.com/tonydzi/leash-poc) |
| **LLM02:2025** | Sensitive Information Disclosure | **attacked and defended.** A planted secret is exfiltrated by the naive agent (237 bytes) and stopped by egress leak-scan | T1 in THREAT-MODEL §5 |
| **LLM03:2025** | Supply Chain | **partially covered.** The poisoned-tool case is modelled and tested (a hostile MCP server is the attacker in the test bed); dependency and model-provenance supply chain is **not** covered | `poc/evil_mcp_server.py`; gap: no AI-BOM |
| **LLM04:2025** | Data and Model Poisoning | **out of scope, honestly.** Nothing here trains or fine-tunes a model. Data poisoning of the retrieval layer is covered under LLM08 | — |
| **LLM05:2025** | Improper Output Handling | **partially covered.** Tool invocation is gated and arguments are scoped, so model output cannot reach a side effect unreviewed; rendering-level output handling is not separately tested | `replay/boundary.py` |
| **LLM06:2025** | Excessive Agency | **this is the centre of the work.** Decision classes, per-principal tool grants, resource scopes, out-of-band approval for irreversible actions, and the two numbers that say how well the classifier does it | [evals/RESULTS.md](evals/RESULTS.md), [agent-approval-gate](https://github.com/tonydzi/agent-approval-gate) |
| **LLM07:2025** | System Prompt Leakage | **modelled, not measured.** The canon is treated as an asset (A1) with a write gate, but I have no red test that extracts it | gap, THREAT-MODEL T8 |
| **LLM08:2025** | Vector and Embedding Weaknesses | **partially covered.** Fabricated-citation detection ships and is tested; RAG poisoning as an end-to-end attack path on our own index is **not** measured | [verbatim-citation-gate](https://github.com/tonydzi/verbatim-citation-gate) |
| **LLM09:2025** | Misinformation | **covered by process, measured weakly.** House rules force evidence-before-claim and a red test before a fix is called done; the citation gate is the only machine-checked part | — |
| **LLM10:2025** | Unbounded Consumption | **measured in production.** Open-ask cap, per-day budgets, channel rate limits; 146 asks were cut by the cap in a 90-day window | [stats/real-traffic.json](stats/real-traffic.json) |

Score honestly: 4 of 10 attacked and defended with runnable evidence, 4 partially covered,
1 out of scope, 1 modelled only.

---

## 2. MITRE ATLAS — techniques I have reproduced against my own fleet

Each row is a technique I actually ran on my own stand, with the surface it entered through
(S-ids from THREAT-MODEL §4) and what stopped it.

| ATLAS id | technique | surface | observed result |
|---|---|---|---|
| **AML.T0051** | LLM Prompt Injection | S1, S2, S4, S5 | one poisoned string, four delivery vectors, five forbidden requests |
| **AML.T0110** | AI Agent Tool Poisoning | S1 | injection carried in the `get_directions` tool description |
| **AML.T0011.002** | Poisoned AI Agent Tool | S1 | hostile MCP server in the test bed |
| **AML.T0084.001** | Discover AI Agent Configuration: Tool Definitions | S1 | the attack needs the tool list first; this is the recon step |
| **AML.T0053** | AI Agent Tool Invocation | — | the action channel the injection tries to reach |
| **AML.T0086** | Exfiltration via AI Agent Tool Invocation | S1 | naive: 4 exfil calls, 168 bytes out. Leashed: 0 |
| **AML.T0057** | LLM Data Leakage | S1 | planted secret leaves the process in the naive run |
| **AML.T0101** | Data Destruction via AI Agent Tool Invocation | S5 | naive fleet deleted the payroll fixture; leashed refused out-of-scope and held in-scope |
| **AML.T0080** | AI Agent Context Poisoning | S5, S6 | a work item from another agent carries the payload |
| **AML.T0099** | AI Agent Tool Data Poisoning | S2 | poisoned page inside a retrieved document |
| **AML.T0066** | Retrieval Content Crafting | S2 | the payload is written to be retrieved |
| **AML.T0093** | Prompt Infiltration via Public-Facing Application | S4 | payload in the body of a fetched web page |
| **AML.T0098** | AI Agent Tool Credential Harvesting | S1 | production key rotation requested through the agent's own tools |
| **AML.T0103** | Deploy AI Agent | S5 | sub-agent spawned with rights the parent lacks; refused as delegation escalation |
| **AML.T0034.002** | Agentic Resource Consumption | — | measured in production as attention cost, not as a crafted attack |

### Techniques that apply to this architecture and that I have **not** tested

Printed because a mapping that only lists hits is marketing.

| ATLAS id | technique | why it applies here | status |
|---|---|---|---|
| **AML.T0070** | RAG Poisoning | the vault is the retrieval index and takes untrusted imports (S2) | not tested end to end |
| **AML.T0071** | False RAG Entry Injection | same surface | not tested |
| **AML.T0082** | RAG Credential Harvesting | the index has touched files that once contained secrets | not tested |
| **AML.T0081** | Modify AI Agent Configuration | the canon is the highest-value asset (A1) | mitigated by a write gate, **no red test** |
| **AML.T0083** | Credentials from AI Agent Configuration | node configuration references credential stores | not tested |
| **AML.T0056** | Extract LLM System Prompt | maps to LLM07 above | not tested |
| **AML.T0061** | LLM Prompt Self-Replication | S6 and S10 make cross-session propagation structurally possible | not tested — and this is the one that worries me most |
| **AML.T0094** | Delay Execution of LLM Instructions | a poisoned routine definition (S10) is persistence | not tested |
| **AML.T0092** | Manipulate User LLM Chat History | sessions are resumable from stored transcripts | not tested |
| **AML.T0100** | AI Agent Clickbait | the fleet browses | not tested |

Tactics touched by the tested rows: AML.TA0004 Initial Access, AML.TA0005 Execution,
AML.TA0008 Discovery, AML.TA0009 Collection, AML.TA0010 Exfiltration, AML.TA0011 Impact,
AML.TA0012 Privilege Escalation, AML.TA0013 Credential Access. Untouched and relevant:
AML.TA0006 Persistence, AML.TA0015 Lateral Movement — both reachable through S5/S10 and the
sync fabric, neither attacked.

---

## 3. MITRE ATLAS mitigations — which ones I actually implement

| ATLAS id | mitigation | implemented as | tested by |
|---|---|---|---|
| **AML.M0029** | Human In-the-Loop for AI Agent Actions | decision classes D/E route to an out-of-band approval channel; token bound to one request id | `evals/refusal_overrefusal.py`, `evals/test_red_first.py` |
| **AML.M0030** | Restrict AI Agent Tool Invocation on Untrusted Data | provenance is carried with every proposed action; the authorization step is a separate component from the deciding one | `poc/test_leash.py` (7 adversarial checks) |
| **AML.M0028** | AI Agent Tools Permissions Configuration | per-principal tool grants; nothing pre-approved | `replay/test_boundary.py` |
| **AML.M0026** | Privileged AI Agent Permissions Configuration | privileged tools (key rotation, delete, sub-agent spawn) are not in ordinary principals' grants | the four STOP rows per agent in the replay table |
| **AML.M0027** | Single-User AI Agent Permissions Configuration | one principal per agent; follower nodes are data-only | THREAT-MODEL TB6 |
| **AML.M0032** | Segmentation of AI Agent Components | plan / authorize / execute are separate components; nodes have separate roles and rights | leash-poc architecture |
| **AML.M0033** | Input and Output Validation for AI Agent Components | egress leak-scan before send; argument and resource-scope validation; citation gate on quoted text | the T1 run is this control firing |
| **AML.M0024** | AI Telemetry Logging | hash-chained, fsync-before-return decision journal; 27 decisions per replay run, chain verified | `replay/node_kill_test.py` |
| **AML.M0004** | Restrict Number of AI Model Queries | open-ask cap, per-day budgets, per-channel rate limits | production counters |
| **AML.M0019** | Control Access to AI Models and Data in Production | canon write right held by one node; read-only propagation to followers | ⚠️ no red test |
| **AML.M0005** | Control Access to AI Models and Data at Rest | credential store kept out of the retrieval index and out of always-loaded context | ⚠️ convention, not enforced by a parser |
| **AML.M0020** | Generative AI Guardrails | output gates on fabricated citations and on outbound text | own suites |

### Mitigations I do **not** implement, and why

| ATLAS id | mitigation | status |
|---|---|---|
| **AML.M0031** | Memory Hardening | **the biggest hole.** Persistent memory (S6) is written by past agent runs and read into privileged context with no integrity check. Mapped, unmitigated, untested |
| **AML.M0023** | AI Bill of Materials | not produced. Relevant: the fleet loads many third-party MCP servers |
| **AML.M0016** | Vulnerability Scanning | not run against the agent surface |
| **AML.M0015** | Adversarial Input Detection | deliberately not relied upon: the architecture assumes detection fails and places the boundary after it |
| **AML.M0018** | User Training | single-principal system; the principal is the author |
| **AML.M0003**, **AML.M0007**, **AML.M0008**, **AML.M0022** | Model Hardening, Sanitize Training Data, Validate AI Model, Model Alignment | out of scope: no training or fine-tuning here; these sit with the model provider |
| **AML.M0034** | Deepfake Detection | not applicable to this system |

---

## 4. The one-paragraph version

The fleet is strong exactly where the architecture does the work — excessive agency,
prompt injection, tool-level least privilege, auditability — and it is weak exactly where
I have been relying on convention instead of a test: agent memory integrity
(AML.M0031), canon modification (AML.T0081), retrieval poisoning (AML.T0070/T0071), and
cross-session propagation (AML.T0061). That list is the roadmap, and it is published
before the fixes rather than after, so the dates are checkable.
