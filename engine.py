"""Project Pulse reasoning engine — orchestration layer (Day 3, Person A).

This is the brain wired together: it threads the seven prompts (Person B) through
the JSON ledger (memory.py) and the change-detector. No Streamlit here on purpose
— app.py is the thin view, this is the testable logic. Every function takes the
ledger and an optional cached OpenAI client, mutates the ledger via memory.*, and
returns the parsed prompt output for the UI to render.

Session model: each Start/Wrap action is one session. current_session is set to
len(snapshots)+1 at the start, and exactly one snapshot is taken at the end — so
session numbers stay aligned to snapshots and the change-detector always has the
right baseline (it diffs the live ledger against the previous session's snapshot).
"""
from __future__ import annotations

import json

import change_detector
import memory
from llm import ask_json
from prompts import (
    ASSUMPTION_EXTRACTION, PRE_MORTEM, RISK_RANKING, TEST_DESIGN,
    EVIDENCE_INTERPRETATION, PERSEVERE_PIVOT, SESSION_BRIEFING,
)

# Words that signal a returning-session message is redirecting the idea (a pivot)
# rather than just asking "where do I stand?".
_PIVOT_HINTS = ("i want", "chase", "pivot", "switch", "focus on", "instead",
                "after-hired", "after hired", "new direction", "change direction",
                "go after", "explore the")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
def project_assumptions(items: list[dict]) -> list[dict]:
    """The clean contract view the prompts expect — just the four fields."""
    return [{"id": a["id"], "belief": a["belief"], "tier": a["tier"],
             "fatal_if_false": a["fatal_if_false"]} for a in items]


def kill_status_text(ledger: dict) -> str:
    """Human-readable kill-criteria status for the prompts and the briefing."""
    ks = ledger["kill_criteria"]
    if not ks:
        return "No kill criteria set yet."
    lines = []
    for k in ks:
        a = memory.get_assumption(ledger, k["assumption_id"])
        belief = a["belief"] if a else k["assumption_id"]
        lines.append(f"- [{k['status']}] {k['criterion']}  (on: {belief})")
    return "\n".join(lines)


def _begin_session(ledger: dict) -> int:
    session = len(ledger["snapshots"]) + 1
    ledger["current_session"] = session
    return session


def _rank_and_set_riskiest(ledger: dict, client=None) -> dict | None:
    """Run RISK_RANKING over the open assumptions and pin the single riskiest.

    This is the contextual RAT judgment a rules engine can't do; it runs every
    Start-mode session so the riskiest re-ranks as tiers move and ideas pivot.
    """
    open_a = memory.open_assumptions(ledger)
    if not open_a:
        return None
    payload = json.dumps({"idea": ledger["idea"]["current"],
                          "assumptions": project_assumptions(open_a)})
    ranking = ask_json(RISK_RANKING, payload, client)
    rid = ranking.get("riskiest_id")
    if rid and memory.get_assumption(ledger, rid):
        memory.set_riskiest(ledger, rid)
    else:  # defensive fallback — never leave the riskiest unset
        memory.set_riskiest(ledger, open_a[0]["id"])
    return ranking


def _looks_like_pivot(statement: str) -> bool:
    s = (statement or "").lower()
    return any(h in s for h in _PIVOT_HINTS)


# ---------------------------------------------------------------------------
# Start mode — first session (intake)
# ---------------------------------------------------------------------------
def start_first(ledger: dict, idea: str, client=None) -> dict:
    """Intake: extract assumptions, run the pre-mortem, rank the riskiest.

    Returns the structured briefing material the UI renders (assumptions with
    tiers, the riskiest, and the ranking's reasoning). The cheapest test is
    deferred to draft_test() behind the approval gate.
    """
    session = _begin_session(ledger)
    memory.set_idea(ledger, idea)

    extraction = ask_json(ASSUMPTION_EXTRACTION, idea, client)
    memory.add_assumptions(ledger, extraction["assumptions"], "extraction", session)

    premortem = ask_json(PRE_MORTEM, idea, client)
    memory.add_assumptions(ledger, premortem["failures"], "premortem", session)

    ranking = _rank_and_set_riskiest(ledger, client)

    memory.take_snapshot(ledger, summary="Session 1: intake + riskiest ranked")
    return {
        "assumptions": memory.open_assumptions(ledger),
        "riskiest": memory.get_assumption(ledger, ledger["riskiest_assumption_id"]),
        "ranking": ranking,
        "why_riskiest": (ranking or {}).get("why_riskiest", ""),
    }


