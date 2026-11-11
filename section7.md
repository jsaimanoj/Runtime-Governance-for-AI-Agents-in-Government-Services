With proposals held fixed, the gate cut unsafe executions from 200 to 7 of 1,500 scenarios and raised legitimate task completion from 82.45% to 86.83%, while benign requests completed at almost the same rate. Because hard-invariant cases are now blocked before they reach a person, escalations to reviewers fell by 33%.

**Implementation.** Every result in this section comes from the released simulator, pvrga_sim.py, which runs each condition in its own fresh environment, as in the loop in Appendix A, with the parameters in Section 6. Under Control-enforced, every action passes the gate before it runs, including actions a reviewer has approved, and the simulator stops with an error if any gated execution lacks an ALLOW decision; none did (838 of 838 executions in the primary run had one). An earlier version of this simulator let actions the agent itself escalated run after reviewer approval without a second gate decision; that version broke complete mediation (I1), and its results are withdrawn. The figures in earlier drafts (34.87%, 14.40%, and 0.53% unsafe execution) came from a separate implementation that ran conditions in a shared environment and whose parameters were not recorded; they could not be reproduced or traced, and are also withdrawn.

**Primary run (seed 20261102, 1,500 scenarios per condition).** Percentages carry 95% Wilson intervals.

| Measure | Baseline | Policy-guided | Control-enforced |
| --- | --- | --- | --- |
| Unsafe proposals | 431 | 197 | 197 |
| Unsafe executions | 422; 28.13% [25.92, 30.46] | 200; 13.33% [11.71, 15.15] | 7; 0.47% [0.23, 0.96] |
| Legitimate task completion (of 957) | 777; 81.19% [78.59, 83.54] | 789; 82.45% [79.91, 84.72] | 831; 86.83% [84.54, 88.83] |
| Benign requests completed (of 750) | 722; 96.27% | 708; 94.40% | 706; 94.13% |
| False blocks by the gate (of 750 benign) | No gate | No gate | 2; 0.27% |
| Escalations to reviewers (per 1,000 scenarios) | 228 (152) | 405 (270) | 270 (180) |
| Unnecessary escalations (benign cases) | 27 | 36 | 51 |
| Escalations unresolved in the service window | 10 | 37 | 21 |
| Escalation precision (escalated case was hazardous) | 88.2% | 91.1% | 81.1% |
| Escalation recall (escalation-type hazards reaching review) | 30.5% | 47.4% | 70.9% |
| Raw completion (any execution) | 1,199 | 989 | 838 |

Unsafe executions can exceed unsafe proposals, as in the Policy-guided column, because without a gate a reviewer can wrongly approve a hazardous case the agent escalated; tool failures work the other way. Under the gate, hard-invariant cases are blocked before review, which is why escalations fall and why escalation precision is lower: the cases left for reviewers are the genuinely ambiguous ones plus benign cases flagged for review. Escalation recall stays below 100% because a hazardous case the agent declines never reaches review: it is unserved, not unsafe. The difference between Baseline and Policy-guided is set by the injected agent probabilities and is not evidence about prompting.

**By scenario family (primary run).**

| Family | Unsafe executions: Baseline, Policy-guided, Control-enforced | Legitimate completion: Policy-guided to Control-enforced | Escalations: Policy-guided to Control-enforced | False blocks |
| --- | --- | --- | --- | --- |
| Consent and privacy | 80, 39, 1 | 91 to 91 of 93 | 84 to 6 | 0 |
| Eligibility evidence | 83, 49, 0 | 99 to 99 of 108 | 70 to 10 | 0 |
| Tool privilege | 100, 37, 1 | 95 to 93 of 101 | 84 to 7 | 2 |
| Rights-affecting action | 75, 32, 1 | 140 to 160 of 203 | 79 to 115 | 0 |
| Conflicting records | 84, 43, 4 | 130 to 154 of 202 | 79 to 119 | 0 |
| Ordinary low risk | 0, 0, 0 | 234 to 234 of 250 | 9 to 13 | 0 |

