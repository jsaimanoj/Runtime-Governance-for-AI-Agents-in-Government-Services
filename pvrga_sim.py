"""PV-RGA design-verification simulator.

Every parameter that shapes the results is in PARAMS below. Each condition
runs in its own fresh environment; common random numbers are drawn once per
scenario so that the Policy-guided and Control-enforced conditions see the
same proposal, the same tool outcome, and the same reviewer draws. That makes
the paired comparison isolate the gate.

Usage:
    python3 pvrga_sim.py            # primary + replication runs, traces,
                                    # sensitivity sweeps, writes results/
"""
import csv
import json
import math
import os
import random
from collections import Counter, defaultdict

FAMILIES = {
    # family: hazard type when the hazard is present
    "consent_privacy": "BLOCK",
    "eligibility_evidence": "BLOCK",
    "tool_privilege": "BLOCK",
    "rights_affecting": "ESCALATE",
    "conflicting_records": "ESCALATE",
    "ordinary_low_risk": None,
}

PARAMS = {
    "scenarios_per_family": 250,
    "hazard_prevalence": 0.60,          # share of scenarios in the five risky families that carry the hazard
    # agent proposal probabilities: (proceed, escalate); decline = remainder
    "baseline_hazard": (0.60, 0.25),
    "baseline_benign": (0.96, 0.03),
    "policy_hazard": (0.25, 0.50),
    "policy_benign": (0.92, 0.06),
    "tool_failure": 0.03,               # execution attempt fails, no side effect
    "gate_miss": 0.02,                  # hazard present but not encoded in the rule set
    "dependency_outage": 0.005,         # governance service unavailable -> fail closed (BLOCK)
    "benign_false_flag": 0.02,          # trusted record wrongly signals a conflict -> ESCALATE
    "review_unresolved": 0.10,          # escalation not decided within the service window
    "approvable_after_review": 0.70,    # ESCALATE-type hazard a reviewer can correctly approve after resolving it
    "reviewer_error": 0.05,             # reviewer reaches the wrong decision on a hazardous case
    "reviewer_benign_reject": 0.03,     # reviewer wrongly rejects a benign case
}


def draws(rng):
    keys = ["hazard", "agent_base", "agent_pol", "tool", "outage", "miss",
            "false_flag", "unresolved", "approvable", "rev"]
    return {k: rng.random() for k in keys}


def make_scenarios(seed, p):
    rng = random.Random(seed)
    out = []
    i = 0
    for fam, htype in FAMILIES.items():
        for _ in range(p["scenarios_per_family"]):
            u = draws(rng)
            hazard = htype is not None and u["hazard"] < p["hazard_prevalence"]
            expected = htype if hazard else "ALLOW"
            out.append({"id": f"S{i:04d}", "family": fam, "hazard": hazard,
                        "htype": htype if hazard else None,
                        "expected": expected, "u": u})
            i += 1
    return out


def agent_proposal(sc, kind, p):
    u = sc["u"]["agent_base" if kind == "baseline" else "agent_pol"]
    key = f"{kind}_{'hazard' if sc['hazard'] else 'benign'}"
    proceed, escalate = p[key]
    if u < proceed:
        return "PROCEED"
    if u < proceed + escalate:
        return "ESCALATE"
    return "DECLINE"


def review(sc, p):
    """Return (approved, unresolved, correct_decision)."""
    u = sc["u"]
    if u["unresolved"] < p["review_unresolved"]:
        return False, True, None
    if not sc["hazard"]:
        correct = True
        approved = u["rev"] >= p["reviewer_benign_reject"]
    else:
        if sc["htype"] == "ESCALATE":
            correct = u["approvable"] < p["approvable_after_review"]
        else:
            correct = False
        wrong = u["rev"] < p["reviewer_error"]
        approved = (not correct) if wrong else correct
    return approved, False, correct


def gate(sc, p, approved=False):
    """Policy decision for one proposed action.

    approved=True means a human reviewer has approved this exact action.
    Approval satisfies an escalation requirement but never overrides a hard
    invariant (BLOCK-type rule) or a fail-closed outage.
    """
    u = sc["u"]
    if u["outage"] < p["dependency_outage"]:
        return "BLOCK", "dependency_unavailable"
    if sc["hazard"]:
        if u["miss"] < p["gate_miss"]:
            return "ALLOW", "rule_gap"
        if sc["htype"] == "BLOCK":
            return "BLOCK", f"{sc['family']}_hard_invariant"
        if approved:
            return "ALLOW", f"{sc['family']}_escalation_satisfied"
        return "ESCALATE", f"{sc['family']}_rule"
    if u["false_flag"] < p["benign_false_flag"]:
        if approved:
            return "ALLOW", "false_flag_escalation_satisfied"
        return "ESCALATE", "false_conflict_flag"
    return "ALLOW", "permitted"


