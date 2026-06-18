"""Day 1 + Day 2 deliverable: run every reasoning prompt against the Adam scenario.

Run:  ./.venv/Scripts/python.exe test_prompts.py

Day 1 (live):   assumption extraction, pre-mortem.
Day 2 (Session 1, live chain): extraction + pre-mortem -> merge -> risk ranking
                -> test design. Proves the real pipeline flows end to end.
Day 2 (Sessions 2/3, fixtures): evidence interpretation, persevere/pivot, and the
                session briefing run off small hand-authored state dicts. Those
                fixtures double as the documented input contract that memory.py
                (Person A) will satisfy.

Each section prints the model output, then a `>>` line asserting the key Adam
beat was caught (mirroring the Day-1 "buried pain caught: YES/NO" check).
"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

from llm import ask, parse_json
from prompts import (
    ADAM_SESSION_1, ADAM_SESSION_2, ADAM_SESSION_3,
    ASSUMPTION_EXTRACTION, PRE_MORTEM, RISK_RANKING, TEST_DESIGN,
    EVIDENCE_INTERPRETATION, PERSEVERE_PIVOT, SESSION_BRIEFING,
)


def header(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def has_any(blob: str, keywords) -> bool:
    blob = blob.lower()
    return any(k in blob for k in keywords)


# ---------------------------------------------------------------------------
# Day 1 — assumption extraction + pre-mortem (live)
# ---------------------------------------------------------------------------
def run_assumptions() -> list[dict]:
    header("PROMPT 1 — ASSUMPTION EXTRACTION")
    items = parse_json(ask(ASSUMPTION_EXTRACTION, ADAM_SESSION_1))["assumptions"]
    for i, a in enumerate(items, 1):
        print(f"\n{i}. [{a['fatal_if_false'].upper()}] {a['belief']}")
        print(f"   why it matters: {a['why_load_bearing']}")

    blob = json.dumps(items).lower()
    caught = has_any(blob, ("real pain", "primary pain", "actually hard", "hard to find",
                            "finding a job", "even a problem", "is finding", "discovery",
                            "the hard part", "bottleneck"))
    print(f"\n>> {len(items)} assumptions extracted.")
    print(f">> Buried 'is finding a job even the real pain?' caught: "
          f"{'YES' if caught else 'NO — needs another iteration'}")
    return items


def run_premortem() -> list[dict]:
    header("PROMPT 2 — PRE-MORTEM")
    failures = parse_json(ask(PRE_MORTEM, ADAM_SESSION_1))["failures"]
    for i, f in enumerate(failures, 1):
        print(f"\n{i}. FAILURE: {f['failure_mode']}")
        print(f"   -> TEST:  {f['testable_assumption']}")

    banned = ["ran out of money", "ran out of runway", "poor marketing",
              "team disagree", "bad execution", "didn't raise", "funding"]
    hits = [b for b in banned if b in json.dumps(failures).lower()]
    print(f"\n>> {len(failures)} failure modes generated.")
    print(f">> Generic-advice leakage: {', '.join(hits) if hits else 'none — all idea-specific'}")
    return failures


# ---------------------------------------------------------------------------
# Day 2, Session 1 — risk ranking + test design (live, chained off the above)
# ---------------------------------------------------------------------------
def merge_assumptions(extracted: list[dict], failures: list[dict]) -> list[dict]:
    """Lightweight stand-in for memory.add_assumptions: merge the extraction set
    with the pre-mortem's testable assumptions and assign ids + Untested tiers."""
    merged: list[dict] = []
    seen: set[str] = set()
    for a in extracted:
        key = a["belief"].strip().lower()
        if key in seen:
            continue
        seen.add(key)
        merged.append({"belief": a["belief"], "why_load_bearing": a["why_load_bearing"],
                       "fatal_if_false": a["fatal_if_false"], "tier": "Untested"})
    for f in failures:
        key = f["testable_assumption"].strip().lower()
        if key in seen:
            continue
        seen.add(key)
        merged.append({"belief": f["testable_assumption"],
                       "why_load_bearing": f["failure_mode"],
                       "fatal_if_false": "high", "tier": "Untested"})
    for i, a in enumerate(merged, 1):
        a["id"] = f"a{i}"
    return merged