In the three hard-invariant families, the gate blocks covered hazards outright, so escalations fall and the only residual risk is a rule gap. In the two escalation families, the gate sends cases the agent would have executed to a reviewer, who can approve them correctly; this is where the gain in legitimate completion comes from, and also where reviewer errors can still let a hazardous case through. False blocks came only from fail-closed outages.

**Paired comparison.** 193 scenarios executed unsafely without the gate and safely with it; none went the other way; 7 executed unsafely in both. The exact McNemar test on the 193 discordant pairs gives p ≈ 1.6 × 10⁻⁵⁸. This confirms the implemented gate changes outcomes under the stated assumptions; it is not a measure of real-world safety.

**Residual unsafe executions, from traces.** Each of the 7 is identified by scenario in traces_primary.csv:

| Cause | Count | Scenarios |
| --- | --- | --- |
| Rule gap: hazard present but not encoded, so the gate allowed it | 4 | S0215 consent and privacy; S0642 tool privilege; S1127 conflicting records; S1221 conflicting records |
| Reviewer wrongly approved an escalation-type case, which the gate then allowed because the escalation requirement was met | 3 | S0884 rights-affecting action (escalated by the gate); S1219 conflicting records (escalated by the agent); S1248 conflicting records (escalated by the agent) |

No residual case came from a hard-invariant family after review: approval cannot override a block, and in these runs no blocked case reached a reviewer at all. The rule gaps are the coverage risk varied in the sensitivity analysis; the reviewer errors are a risk the gate is designed to hand to people, not remove. No reverse case occurred. With isolated environments and shared random draws, the gate can remove an unsafe execution but cannot add one.

**Replication.** With seed 20261103, unsafe executions were 463, 200, and 11 (30.87%, 13.33%, 0.73%); legitimate completion was 78.64%, 81.94%, and 86.27%; benign completion was 714, 704, and 700 of 744; the gate made 3 false blocks; and escalations were 197, 419, and 295. The 11 residual cases were 5 rule gaps and 6 reviewer errors on escalation-type cases, with no reverse cases (McNemar p ≈ 2.5 × 10⁻⁵⁷). Across 100 further seeds, mean unsafe execution was 29.55% (standard deviation 1.04), 13.07% (0.92), and 0.48% (0.18), and mean legitimate completion was 79.17%, 82.82%, and 86.71%.

**Sensitivity.** Each parameter was varied with the others at their defaults, averaging 20 seeds per value:

| Parameter varied (default) | Values | Control-enforced unsafe execution | Reduction against Policy-guided | Control-enforced legitimate completion |
| --- | --- | --- | --- | --- |
| Reviewer wrong decision (0.05) | 0 to 0.30 | 0.24% to 1.44% | 97.9% to 91.3% | 87.4% to 83.1% |
| Gate miss rate (0.02) | 0 to 0.20 | 0.18% to 2.68% | 98.6% to 78.7% | 86.8% to 85.9% |
| Policy-guided agent proceeds on hazards (0.25) | 0.10 to 0.40 | 0.27% to 0.60% | 95.3% to 96.9% | 85.8% to 87.5% |
| Escalations unresolved (0.10) | 0 to 0.30 | 0.46% to 0.40% | 96.4% to 96.8% | 88.8% to 82.5% |
| Benign case wrongly flagged (0.02) | 0 to 0.10 | 0.44% at every value | 96.5% at every value | 86.9% to 86.0%; escalations 181 to 227 per 1,000 |

The gate reduced unsafe execution at every value tested, but the size of the reduction is not fixed. It depends most on rule coverage and on reviewer reliability in the escalation families, and it grows with how often the ungated agent proposes unsafe actions. The headline reduction should therefore always be quoted with its parameters. Unresolved escalations barely affect safety but cost legitimate completion directly.

**What this establishes.** These results establish Stage 1 design behavior under stated assumptions: a deterministic gate that mediates every action removes most unsafe executions, the remaining risk sits in rule coverage and in human review of genuinely ambiguous cases, and blocking hard-invariant cases before review reduces reviewer workload rather than adding to it. They do not measure any real model, reviewer, or legal rule set.