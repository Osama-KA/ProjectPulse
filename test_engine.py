"""Headless walk of Adam's full arc through engine.py (Day 3, Person A).

The Streamlit UI is just a view over these engine calls, so proving the arc here
means the app's data path is sound without needing a browser. Exercises the live
prompts (~7 calls). Run:  ./.venv/Scripts/python.exe test_engine.py
"""
import sys

sys.stdout.reconfigure(encoding="utf-8")

import engine
import memory
from llm import get_client
from prompts import ADAM_SESSION_1, ADAM_SESSION_2, ADAM_SESSION_3


def main():
    client = get_client()
    ledger = memory.load("___engine_test___.json")  # missing -> fresh in-memory ledger

    # --- Session 1: intake -------------------------------------------------
    print("[S1] start_first…")
    res = engine.start_first(ledger, ADAM_SESSION_1, client)
    assert len(res["assumptions"]) >= 6, "expected 6+ assumptions"
    assert res["riskiest"], "riskiest must be set"
    assert res["why_riskiest"], "ranking should explain the riskiest"
    print(f"     {len(res['assumptions'])} assumptions; riskiest → {res['riskiest']['belief'][:70]}…")

    # Founder confirms decision #1 + sets a kill criterion (what the UI does).
    rid = ledger["riskiest_assumption_id"]
    memory.add_decision(ledger, f"Test first: {res['riskiest']['belief']}", "confirmed", 1, "test_choice")
    memory.add_kill_criterion(
        ledger, rid, "If 4+ of 7 interviewees say finding a job isn't a real pain, stop.", 1)

    # Approved action: draft the test.
    print("[S1] draft_test…")
    art = engine.draft_test(ledger, res["riskiest"]["belief"], client)
    assert art.get("interview_script"), "test must include an interview script"
    assert art.get("suggested_kill_criterion"), "test must suggest a kill criterion"
    leading = [q for q in art["interview_script"]
               if any(k in q.lower() for k in ("would you use", "would you pay", "our app", "this app"))]
    print(f"     {len(art['interview_script'])} questions, {len(leading)} leading (want 0)")

    # --- Session 2: evidence comes in -------------------------------------
    print("[S2] wrap…")
    wres = engine.wrap(ledger, ADAM_SESSION_2, client)
    interp = wres["interpretation"]
    weakened = [u for u in interp["assumption_updates"]
                if u["new_tier"] in ("Weak signal", "Contested")]
    assert weakened, "evidence should weaken at least one assumption"
    assert interp.get("false_positive_flags"), "should flag the friend-bias false positive"
    assert interp.get("new_assumptions"), "post-hire assumption should emerge"
    assert wres["decision"], "a persevere/pivot decision should be due"
    dec = wres["decision"]
    assert dec.get("case_for_persevere") and dec.get("case_for_pivot"), "both sides must be steelmanned"
    print(f"     {len(weakened)} weakened, {len(interp['false_positive_flags'])} false-positive flag(s), "
          f"{len(interp['new_assumptions'])} emerged; decision moment raised")

    # Founder leans pivot (what the UI records).
    memory.add_decision(ledger, "Lean Pivot", "post-hire pain looks sharper", 2, "persevere_pivot_stop")
    memory.set_kill_status(ledger, rid, "crossed")

    # --- Session 3: the pivot re-brief (money shot) -----------------------
    print("[S3] start_return…")
    sres = engine.start_return(ledger, ADAM_SESSION_3, client, pivot=True)
    assert sres["diff"]["idea_changed"], "the pivot should register as an idea change"
    b = sres["briefing"]
    assert b.get("where_it_stands") and b.get("the_one_move"), "briefing must stand + name one move"
    arc = (b["where_it_stands"] + b.get("what_changed", "")).lower()
    assert any(k in arc for k in ("last session", "weak signal", "pushed", "pivot", "post-hire", "after")), \
        "briefing should reconstruct the arc, not just describe the present"
    print(f"     idea pivoted ✓; one move → {b['the_one_move'].get('action','')[:70]}…")

    assert len(ledger["snapshots"]) == 3, f"expected 3 snapshots, got {len(ledger['snapshots'])}"
    print("\nENGINE ARC OK — S1 intake → test draft → S2 evidence+decision → S3 continuity re-brief.")


if __name__ == "__main__":
    main()
