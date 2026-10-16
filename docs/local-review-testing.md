# Local conversation review acceptance

2026-10-16 · local 5.0.1 update

The human can review prepared definitions in either Codex or the Council webpage. The new local `human-action` command records an explicit conversation instruction and calls the existing human mutation paths. Preparation, candidate tokens, dependency checks, formal versions and atomic group writes remain shared.

The Skill routes this independent step to [local-review.md](../skills/oppencouncil/references/local-review.md). It preserves prerequisite work and the research handoff, presents one group or up to three independent F records per exchange, and requires clear, concrete dialogue with the proposed wording first.

## Automated checks

| Check | Result and scope |
| --- | --- |
| `council/tests/test_human_actions.py` | 32 passed: required authorization, ordinary AI restrictions, stale candidate/evidence tokens, preparation and handoff gates, single/group confirmation, same-version reconfirmation, discussion, candidate edits, withdrawal, idempotency, interrupted transaction recovery, v3/v4 compatibility and the actual Skill entrypoint |
| Existing definition, decision-group, workflow, helper-routing, capability and site tests | Relevant regression tests passed. The sandbox initially blocked socket tests; the capability/site suites passed with local socket access (35 tests). |
| New site interoperability test | 2 passed: conversation confirmation appears in HTTP snapshots; a subsequent web revision invalidates old conversation tokens; web confirmation preserves prior conversation provenance |
| Workbench, group and evidence JavaScript suites | 103 passed; the added case checks that conversation receipts follow the definition text, identify the executor and safely render the instruction |
| MCP v5 Council tests | 14 passed; curated external reads retain human discussion but omit local execution receipts; external write permissions remain unchanged |
| Skill and source checks | Skill validator, changed Python lint and `git diff --check` passed; Decision Memory text is unchanged |

These are selected component checks, not a new full CI or release run. Skill instructions and interface tests do not by themselves demonstrate that every model will consistently follow the dialogue pacing.

## Real browser checks

A small synthetic general project contained one two-member group and one independent F. No real research project records were modified.

1. Saved a human conversation comment and confirmed the prepared group through the local helper.
2. Opened the actual workbench in the Codex browser. Both members showed formal v1, the discussion showed “来自 Codex 对话”, and the expandable operation record showed the human instruction and Codex executor below the definition.
3. Opened the independent F, which had a conversation comment but was still a candidate. Clicked its normal webpage confirmation button.
4. Read the F through the local command: the same wording was formal v1, with no remaining candidate. The earlier conversation comment remained; the web confirmation was not relabelled as a conversation approval.

Screenshots were saved locally outside the product repository. Testing used temporary synthetic records, without copying, migrating or archiving a real project.