def run_risk_ranking(assumptions: list[dict]) -> dict:
    header("PROMPT 3 — RISK RANKING (RAT)")
    payload = json.dumps({"idea": ADAM_SESSION_1, "assumptions": assumptions})
    data = parse_json(ask(RISK_RANKING, payload))
    for r in sorted(data["ranking"], key=lambda x: int(x["rank"])):
        print(f"\n#{r['rank']} [{r['fatal_if_false'].upper()} / {r['evidence_status']}] {r['belief']}")
        print(f"   why: {r['risk_reasoning']}")
    print(f"\n>> RISKIEST: {data['riskiest_belief']}")
    print(f">> why: {data['why_riskiest']}")

    finding = has_any(data["riskiest_belief"], ("find", "finding", "discover", "search",
                                                "the hard part", "real pain", "primary pain"))
    print(f">> Riskiest is the 'finding-pain' belief: "
          f"{'YES' if finding else 'NO — check the ranking'}")
    return data


def run_test_design(riskiest_belief: str) -> dict:
    header("PROMPT 4 — TEST DESIGN")
    payload = json.dumps({"idea": ADAM_SESSION_1, "riskiest_assumption": riskiest_belief})
    data = parse_json(ask(TEST_DESIGN, payload))
    print(f"\nCHEAPEST TEST: {data['cheapest_test']}")
    print("\nINTERVIEW SCRIPT (must be non-leading):")
    for q in data["interview_script"]:
        print(f"   - {q}")
    fd = data["fake_door"]
    print(f"\nFAKE DOOR: {fd['headline']} / {fd['subhead']} [{fd['cta']}]")
    print(f"   a signup means: {fd['what_a_signup_means']}")
    print(f"\nWHAT WOULD FALSIFY: {data['what_would_falsify']}")
    print(f"KILL CRITERION:     {data['suggested_kill_criterion']}")

    # Heuristic non-leading check: flag hypothetical-enthusiasm phrasing.
    leading = [q for q in data["interview_script"]
               if has_any(q, ("would you use", "would you pay", "do you think you'd",
                               "an app that", "our app", "this app", "my app"))]
    print(f"\n>> {len(data['interview_script'])} interview questions; "
          f"leading/hypothetical ones: {len(leading)} (want 0)")
    print(f">> Kill criterion present: {'YES' if data.get('suggested_kill_criterion') else 'NO'}")
    if leading:
        for q in leading:
            print(f"   LEADING: {q}")
    return data


# ---------------------------------------------------------------------------
# Day 2, Session 2 — evidence interpretation + persevere/pivot (fixtures)
# ---------------------------------------------------------------------------
# Post-Session-1 ledger state (what memory.py would hold). Kept small + stable so
# the Session-2/3 prompts get a deterministic input. The finding-pain assumption
# is a1 — the one the Adam evidence should weaken to Weak signal.
POST_S1_ASSUMPTIONS = [
    {"id": "a1", "belief": "Students find it genuinely hard to find a part-time job "
                           "that fits around their class timetable.", "tier": "Untested"},
    {"id": "a2", "belief": "Schedule clash is the primary pain in student part-time "
                           "work, ahead of pay, location, or job type.", "tier": "Untested"},
    {"id": "a3", "belief": "Students would switch from Indeed / the college job board / "
                           "group chats to a new timetable-matching app.", "tier": "Untested"},
    {"id": "a4", "belief": "Employers would list jobs on a student-specific, "
                           "timetable-aware platform.", "tier": "Untested"},
]


