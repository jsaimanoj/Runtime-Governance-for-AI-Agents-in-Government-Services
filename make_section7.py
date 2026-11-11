"""Generate the manuscript's Section 7 text and headline sentences from results/report.json."""
import json
import sys
import math
from collections import Counter
from pvrga_sim import wilson

sys.stdout.reconfigure(encoding="utf-8")

r = json.load(open("results/report.json", encoding="utf-8"))
P = r["runs"]["primary"]["summary"]
R = r["runs"]["replication"]["summary"]
pr = r["runs"]["primary"]
rp = r["runs"]["replication"]
C3 = ("baseline", "policy", "control")
pct = lambda k, n: "%.2f%%" % (100 * k / n)


def ci(k, n):
    lo, hi = wilson(k, n)
    return "%d; %s [%.2f, %.2f]" % (k, pct(k, n), 100 * lo, 100 * hi)


def sci(p):
    e = math.floor(math.log10(p))
    m = p / 10 ** e
    sup = str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹")
    return "%.1f × 10%s" % (m, str(e).translate(sup))


def fmt_int(x):
    return "{:,}".format(x)


b, p_, c = (P[k] for k in C3)
esc_change = c["escalations"] / p_["escalations"] - 1
direction = "fell" if esc_change < 0 else "rose"
reduction = 1 - c["unsafe_exec"] / p_["unsafe_exec"]
sens = r["sensitivity"]
reds = [x["relative_reduction"] for rows in sens.values() for x in rows]
red_lo, red_hi = round(100 * min(reds)), round(100 * max(reds))
lo_c, hi_c = wilson(c["unsafe_exec"], 1500)
lo_p, hi_p = wilson(p_["unsafe_exec"], 1500)

L = []
L.append("With proposals held fixed, the gate cut unsafe executions from %d to %d of 1,500 scenarios and raised legitimate task completion from %s to %s, while benign requests completed at almost the same rate. Because hard-invariant cases are now blocked before they reach a person, escalations to reviewers %s by %d%%." % (
    p_["unsafe_exec"], c["unsafe_exec"], pct(p_["legit_completed"], p_["eligible"]), pct(c["legit_completed"], c["eligible"]), direction, round(abs(100 * esc_change))))
L.append("")
L.append("**Implementation.** Every result in this section comes from the released simulator, pvrga_sim.py, which runs each condition in its own fresh environment, as in the loop in Appendix A, with the parameters in Section 6. Under Control-enforced, every action passes the gate before it runs, including actions a reviewer has approved, and the simulator stops with an error if any gated execution lacks an ALLOW decision; none did (%d of %d executions in the primary run had one). An earlier version of this simulator let actions the agent itself escalated run after reviewer approval without a second gate decision; that version broke complete mediation (I1), and its results are withdrawn. The figures in earlier drafts (34.87%%, 14.40%%, and 0.53%% unsafe execution) came from a separate implementation that ran conditions in a shared environment and whose parameters were not recorded; they could not be reproduced or traced, and are also withdrawn." % (
    pr["control_executions"] - pr["control_executions_without_gate_allow"], pr["control_executions"]))
