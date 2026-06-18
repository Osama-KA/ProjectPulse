"""Deterministic tests for the memory layer + change-detector (Day 2, Person A).

No API calls — fast, free, repeatable. Proves the JSON ledger round-trips and
that the change-detector reports new assumptions, tier moves, riskiest shifts,
and idea pivots correctly. The final test scripts Adam's full 3-session arc
with hand-fed data so the Day-3 cross-session "money shot" is rehearsed purely
in code.

Run:  ./.venv/Scripts/python.exe test_memory.py
"""
import os
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8")

import change_detector
import memory


def test_round_trip():
    ledger = memory.load("___no_such_file___.json")  # missing -> empty
    memory.set_idea(ledger, "An app that does X")
    ids = memory.add_assumptions(
        ledger,
        [
            {"belief": "Users feel pain P", "why_load_bearing": "core", "fatal_if_false": "high"},
            {"belief": "Users will switch", "why_load_bearing": "adoption", "fatal_if_false": "medium"},
        ],
        source="extraction",
        session=1,
    )
    memory.set_riskiest(ledger, ids[0])
    memory.add_kill_criterion(ledger, ids[0], "fewer than 5/10 confirm pain", 1)

    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "m.json")
        memory.save(ledger, path)
        reloaded = memory.load(path)

    assert reloaded == ledger, "round-trip changed the ledger"
    assert len(reloaded["assumptions"]) == 2
    assert reloaded["riskiest_assumption_id"] == ids[0]
    print("✓ round-trip: save → load preserves the ledger exactly")


def test_dedupe():
    ledger = memory.load("___no_such_file___.json")
    memory.add_assumptions(ledger, [{"belief": "Same belief"}], "extraction", 1)
    added = memory.add_assumptions(
        ledger,
        [{"testable_assumption": "Same belief"}, {"testable_assumption": "Fresh one"}],
        "premortem",
        1,
    )
    assert len(added) == 1, "duplicate belief should not be re-added"
    assert len(ledger["assumptions"]) == 2
    print("✓ dedupe: pre-mortem does not re-add an extraction belief")


def test_tier_validation():
    ledger = memory.load("___no_such_file___.json")
    (aid,) = memory.add_assumptions(ledger, [{"belief": "B"}], "extraction", 1)
    assert memory.get_assumption(ledger, aid)["tier"] == "Untested"
    memory.update_tier(ledger, aid, "Weak signal", 2)
    assert memory.get_assumption(ledger, aid)["tier"] == "Weak signal"
    try:
        memory.update_tier(ledger, aid, "73%", 2)
    except ValueError:
        print("✓ tier validation: rejects a percentage, only the 4 bands allowed")
    else:
        raise AssertionError("update_tier accepted an invalid tier")


def test_change_detector():
    ledger = memory.load("___no_such_file___.json")
    memory.set_idea(ledger, "Idea v1")
    a1, a2 = memory.add_assumptions(
        ledger,
        [{"belief": "Pain is real", "fatal_if_false": "high"}, {"belief": "They'll switch"}],
        "extraction",
        1,
    )
    memory.set_riskiest(ledger, a1)

    # First diff: no prior snapshot -> first session.
    d0 = change_detector.diff(ledger)
    assert d0["is_first_session"] and set(d0["new_assumptions"]) == {a1, a2}
    memory.take_snapshot(ledger)

    # Session 2 mutations: tier drop, retire one, new assumption, riskiest shift, pivot.
    memory.update_tier(ledger, a1, "Weak signal", 2)
    memory.retire_assumption(ledger, a2)
    (a3,) = memory.add_assumptions(ledger, [{"belief": "Post-hire pain is the real one"}], "emerged", 2)
    memory.set_riskiest(ledger, a3)
    memory.set_idea(ledger, "Idea v2 — pivot")

    d1 = change_detector.diff(ledger)
    assert d1["is_first_session"] is False
    assert d1["new_assumptions"] == [a3]
    assert any(tc["id"] == a1 and tc["to"] == "Weak signal" for tc in d1["tier_changes"])
    assert d1["retired_assumptions"] == [a2]
    assert d1["riskiest_changed"] == {"from": a1, "to": a3}
    assert d1["idea_changed"]["to"] == "Idea v2 — pivot"
    print("✓ change-detector: new / tier-move / retire / riskiest-shift / pivot all caught")