def run_evidence_interpretation() -> dict:
    header("PROMPT 5 — EVIDENCE INTERPRETATION + TIER (Session 2)")
    payload = json.dumps({"assumptions": POST_S1_ASSUMPTIONS, "evidence_text": ADAM_SESSION_2})
    data = parse_json(ask(EVIDENCE_INTERPRETATION, payload))
    print(f"\nSUMMARY: {data['evidence_summary']}")
    print("\nTIER UPDATES:")
    for u in data["assumption_updates"]:
        print(f"   [{u['id']}] {u['old_tier']} -> {u['new_tier']}: {u['belief']}")
        print(f"        because: {u['reasoning']}")
    print("\nFALSE-POSITIVE FLAGS:")
    for f in data["false_positive_flags"]:
        print(f"   - {f['concern']}: {f['why']}")
    print("\nNEW ASSUMPTIONS THAT EMERGED:")
    for n in data["new_assumptions"]:
        print(f"   - [{n['fatal_if_false'].upper()}] {n['belief']}")

    a1 = next((u for u in data["assumption_updates"] if u["id"] == "a1"), None)
    weakened = bool(a1) and a1["new_tier"] in ("Weak signal", "Contested")
    fp_blob = json.dumps(data["false_positive_flags"]).lower()
    friend_flag = has_any(fp_blob, ("jordan", "sam", "friend", "coursemate", "course mate",
                                    "knew them", "biased sample", "on my course"))
    posthire = has_any(json.dumps(data["new_assumptions"]).lower(),
                       ("after", "hired", "post-hire", "shift", "swap", "roster", "exam"))
    print(f"\n>> Finding-pain assumption (a1) weakened to Weak signal/Contested: "
          f"{'YES' if weakened else 'NO'}" + (f" (got {a1['new_tier']})" if a1 else " (a1 missing)"))
    print(f">> Friend-bias false positive (Jordan/Sam) flagged: {'YES' if friend_flag else 'NO'}")
    print(f">> Post-hire pain surfaced as a new assumption: {'YES' if posthire else 'NO'}")
    return data


def run_persevere_pivot() -> dict:
    header("PROMPT 6 — PERSEVERE / PIVOT / STOP (Session 2 decision moment)")
    payload = json.dumps({
        "idea": ADAM_SESSION_1,
        "riskiest_assumption": {
            "belief": POST_S1_ASSUMPTIONS[0]["belief"], "tier": "Weak signal"},
        "key_evidence": "5 of 7 interviewees said finding a job isn't the hard part and "
                        "they cope with Indeed / the job board / group chats. The only 2 "
                        "keen responses were Jordan and Sam, coursemates and friends. "
                        "Landing page: 2 signups from 60 visitors. 3 people independently "
                        "raised a different, unserved pain: managing shifts AFTER being "
                        "hired (exam-week rostering, swapping shifts).",
        "kill_criteria_status": "Kill criterion was: if 4+ of 7 interviewees say finding a "
                                "job isn't a real pain, treat finding-pain as falsified. "
                                "5 of 7 said exactly that — criterion crossed.",
        "emerged_assumptions": [
            "The real unserved pain is post-hire shift management (swapping shifts, "
            "exam-week availability); incumbents stop being useful the second you're hired."],
    })
    data = parse_json(ask(PERSEVERE_PIVOT, payload))
    print(f"\nSITUATION: {data['situation']}")
    print(f"\nKILL-CRITERIA STATUS: {data['kill_criteria_status']}")
    print(f"\nCASE FOR PERSEVERE: {data['case_for_persevere']}")
    print(f"\nCASE FOR PIVOT:     {data['case_for_pivot']}")
    if data.get("case_for_stop"):
        print(f"\nCASE FOR STOP:      {data['case_for_stop']}")
    print(f"\nYOUR CALL: {data['this_is_your_call']}")

    both_sides = bool(data.get("case_for_persevere", "").strip()) and \
        bool(data.get("case_for_pivot", "").strip())
    hands_off = has_any(data.get("this_is_your_call", ""),
                        ("your call", "you decide", "you can decide", "only you",
                         "not a verdict", "does not decide", "decision input", "up to you",
                         "not choosing for you", "is not choosing", "the decision requires you",
                         "not a recommendation"))
    # No verdict should leak: Pulse must not say "you should pivot/persevere".
    verdict_leak = has_any(json.dumps(data).lower(),
                           ("we recommend", "you should pivot", "you should persevere",
                            "you should stop", "i recommend", "the right choice is"))
    print(f"\n>> Both sides steelmanned (persevere AND pivot non-empty): "
          f"{'YES' if both_sides else 'NO'}")
    print(f">> Hands the decision to the founder (no verdict): "
          f"{'YES' if hands_off and not verdict_leak else 'NO'}")
    return data


