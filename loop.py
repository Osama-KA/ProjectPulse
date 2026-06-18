"""Bare terminal loop — the Day-2 proof that the brain works end to end.

Feed Adam's idea in, run the two existing reasoning prompts (assumption
extraction + pre-mortem), store everything in the JSON ledger, then print a
Start-mode briefing and snapshot the session. "Ugly is fine" — this exists to
prove the logic in the terminal before the Streamlit UI goes on top (Day 3).

Run:  ./.venv/Scripts/python.exe loop.py

NOTE — two pieces here are deterministic PLACEHOLDERS owned by Person B's
prompts on Day 3:
  • _pick_riskiest()  -> swap for the LLM risk-ranking prompt.
  • print_briefing()  -> swap for the LLM session-briefing prompt.
Both are clearly marked so the swap is mechanical.
"""
import sys

sys.stdout.reconfigure(encoding="utf-8")

import change_detector
import memory
from llm import ask, parse_json
from prompts import ADAM_SESSION_1, ASSUMPTION_EXTRACTION, PRE_MORTEM

_FATAL_RANK = {"high": 0, "medium": 1, "low": 2}
_TIER_RANK = {t: i for i, t in enumerate(memory.TIERS)}  # Untested = thinnest = 0


def _pick_riskiest(ledger: dict) -> str | None:
    """PLACEHOLDER for Person B's LLM risk-ranking (RAT).

    Deterministic stand-in: riskiest = most fatal-if-false, tie-broken by
    thinnest evidence. Real ranking is contextual judgment (spec section 5) and
    becomes an LLM call on Day 3; this just lets the loop run end to end today.
    """
    open_a = memory.open_assumptions(ledger)
    if not open_a:
        return None
    open_a.sort(
        key=lambda a: (_FATAL_RANK.get(a["fatal_if_false"], 1), _TIER_RANK.get(a["tier"], 0))
    )
    return open_a[0]["id"]


def print_briefing(ledger: dict, changes: dict) -> None:
    """PLACEHOLDER for Person B's LLM session-briefing prompt.

    Plain-text render of ledger state: idea, every assumption with its tier and
    fatal-if-false, the single riskiest belief, what changed, and the one next
    move. Day 3 replaces this prose with the LLM briefing that stitches it
    together with shown reasoning.
    """
    bar = "=" * 72
    print(bar)
    print("PROJECT PULSE — SESSION START BRIEFING")
    print(bar)
    print(f"\nIDEA:\n  {ledger['idea']['current']}\n")

    print("ASSUMPTIONS THIS IDEA RESTS ON:")
    for a in memory.open_assumptions(ledger):
        print(f"  [{a['tier']}] (fatal-if-false: {a['fatal_if_false']})  {a['belief']}")
        print(f"        why it's load-bearing: {a['why_load_bearing']}")

    riskiest = memory.get_assumption(ledger, ledger["riskiest_assumption_id"])
    print("\nRISKIEST ASSUMPTION (test this first):")
    if riskiest:
        print(f"  → {riskiest['belief']}")
        print(f"    [{riskiest['tier']}] · fatal-if-false: {riskiest['fatal_if_false']}")
    else:
        print("  → (none yet)")

    print()
    print(change_detector.format_changes(ledger, changes))

    print("\nNEXT MOVE:")
    if riskiest:
        print(f"  Design the cheapest test that could FALSIFY: {riskiest['belief']}")
    print(bar)


def run_start_session(idea: str = ADAM_SESSION_1, path: str = memory.DEFAULT_PATH) -> dict:
    """One Start-mode pass: ingest idea → extract → pre-mortem → store →
    pick riskiest → briefing → snapshot → save. Returns the ledger."""
    ledger = memory.load(path)
    session = ledger["current_session"]
    memory.set_idea(ledger, idea)

    print("… extracting assumptions")
    extraction = parse_json(ask(ASSUMPTION_EXTRACTION, idea))
    memory.add_assumptions(ledger, extraction["assumptions"], "extraction", session)

    print("… running pre-mortem")
    premortem = parse_json(ask(PRE_MORTEM, idea))
    memory.add_assumptions(ledger, premortem["failures"], "premortem", session)

    riskiest = _pick_riskiest(ledger)
    if riskiest:
        memory.set_riskiest(ledger, riskiest)

    changes = change_detector.diff(ledger)
    print()
    print_briefing(ledger, changes)

    memory.take_snapshot(ledger)
    memory.save(ledger, path)
    print(f"\n[ledger saved to {path}]")
    return ledger


if __name__ == "__main__":
    run_start_session()
