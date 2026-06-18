"""Change detector — diffs the live ledger against the last snapshot (Day 2).

This is deliberately plain code, no LLM (spec section 5: "Diffing state between
sessions to detect what's new" does NOT need a reasoner). It answers the
question a Start-mode briefing opens with: *what changed since last time?* —
new assumptions, tier moves, a shifted riskiest belief, a pivoted idea, retired
assumptions. The reasoning about what those changes MEAN is the LLM's job; this
just establishes the facts.
"""
from __future__ import annotations

import memory


def diff(ledger: dict) -> dict:
    """Compare current live state vs the most recent snapshot.

    On the very first session there is no prior snapshot, so everything is new;
    `is_first_session` is set so the briefing can say "first session" rather
    than listing every assumption as a change.
    """
    snap = memory.last_snapshot(ledger)
    if snap is None:
        return {
            "is_first_session": True,
            "new_assumptions": [a["id"] for a in ledger["assumptions"]],
            "tier_changes": [],
            "riskiest_changed": None,
            "idea_changed": None,
            "retired_assumptions": [],
        }

    prev_by_id = {a["id"]: a for a in snap["assumptions"]}
    cur = ledger["assumptions"]

    new_assumptions = [a["id"] for a in cur if a["id"] not in prev_by_id]

    tier_changes = []
    retired = []
    for a in cur:
        prev = prev_by_id.get(a["id"])
        if prev is None:
            continue
        if a["tier"] != prev["tier"]:
            tier_changes.append(
                {
                    "id": a["id"],
                    "belief": a["belief"],
                    "from": prev["tier"],
                    "to": a["tier"],
                }
            )
        if a["status"] == "retired" and prev["status"] != "retired":
            retired.append(a["id"])

    riskiest_changed = None
    if ledger["riskiest_assumption_id"] != snap["riskiest_assumption_id"]:
        riskiest_changed = {
            "from": snap["riskiest_assumption_id"],
            "to": ledger["riskiest_assumption_id"],
        }

    idea_changed = None
    if ledger["idea"]["current"] != snap["idea"]:
        idea_changed = {"from": snap["idea"], "to": ledger["idea"]["current"]}

    return {
        "is_first_session": False,
        "new_assumptions": new_assumptions,
        "tier_changes": tier_changes,
        "riskiest_changed": riskiest_changed,
        "idea_changed": idea_changed,
        "retired_assumptions": retired,
    }


def _belief(ledger: dict, assumption_id: str | None) -> str:
    if assumption_id is None:
        return "(none)"
    a = memory.get_assumption(ledger, assumption_id)
    return a["belief"] if a else assumption_id


def format_changes(ledger: dict, d: dict) -> str:
    """Render the diff as the 'What changed since last session' briefing block."""
    if d["is_first_session"]:
        n = len(d["new_assumptions"])
        return (
            "WHAT CHANGED SINCE LAST SESSION\n"
            f"  First session — {n} assumptions surfaced, nothing to compare yet."
        )

    lines = ["WHAT CHANGED SINCE LAST SESSION"]

    if d["idea_changed"]:
        lines.append("  • Idea pivoted:")
        lines.append(f"      was:  {d['idea_changed']['from']}")
        lines.append(f"      now:  {d['idea_changed']['to']}")

    for tc in d["tier_changes"]:
        lines.append(
            f"  • Tier moved [{tc['from']} → {tc['to']}]: {tc['belief']}"
        )

    if d["new_assumptions"]:
        lines.append(f"  • {len(d['new_assumptions'])} new assumption(s) emerged:")
        for aid in d["new_assumptions"]:
            lines.append(f"      - {_belief(ledger, aid)}")

    for aid in d["retired_assumptions"]:
        lines.append(f"  • Retired: {_belief(ledger, aid)}")

    if d["riskiest_changed"]:
        rc = d["riskiest_changed"]
        lines.append("  • Riskiest assumption shifted:")
        lines.append(f"      was:  {_belief(ledger, rc['from'])}")
        lines.append(f"      now:  {_belief(ledger, rc['to'])}")

    if len(lines) == 1:
        lines.append("  • No changes since last snapshot.")
    return "\n".join(lines)