# ---------------------------------------------------------------------------
# Day 2, Session 3 — the session briefing money shot (fixture w/ change-detector diff)
# ---------------------------------------------------------------------------
def run_session_briefing() -> dict:
    header("PROMPT 7 — SESSION BRIEFING (Session 3 — the continuity 'money shot')")
    payload = json.dumps({
        "idea": ADAM_SESSION_3,
        "diff": {
            "idea_changed": True,
            "idea_before": ADAM_SESSION_1,
            "tier_changes": [{
                "belief": POST_S1_ASSUMPTIONS[0]["belief"],
                "from": "Untested", "to": "Weak signal", "direction": "down"}],
            "new_assumptions": [{
                "belief": "Employed students actively want a third-party tool to swap "
                          "shifts and manage availability around exams."}],
            "new_evidence": ["7 interviews (5 dismissive), 2/60 landing-page signups, "
                             "3 people independently raised post-hire pain"],
        },
        "assumptions": [
            {"belief": POST_S1_ASSUMPTIONS[0]["belief"], "tier": "Weak signal",
             "why_tier": "5 of 7 interviewees said finding a job isn't the hard part."},
            {"belief": "Employed students actively want a third-party tool to swap shifts "
                       "and manage availability around exams.", "tier": "Untested",
             "why_tier": "Raised unprompted by 3 people; no test run yet."},
        ],
        "riskiest": {
            "belief": "Employed students actively want a third-party tool to swap shifts "
                      "and manage availability around exams (vs. just grumbling and "
                      "absorbing it).", "tier": "Untested"},
        "kill_criteria_status": "Finding-pain kill criterion was crossed (5 of 7); that "
                                "direction is parked. No kill criterion set yet on the "
                                "new post-hire direction.",
    })
    data = parse_json(ask(SESSION_BRIEFING, payload))
    print(f"\nWHERE IT STANDS: {data['where_it_stands']}")
    print(f"\nWHAT CHANGED:    {data['what_changed']}")
    print("\nRISK PICTURE:")
    for r in data["risk_picture"]:
        print(f"   [{r['tier']}] {r['belief']}")
        print(f"        why: {r['why_tier']}")
    m = data["the_one_move"]
    print(f"\nTHE ONE MOVE: {m['action']}")
    print(f"   targets:  {m['assumption_targeted']}")
    print(f"   reasoning: {m['reasoning']}")
    print(f"   expected signal: {m['expected_signal']}")
    print(f"\nDECISION MOMENT: {data.get('decision_moment')}")

    blob = json.dumps(data).lower()
    reconstructs = has_any(blob, ("last session", "two weeks", "previously", "earlier",
                                  "pushed", "weak signal", "started", "originally"))
    pivot_named = has_any(blob, ("post-hire", "after you", "after being hired", "shift",
                                 "swap", "roster", "exam"))
    one_move = bool(m.get("action", "").strip())
    print(f"\n>> Reconstructs the arc (references the journey/prior state): "
          f"{'YES' if reconstructs else 'NO'}")
    print(f">> Names the post-hire pivot + new riskiest assumption: "
          f"{'YES' if pivot_named else 'NO'}")
    print(f">> Gives exactly one next move: {'YES' if one_move else 'NO'}")
    return data


if __name__ == "__main__":
    # Session 1 — live chain through the real pipeline.
    extracted = run_assumptions()
    failures = run_premortem()
    merged = merge_assumptions(extracted, failures)
    ranking = run_risk_ranking(merged)
    run_test_design(ranking["riskiest_belief"])

    # Session 2 — evidence comes in; tiers update; the decision moment appears.
    run_evidence_interpretation()
    run_persevere_pivot()

    # Session 3 — the continuity briefing after Adam pivots.
    run_session_briefing()

    print("\n" + "=" * 70)
    print("All 7 prompts exercised against the Adam scenario.")
    print("=" * 70)