# ---------------------------------------------------------------------------
# Start mode — returning session (the continuity briefing / money shot)
# ---------------------------------------------------------------------------
def start_return(ledger: dict, statement: str, client=None) -> dict:
    """Returning Start: optionally absorb a pivot, re-rank, diff vs the last
    snapshot, and produce the SESSION_BRIEFING that reconstructs the arc."""
    _begin_session(ledger)

    pivoted = _looks_like_pivot(statement)
    if pivoted:
        memory.set_idea(ledger, statement)  # history captures the old idea

    # Re-rank first so the diff registers any riskiest shift, then diff against
    # the previous session's snapshot (taken before this session's own).
    _rank_and_set_riskiest(ledger, client)
    diff = change_detector.diff(ledger)

    riskiest = memory.get_assumption(ledger, ledger["riskiest_assumption_id"])
    payload = json.dumps({
        "idea": ledger["idea"]["current"],
        "diff": diff,
        "assumptions": [{"belief": a["belief"], "tier": a["tier"],
                         "why_tier": a.get("tier_reason", "")}
                        for a in memory.open_assumptions(ledger)],
        "riskiest": {"belief": riskiest["belief"], "tier": riskiest["tier"]} if riskiest else None,
        "kill_criteria_status": kill_status_text(ledger),
    })
    briefing = ask_json(SESSION_BRIEFING, payload, client)

    memory.take_snapshot(ledger, summary="Returning session: continuity briefing")
    return {"diff": diff, "briefing": briefing, "pivoted": pivoted, "riskiest": riskiest}


# ---------------------------------------------------------------------------
# Wrap mode — log evidence, re-tier, surface the decision moment
# ---------------------------------------------------------------------------
def _decision_due(ledger: dict, interp: dict) -> bool:
    """A persevere/pivot/stop call is due if the evidence undercut the riskiest
    belief, a sharper opportunity emerged, or a kill criterion was crossed."""
    if interp.get("new_assumptions"):
        return True
    if any(k["status"] == "crossed" for k in ledger["kill_criteria"]):
        return True
    riskiest = memory.get_assumption(ledger, ledger["riskiest_assumption_id"])
    return bool(riskiest) and riskiest["tier"] in ("Weak signal", "Contested")


def _run_persevere_pivot(ledger: dict, evidence_text: str, interp: dict, client=None) -> dict:
    riskiest = memory.get_assumption(ledger, ledger["riskiest_assumption_id"])
    emerged = [a["belief"] for a in ledger["assumptions"]
               if a["source"] == "emerged" and a["status"] == "open"]
    payload = json.dumps({
        "idea": ledger["idea"]["current"],
        "riskiest_assumption": {"belief": riskiest["belief"], "tier": riskiest["tier"]} if riskiest else {},
        "key_evidence": f"{interp.get('evidence_summary', '')}\n\nRaw report: {evidence_text}",
        "kill_criteria_status": kill_status_text(ledger),
        "emerged_assumptions": emerged,
    })
    return ask_json(PERSEVERE_PIVOT, payload, client)


def wrap(ledger: dict, evidence_text: str, client=None) -> dict:
    """Interpret logged evidence: re-tier affected assumptions, flag false
    positives, surface new assumptions, and frame a decision when one is due."""
    session = _begin_session(ledger)

    payload = json.dumps({
        "assumptions": project_assumptions(memory.open_assumptions(ledger)),
        "evidence_text": evidence_text,
    })
    interp = ask_json(EVIDENCE_INTERPRETATION, payload, client)

    for u in interp.get("assumption_updates", []):
        try:
            memory.update_tier(ledger, u["id"], u["new_tier"], session)
            a = memory.get_assumption(ledger, u["id"])
            if a is not None:  # stash the reason so the next briefing can cite it
                a["tier_reason"] = u.get("reasoning", "")
        except (ValueError, KeyError):
            pass  # illegal tier or unknown id — skip rather than crash the demo

    memory.add_evidence(ledger, evidence_text, session,
                        interpretation=interp.get("evidence_summary", ""))
    emerged_ids = memory.add_assumptions(
        ledger, interp.get("new_assumptions", []), "emerged", session)

    decision = _run_persevere_pivot(ledger, evidence_text, interp, client) \
        if _decision_due(ledger, interp) else None

    memory.take_snapshot(ledger, summary="Wrap: evidence interpreted, tiers updated")
    return {"interpretation": interp, "decision": decision, "emerged_ids": emerged_ids}


# ---------------------------------------------------------------------------
# Approval-gated action — draft the test artifact
# ---------------------------------------------------------------------------
def draft_test(ledger: dict, riskiest_belief: str, client=None) -> dict:
    """The one approved action: design the cheapest falsification test for the
    riskiest assumption (interview script, fake-door copy, survey, kill rule)."""
    payload = json.dumps({"idea": ledger["idea"]["current"],
                          "riskiest_assumption": riskiest_belief})
    return ask_json(TEST_DESIGN, payload, client)