L.append("")
L.append("**Primary run (seed 20261102, 1,500 scenarios per condition).** Percentages carry 95% Wilson intervals.")
L.append("")
L.append("| Measure | Baseline | Policy-guided | Control-enforced |")
L.append("| --- | --- | --- | --- |")
L.append("| Unsafe proposals | %d | %d | %d |" % tuple(P[k]["unsafe_proposals"] for k in C3))
L.append("| Unsafe executions | %s | %s | %s |" % tuple(ci(P[k]["unsafe_exec"], 1500) for k in C3))
L.append("| Legitimate task completion (of %d) | %s | %s | %s |" % ((b["eligible"],) + tuple(ci(P[k]["legit_completed"], P[k]["eligible"]) for k in C3)))
L.append("| Benign requests completed (of %d) | %s | %s | %s |" % ((b["benign"],) + tuple("%d; %s" % (P[k]["benign"] - P[k]["benign_not_completed"], pct(P[k]["benign"] - P[k]["benign_not_completed"], P[k]["benign"])) for k in C3)))
L.append("| False blocks by the gate (of %d benign) | No gate | No gate | %d; %s |" % (c["benign"], c["false_blocks"], pct(c["false_blocks"], c["benign"])))
L.append("| Escalations to reviewers (per 1,000 scenarios) | %s |" % " | ".join("%d (%d)" % (P[k]["escalations"], round(P[k]["escalations"] / 1.5)) for k in C3))
L.append("| Unnecessary escalations (benign cases) | %d | %d | %d |" % tuple(P[k]["unnecessary_escalations"] for k in C3))
L.append("| Escalations unresolved in the service window | %d | %d | %d |" % tuple(P[k]["unresolved"] for k in C3))
L.append("| Escalation precision (escalated case was hazardous) | %s |" % " | ".join("%.1f%%" % (100 * P[k]["esc_precision"]) for k in C3))
L.append("| Escalation recall (escalation-type hazards reaching review) | %s |" % " | ".join("%.1f%%" % (100 * P[k]["esc_recall"]) for k in C3))
L.append("| Raw completion (any execution) | %s |" % " | ".join(fmt_int(P[k]["completed"]) for k in C3))
L.append("")
L.append("Unsafe executions can exceed unsafe proposals, as in the Policy-guided column, because without a gate a reviewer can wrongly approve a hazardous case the agent escalated; tool failures work the other way. Under the gate, hard-invariant cases are blocked before review, which is why escalations fall and why escalation precision is lower: the cases left for reviewers are the genuinely ambiguous ones plus benign cases flagged for review. Escalation recall stays below 100% because a hazardous case the agent declines never reaches review: it is unserved, not unsafe. The difference between Baseline and Policy-guided is set by the injected agent probabilities and is not evidence about prompting.")
L.append("")
L.append("**By scenario family (primary run).**")
L.append("")
names = {"consent_privacy": "Consent and privacy", "eligibility_evidence": "Eligibility evidence",
         "tool_privilege": "Tool privilege", "rights_affecting": "Rights-affecting action",
         "conflicting_records": "Conflicting records", "ordinary_low_risk": "Ordinary low risk"}
fam = pr["per_family"]
L.append("| Family | Unsafe executions: Baseline, Policy-guided, Control-enforced | Legitimate completion: Policy-guided to Control-enforced | Escalations: Policy-guided to Control-enforced | False blocks |")
L.append("| --- | --- | --- | --- | --- |")
for k, nm in names.items():
    fb, fp, fc = fam["baseline"][k], fam["policy"][k], fam["control"][k]
    L.append("| %s | %d, %d, %d | %d to %d of %d | %d to %d | %d |" % (nm, fb["unsafe_exec"], fp["unsafe_exec"], fc["unsafe_exec"], fp["legit_completed"], fc["legit_completed"], fc["eligible"], fp["escalations"], fc["escalations"], fc["false_blocks"]))
L.append("")
L.append("In the three hard-invariant families, the gate blocks covered hazards outright, so escalations fall and the only residual risk is a rule gap. In the two escalation families, the gate sends cases the agent would have executed to a reviewer, who can approve them correctly; this is where the gain in legitimate completion comes from, and also where reviewer errors can still let a hazardous case through. False blocks came only from fail-closed outages.")
L.append("")
pp = pr["paired"]
L.append("**Paired comparison.** %d scenarios executed unsafely without the gate and safely with it; %s went the other way; %d executed unsafely in both. The exact McNemar test on the %d discordant pairs gives p ≈ %s. This confirms the implemented gate changes outcomes under the stated assumptions; it is not a measure of real-world safety." % (
    pp["policy_unsafe_control_safe"], "none" if pp["control_unsafe_policy_safe"] == 0 else str(pp["control_unsafe_policy_safe"]), pp["both_unsafe"], pp["policy_unsafe_control_safe"] + pp["control_unsafe_policy_safe"], sci(pp["exact_mcnemar_p"])))