def test_adam_three_session_arc():
    """Rehearse the demo arc end to end with hand-fed data (no LLM)."""
    ledger = memory.load("___no_such_file___.json")

    # --- Session 1: the idea + extracted assumptions ---
    ledger["current_session"] = 1
    memory.set_idea(ledger, "Help students find part-time jobs that fit their timetable")
    finding, switch, employers = memory.add_assumptions(
        ledger,
        [
            {"belief": "Finding a schedule-friendly job is a strong pain students will adopt an app for", "fatal_if_false": "high"},
            {"belief": "Students would switch from Indeed / job boards / group chats", "fatal_if_false": "medium"},
            {"belief": "Employers would list jobs on a student-specific platform", "fatal_if_false": "medium"},
        ],
        "extraction",
        1,
    )
    memory.set_riskiest(ledger, finding)
    memory.add_kill_criterion(ledger, finding, "If <3 of ~7 interviewees call finding a job a real pain, stop.", 1)
    memory.take_snapshot(ledger, summary="S1: idea + assumptions, riskiest = finding-pain")

    # --- Session 2: evidence comes back; the finding-pain assumption weakens ---
    ledger["current_session"] = 2
    memory.add_evidence(
        ledger,
        raw="7 interviews: 5 said finding a job isn't hard (use Indeed/board/WhatsApp). "
            "Only Jordan and Sam (coursemates, friends) were keen. Landing page: 60 visitors, 2 signups.",
        session=2,
        touches=[finding],
        interpretation="Core finding-pain not confirmed; the 2 positives are a biased friend sample.",
        false_positive_flag="Jordan & Sam are coursemates/friends — supportive, not market signal.",
    )
    memory.update_tier(ledger, finding, "Weak signal", 2)
    (posthire,) = memory.add_assumptions(
        ledger,
        [{"belief": "The real unserved pain is POST-hire: shift swaps, availability, exam-week rostering — incumbents abandon students once hired", "fatal_if_false": "high"}],
        "emerged",
        2,
    )
    memory.add_decision(
        ledger,
        decision="Explore the post-hire pivot",
        rationale="5/7 reject finding-pain; the only yeses are biased friends; 3 raised post-hire pain unprompted.",
        session=2,
        kind="persevere_pivot_stop",
    )
    memory.take_snapshot(ledger, summary="S2: finding-pain -> Weak signal; post-hire emerged; chose pivot")

    # --- Session 3: the pivot ---
    ledger["current_session"] = 3
    memory.retire_assumption(ledger, finding)
    memory.set_idea(ledger, "Help employed students manage shifts around exams and swap shifts easily")
    memory.set_riskiest(ledger, posthire)

    d = change_detector.diff(ledger)
    assert d["idea_changed"] is not None, "pivot should register as an idea change"
    assert d["riskiest_changed"]["to"] == posthire, "riskiest should move to post-hire pain"
    assert finding in d["retired_assumptions"], "old finding-pain assumption should be retired"

    # The continuity story is reconstructable from memory across all 3 snapshots.
    assert len(ledger["snapshots"]) == 2  # snapshots taken at S1 and S2
    assert ledger["idea"]["history"], "prior idea should be remembered after the pivot"
    print("✓ Adam 3-session arc: finding-pain → Weak signal → post-hire pivot, all in memory")
    print("    " + change_detector.format_changes(ledger, d).replace("\n", "\n    "))


if __name__ == "__main__":
    test_round_trip()
    test_dedupe()
    test_tier_validation()
    test_change_detector()
    test_adam_three_session_arc()
    print("\nAll memory-layer tests passed.")
