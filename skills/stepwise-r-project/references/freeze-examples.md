# Content quality examples

Read only when an example is needed to calibrate the content gate. All invented values are teaching fixtures, never defaults for a real project.

## Scientific example: direction versus an inclusion rule

“Target T2D + CKD; T2D follows RAMP; CKD will be verified separately” fixes a research direction but cannot determine patient eligibility. Test it with a synthetic person having Type_2 at month M−8 and Type_1 at M−1: an “ever Type_2” reader and a “most recent label” reader can disagree while both claiming to follow RAMP. Neither rule may be adopted from this illustration. Verify the actual field, source algorithm, temporal availability and conflict policy; compare any genuinely unbound choices for the researcher.

Likewise, one abnormal kidney measurement and repeated measurements may be treated differently by different CKD rules. The relevant threshold, units, persistence, source hierarchy and pre-entry availability must be obtained from the chosen authoritative definition or explicitly proposed and decided. Do not substitute an RCT's renal eligibility range for a general CKD definition without explaining and deciding that distinction. Bind time-zero and missing-eligibility dependencies to their real owners. If those are unresolved, report that cohort membership is not yet determined.

A **synthetic**, fully specified small rule can be brief: “At the first day of index month M, consider only the six complete calendar months M−6 through M−1. Valid `flag` values are exactly 0 or 1; ignore null/invalid flags. Inspect months from newest to oldest, skipping months with no valid flag. In the first remaining month, identical valid flags count once; if both 0 and 1 occur, return unknown without looking further back. Otherwise output true for 1 and false for 0. No valid month yields unknown. Never use month M or later.” For M = 2026-07, January flag 1 alone returns true; December flag 1 alone returns unknown; February 1 followed by June 0 returns false; June 0 and 1 returns unknown; July 1 alone returns unknown. These are teaching fixtures, not a clinical phenotype or an approved project rule.