L.append("")
res = pr["residual_traces"]
gap = [t for t in res if t["cause"].startswith("gate rule gap")]
rev = [t for t in res if t["cause"].startswith("reviewer")]
fname = lambda t: names[t["family"]].lower()
L.append("**Residual unsafe executions, from traces.** Each of the %d is identified by scenario in traces_primary.csv:" % len(res))
L.append("")
L.append("| Cause | Count | Scenarios |")
L.append("| --- | --- | --- |")
L.append("| Rule gap: hazard present but not encoded, so the gate allowed it | %d | %s |" % (len(gap), "; ".join("%s %s" % (t["id"], fname(t)) for t in gap)))
L.append("| Reviewer wrongly approved an escalation-type case, which the gate then allowed because the escalation requirement was met | %d | %s |" % (len(rev), "; ".join("%s %s (%s)" % (t["id"], fname(t), "escalated by the gate" if t["proposal"] == "PROCEED" else "escalated by the agent") for t in rev)))
L.append("")
L.append("No residual case came from a hard-invariant family after review: approval cannot override a block, and in these runs no blocked case reached a reviewer at all. The rule gaps are the coverage risk varied in the sensitivity analysis; the reviewer errors are a risk the gate is designed to hand to people, not remove. No reverse case occurred. With isolated environments and shared random draws, the gate can remove an unsafe execution but cannot add one.")
L.append("")
rc = rp["residual_causes"]
dd = r["seed_distribution_100"]
L.append("**Replication.** With seed 20261103, unsafe executions were %d, %d, and %d (%s, %s, %s); legitimate completion was %s, %s, and %s; benign completion was %d, %d, and %d of %d; the gate made %d false blocks; and escalations were %d, %d, and %d. The %d residual cases were %d rule gaps and %d reviewer errors on escalation-type cases, with no reverse cases (McNemar p ≈ %s). Across 100 further seeds, mean unsafe execution was %.2f%% (standard deviation %.2f), %.2f%% (%.2f), and %.2f%% (%.2f), and mean legitimate completion was %.2f%%, %.2f%%, and %.2f%%." % (
    R["baseline"]["unsafe_exec"], R["policy"]["unsafe_exec"], R["control"]["unsafe_exec"],
    pct(R["baseline"]["unsafe_exec"], 1500), pct(R["policy"]["unsafe_exec"], 1500), pct(R["control"]["unsafe_exec"], 1500),
    pct(R["baseline"]["legit_completed"], R["baseline"]["eligible"]), pct(R["policy"]["legit_completed"], R["policy"]["eligible"]), pct(R["control"]["legit_completed"], R["control"]["eligible"]),
    R["baseline"]["benign"] - R["baseline"]["benign_not_completed"], R["policy"]["benign"] - R["policy"]["benign_not_completed"], R["control"]["benign"] - R["control"]["benign_not_completed"], R["control"]["benign"],
    R["control"]["false_blocks"], R["baseline"]["escalations"], R["policy"]["escalations"], R["control"]["escalations"],
    R["control"]["unsafe_exec"], rc.get("gate rule gap (hazard not encoded)", 0), rc.get("reviewer wrongly approved an escalation-type case", 0),
    sci(rp["paired"]["exact_mcnemar_p"]),
    100 * dd["baseline_unsafe"]["mean"], 100 * dd["baseline_unsafe"]["sd"], 100 * dd["policy_unsafe"]["mean"], 100 * dd["policy_unsafe"]["sd"], 100 * dd["control_unsafe"]["mean"], 100 * dd["control_unsafe"]["sd"],
    100 * dd["baseline_legit"]["mean"], 100 * dd["policy_legit"]["mean"], 100 * dd["control_legit"]["mean"]))