def run_condition(sc, cond, p):
    """Run one scenario in a fresh environment. Returns a trace dict."""
    env = {"side_effect": False}                     # fresh copy per condition
    kind = "baseline" if cond == "baseline" else "policy"
    prop = agent_proposal(sc, kind, p)
    t = {"id": sc["id"], "family": sc["family"], "condition": cond,
         "hazard": sc["hazard"], "expected": sc["expected"], "proposal": prop,
         "gate": None, "gate_reason": None, "gate_final": None,
         "gate_final_reason": None, "reviewed": False,
         "review_unresolved": False, "review_approved": None,
         "review_correct": None, "executed": False, "tool_failed": False}
    gated = cond == "control"
    route = prop
    if gated and prop in ("PROCEED", "ESCALATE"):
        # Every proposal is decided by the gate first, including agent escalations.
        g, why = gate(sc, p)
        t["gate"], t["gate_reason"] = g, why
        if g == "BLOCK":
            route = "STOP"
        elif g == "ESCALATE" or prop == "ESCALATE":
            route = "ESCALATE"          # gate requires review, or agent asked for it
        else:
            route = "PROCEED"
        if route == "PROCEED":
            t["gate_final"], t["gate_final_reason"] = g, why
    approved_by_review = False
    if route == "ESCALATE":
        t["reviewed"] = True
        approved, unresolved, correct = review(sc, p)
        t["review_unresolved"], t["review_approved"] = unresolved, approved
        t["review_correct"] = correct
        if approved:
            route, approved_by_review = "PROCEED", True
            if gated:
                # Check at use: the approved action is decided again before it runs.
                g2, why2 = gate(sc, p, approved=True)
                t["gate_final"], t["gate_final_reason"] = g2, why2
                if g2 != "ALLOW":
                    route = "STOP"
        else:
            route = "STOP"
    if gated and route == "PROCEED":
        assert t["gate_final"] == "ALLOW", f"I1 violated in {sc['id']}"
    if route == "PROCEED":
        if sc["u"]["tool"] < p["tool_failure"]:
            t["tool_failed"] = True
        else:
            env["side_effect"] = True
            t["executed"] = True
    # outcome classification
    safe_after_review = approved_by_review and t["review_correct"] is True
    t["unsafe"] = t["executed"] and sc["hazard"] and not safe_after_review
    can_complete_safely = (not sc["hazard"]) or (
        sc["htype"] == "ESCALATE" and sc["u"]["approvable"] < p["approvable_after_review"])
    t["eligible"] = can_complete_safely
    t["legit_completed"] = t["executed"] and can_complete_safely and not t["unsafe"]
    return t


def summarize(traces, n):
    s = {}
    s["n"] = n
    s["unsafe_proposals"] = sum(1 for t in traces if t["hazard"] and t["proposal"] == "PROCEED")
    s["unsafe_exec"] = sum(t["unsafe"] for t in traces)
    s["completed"] = sum(t["executed"] for t in traces)
    s["eligible"] = sum(t["eligible"] for t in traces)
    s["legit_completed"] = sum(t["legit_completed"] for t in traces)
    benign = [t for t in traces if not t["hazard"]]
    s["benign"] = len(benign)
    s["false_blocks"] = sum(1 for t in benign if t["gate"] == "BLOCK")
    s["benign_not_completed"] = sum(1 for t in benign if not t["executed"])
    esc = [t for t in traces if t["reviewed"]]
    s["escalations"] = len(esc)
    s["unnecessary_escalations"] = sum(1 for t in esc if not t["hazard"])
    s["unresolved"] = sum(t["review_unresolved"] for t in esc)
    esc_type = [t for t in traces if t["expected"] == "ESCALATE"]
    # escalation precision: share of escalated cases that were hazardous (reported in the paper)
    s["esc_precision"] = (sum(1 for t in esc if t["hazard"]) / len(esc)) if esc else float("nan")
    # narrower diagnostic: share of escalated cases whose expected disposition is ESCALATE
    s["esc_share_escalation_type"] = (sum(1 for t in esc if t["expected"] == "ESCALATE") / len(esc)) if esc else float("nan")
    # escalation recall: share of escalation-type hazards that reached a reviewer
    s["esc_recall"] = (sum(1 for t in esc_type if t["reviewed"]) / len(esc_type)) if esc_type else float("nan")
    gated_exec = [t for t in traces if t["condition"] == "control" and t["executed"]]
    s["executions_without_gate_allow"] = sum(1 for t in gated_exec if t["gate_final"] != "ALLOW")
    return s


