"""Full-infrastructure integration test: memory layer ⇄ reasoning prompts.

test_memory.py proves the deterministic layer in isolation; test_prompts.py
proves each prompt against its own fixtures. Neither proves the *seam* — that
Person A's memory.py and Person B's prompts.py actually interlock. This does:
real LLM output flows INTO the ledger and ledger state flows BACK OUT to the
prompts, with the change-detector observing changes driven by live reasoning.

Two live API calls (risk-ranking + evidence-interpretation). Run:
  ./.venv/Scripts/python.exe test_integration.py
"""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

import change_detector
import memory
from llm import ask, parse_json
from prompts import ADAM_SESSION_2, EVIDENCE_INTERPRETATION, RISK_RANKING

# Seeded Session-1 assumptions in memory's own shape (the finding-pain one is a1,
# the belief Adam's Session-2 evidence should weaken).
S1_ASSUMPTIONS = [
    {"belief": "Students find it genuinely hard to find a part-time job that fits "
               "around their class timetable.",
     "why_load_bearing": "If finding isn't the pain, the whole product solves a non-problem.",
     "fatal_if_false": "high"},
    {"belief": "Students would switch from Indeed / the college job board / group "
               "chats to a new timetable-matching app.",
     "why_load_bearing": "Without switching, the marketplace never forms.",
     "fatal_if_false": "medium"},
    {"belief": "Employers would list jobs on a student-specific, timetable-aware platform.",
     "why_load_bearing": "No supply side, nothing to match against.",
     "fatal_if_false": "medium"},
]


def _project(assumptions):
    """The clean view the prompts expect — exactly the contract fields."""
    return [{"id": a["id"], "belief": a["belief"], "tier": a["tier"],
             "fatal_if_false": a["fatal_if_false"]} for a in assumptions]


def main():
    path = "___integration_test_ledger___.json"
    import os
    if os.path.exists(path):
        os.remove(path)

    # --- Session 1: build the ledger via memory.py -------------------------
    ledger = memory.load(path)
    memory.set_idea(ledger, "An app that shows students part-time jobs whose shifts "
                            "fit around their class timetable.")
    ids = memory.add_assumptions(ledger, S1_ASSUMPTIONS, source="extraction", session=1)
    assert len(ids) == 3 and ids[0] == "a1", "memory seeding failed"
    print(f"[S1] seeded {len(ids)} assumptions in the ledger: {ids}")

    # --- SEAM 1: ledger assumptions -> RISK_RANKING -> ledger.riskiest -----
    print("\n… live call: RISK_RANKING (memory → prompt → memory)")
    payload = json.dumps({"idea": ledger["idea"]["current"],
                          "assumptions": _project(memory.open_assumptions(ledger))})
    ranking = parse_json(ask(RISK_RANKING, payload))
    riskiest_id = ranking["riskiest_id"]
    assert memory.get_assumption(ledger, riskiest_id) is not None, \
        f"RISK_RANKING returned id {riskiest_id!r} that isn't in the ledger — CONTRACT BREAK"
    memory.set_riskiest(ledger, riskiest_id)
    print(f"    ✓ riskiest_id {riskiest_id!r} maps to a real ledger assumption and was set")
    print(f"      → {memory.get_assumption(ledger, riskiest_id)['belief'][:80]}…")

    memory.take_snapshot(ledger, summary="S1: assumptions + riskiest set by RISK_RANKING")

    # --- Session 2: evidence comes in -------------------------------------
    ledger["current_session"] = 2
    print("\n… live call: EVIDENCE_INTERPRETATION (Adam Session 2 → ledger tiers)")
    payload = json.dumps({"assumptions": _project(memory.open_assumptions(ledger)),
                          "evidence_text": ADAM_SESSION_2})
    interp = parse_json(ask(EVIDENCE_INTERPRETATION, payload))

    memory.add_evidence(ledger, raw=ADAM_SESSION_2, session=2,
                        interpretation=interp.get("evidence_summary", ""))

    # --- SEAM 2: EVIDENCE_INTERPRETATION output -> memory mutations --------
    applied_tiers, bad_tiers = 0, []
    for u in interp["assumption_updates"]:
        try:
            memory.update_tier(ledger, u["id"], u["new_tier"], session=2)
            applied_tiers += 1
        except ValueError:
            bad_tiers.append(u["new_tier"])   # tier outside the 4 bands == contract break
        except KeyError:
            pass  # update referenced an id not in ledger; tolerated, just not applied
    assert not bad_tiers, f"EVIDENCE_INTERPRETATION emitted illegal tier(s): {bad_tiers}"
    print(f"    ✓ {applied_tiers} tier update(s) applied; all tiers were valid bands")

    emerged = memory.add_assumptions(
        ledger, interp.get("new_assumptions", []), source="emerged", session=2)
    print(f"    ✓ {len(emerged)} emerged assumption(s) added to the ledger: {emerged}")

    # --- SEAM 3: change-detector sees changes driven by live reasoning -----
    d = change_detector.diff(ledger)
    assert not d["is_first_session"], "should have a prior snapshot from S1"
    assert d["tier_changes"] or d["new_assumptions"], \
        "live evidence produced no detectable change — seam is dead"
    print("\n[change-detector] observed live-driven changes:")
    print("    " + change_detector.format_changes(ledger, d).replace("\n", "\n    "))

    memory.take_snapshot(ledger, summary="S2: tiers updated from evidence")
    memory.save(ledger, path)

    # round-trip the live-built ledger through disk
    reloaded = memory.load(path)
    assert reloaded == ledger, "live-built ledger did not survive save/load"
    os.remove(path)

    print("\n" + "=" * 60)
    print("INTEGRATION OK — memory.py and prompts.py interlock end to end:")
    print("  • ledger assumptions are accepted by RISK_RANKING")
    print("  • riskiest_id round-trips back into the ledger")
    print("  • every tier from EVIDENCE_INTERPRETATION is a legal band")
    print("  • emerged assumptions land in the ledger")
    print("  • change-detector reports the live-driven diff")
    print("  • the live-built ledger survives save/load")
    print("=" * 60)


if __name__ == "__main__":
    main()