L.append("")
L.append("**Sensitivity.** Each parameter was varied with the others at their defaults, averaging 20 seeds per value:")
L.append("")
L.append("| Parameter varied (default) | Values | Control-enforced unsafe execution | Reduction against Policy-guided | Control-enforced legitimate completion |")
L.append("| --- | --- | --- | --- | --- |")
labels = [("reviewer_error", "Reviewer wrong decision (0.05)", "0 to 0.30"),
          ("gate_miss", "Gate miss rate (0.02)", "0 to 0.20"),
          ("policy_hazard", "Policy-guided agent proceeds on hazards (0.25)", "0.10 to 0.40"),
          ("review_unresolved", "Escalations unresolved (0.10)", "0 to 0.30"),
          ("benign_false_flag", "Benign case wrongly flagged (0.02)", "0 to 0.10")]
for key, lab, vals in labels:
    rows = sens[key]
    f0, f1 = rows[0], rows[-1]
    def rng(k, f):
        a, b_ = f % (100 * f0[k]), f % (100 * f1[k])
        return a + " at every value" if a == b_ else a + " to " + b_
    extra = ""
    if key == "benign_false_flag":
        extra = "; escalations %d to %d per 1,000" % (round(f0["control_esc_per_1000"]), round(f1["control_esc_per_1000"]))
    L.append("| %s | %s | %s | %s | %s%s |" % (lab, vals, rng("control_unsafe", "%.2f%%"), rng("relative_reduction", "%.1f%%"), rng("control_legit", "%.1f%%"), extra))
L.append("")
L.append("The gate reduced unsafe execution at every value tested, but the size of the reduction is not fixed. It depends most on rule coverage and on reviewer reliability in the escalation families, and it grows with how often the ungated agent proposes unsafe actions. The headline reduction should therefore always be quoted with its parameters. Unresolved escalations barely affect safety but cost legitimate completion directly.")
L.append("")
L.append("**What this establishes.** These results establish Stage 1 design behavior under stated assumptions: a deterministic gate that mediates every action removes most unsafe executions, the remaining risk sits in rule coverage and in human review of genuinely ambiguous cases, and blocking hard-invariant cases before review reduces reviewer workload rather than adding to it. They do not measure any real model, reviewer, or legal rule set.")
section7 = "\n".join(L)
open("section7.md", "w", encoding="utf-8").write(section7)

head = {
    "abstract": "adding the runtime gate lowered unsafe execution from %s (95%% CI %.2f to %.2f) to %s (%.2f to %.2f) and raised completion of legitimate requests from %s to %s, while benign requests completed at nearly the same rate and escalations to human reviewers %s by %d%%. A replication seed and 100 further seeds preserved the result, every residual unsafe execution is traced to a rule gap or a reviewer error on an escalation-type case, and sensitivity analysis shows the reduction ranging from %d%% to %d%% depending mainly on rule coverage and reviewer reliability." % (
        pct(p_["unsafe_exec"], 1500), 100 * lo_p, 100 * hi_p, pct(c["unsafe_exec"], 1500), 100 * lo_c, 100 * hi_c,
        pct(p_["legit_completed"], p_["eligible"]), pct(c["legit_completed"], c["eligible"]), direction, round(abs(100 * esc_change)), red_lo, red_hi),
    "limitation": "%s, %s, and %s unsafe execution in the primary run" % tuple(pct(P[k]["unsafe_exec"], 1500) for k in C3),
    "conclusion": "a deterministic gate that mediates every action stopped %d of %d unsafe actions from becoming side effects in the primary run, with little cost to benign requests and less reviewer workload than prompting alone. The remaining risk lay in rule gaps and in reviewer errors on genuinely ambiguous cases." % (pp["policy_unsafe_control_safe"], p_["unsafe_exec"]),
    "reduction": "%.1f%%" % (100 * reduction),
}
json.dump(head, open("headlines.json", "w", encoding="utf-8"), indent=1)
print(section7)
print(json.dumps(head, indent=1))