def wilson(k, n, z=1.959964):
    if n == 0:
        return (float("nan"), float("nan"))
    ph = k / n
    d = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / d
    h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def exact_mcnemar(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def run(seed, p=PARAMS):
    scs = make_scenarios(seed, p)
    out = {c: [run_condition(sc, c, p) for sc in scs] for c in ("baseline", "policy", "control")}
    return scs, out


def per_family(traces):
    by = defaultdict(list)
    for t in traces:
        by[t["family"]].append(t)
    return {f: summarize(ts, len(ts)) for f, ts in by.items()}


def main():
    os.makedirs("results", exist_ok=True)
    report = {"params": PARAMS, "runs": {}}
    for label, seed in (("primary", 20261102), ("replication", 20261103)):
        scs, out = run(seed)
        n = len(scs)
        summ = {c: summarize(ts, n) for c, ts in out.items()}
        fam = {c: per_family(ts) for c, ts in out.items()}
        P, C = out["policy"], out["control"]
        b = sum(1 for x, y in zip(P, C) if x["unsafe"] and not y["unsafe"])
        rev = sum(1 for x, y in zip(P, C) if y["unsafe"] and not x["unsafe"])
        both = sum(1 for x, y in zip(P, C) if x["unsafe"] and y["unsafe"])
        residual = [y for y in C if y["unsafe"]]
        cause = Counter()
        res_rows = []
        for y in residual:
            if y["gate_final_reason"] == "rule_gap":
                why = "gate rule gap (hazard not encoded)"
            elif y["reviewed"] and y["review_approved"]:
                why = "reviewer wrongly approved an escalation-type case"
            else:
                why = "other"
            cause[why] += 1
            res_rows.append({"id": y["id"], "family": y["family"], "proposal": y["proposal"],
                             "gate": y["gate"], "gate_final": y["gate_final"],
                             "gate_final_reason": y["gate_final_reason"],
                             "reviewed": y["reviewed"], "cause": why})
        blocked_after_approval = [y for y in C if y["review_approved"] and y["gate_final"] == "BLOCK"]
        report["runs"][label] = {
            "seed": seed, "summary": summ, "per_family": fam,
            "paired": {"policy_unsafe_control_safe": b, "control_unsafe_policy_safe": rev,
                       "both_unsafe": both, "exact_mcnemar_p": exact_mcnemar(b, rev)},
            "residual_causes": dict(cause), "residual_traces": res_rows,
            "approvals_blocked_by_hard_invariant": len(blocked_after_approval),
            "approvals_blocked_ids": [y["id"] for y in blocked_after_approval],
            "control_executions": sum(y["executed"] for y in C),
            "control_executions_without_gate_allow": summ["control"]["executions_without_gate_allow"],
        }
        with open(f"results/traces_{label}.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(out["control"][0].keys()))
            w.writeheader()
            for c in ("baseline", "policy", "control"):
                w.writerows(out[c])
    # 100-seed distribution
    dist = defaultdict(list)
    for s in range(1000, 1100):
        scs, out = run(s)
        n = len(scs)
        for c in out:
            sm = summarize(out[c], n)
            dist[c + "_unsafe"].append(sm["unsafe_exec"] / n)
            dist[c + "_legit"].append(sm["legit_completed"] / sm["eligible"])
    report["seed_distribution_100"] = {
        k: {"mean": sum(v) / len(v), "sd": (sum((x - sum(v) / len(v)) ** 2 for x in v) / (len(v) - 1)) ** 0.5,
            "min": min(v), "max": max(v)} for k, v in dist.items()}
    # sensitivity sweeps (20 seeds each, mean)
    sweeps = {
        "gate_miss": [0.0, 0.02, 0.05, 0.10, 0.20],
        "reviewer_error": [0.0, 0.05, 0.10, 0.20, 0.30],
        "review_unresolved": [0.0, 0.10, 0.20, 0.30],
        "benign_false_flag": [0.0, 0.02, 0.05, 0.10],
        "policy_hazard": [(0.10, 0.60), (0.25, 0.50), (0.40, 0.40)],
    }
    sens = {}
    for param, values in sweeps.items():
        rows = []
        for v in values:
            p = dict(PARAMS)
            p[param] = v
            acc = defaultdict(float)
            for s in range(2000, 2020):
                scs, out = run(s, p)
                n = len(scs)
                sp, sc_ = summarize(out["policy"], n), summarize(out["control"], n)
                acc["policy_unsafe"] += sp["unsafe_exec"] / n / 20
                acc["control_unsafe"] += sc_["unsafe_exec"] / n / 20
                acc["policy_legit"] += sp["legit_completed"] / sp["eligible"] / 20
                acc["control_legit"] += sc_["legit_completed"] / sc_["eligible"] / 20
                acc["control_esc_per_1000"] += sc_["escalations"] / n * 1000 / 20
            acc["relative_reduction"] = 1 - acc["control_unsafe"] / acc["policy_unsafe"]
            rows.append({"value": v if not isinstance(v, tuple) else v[0], **acc})
        sens[param] = rows
    report["sensitivity"] = sens
    with open("results/report.json", "w") as f:
        json.dump(report, f, indent=1, default=str)
    print(json.dumps({k: report["runs"][k]["summary"] for k in report["runs"]}, indent=1))


if __name__ == "__main__":
    main()
