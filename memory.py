"""Project Pulse memory layer — the validation ledger (Day 2, Person A).

A single local JSON file is the whole memory of the product: the founder's
idea, the assumptions it rests on, the evidence gathered, the evidence-tier on
each assumption, the decisions made, the kill criteria, and per-session
snapshots. The spec is explicit (section 5) that this layer is *deterministic
code* — no LLM. Storing, retrieving, and tracking tiers is not a reasoning job.

Everything here is plain functions over a dict so the loop, the change-detector,
and (Day 3) the Streamlit app can all share one representation.
"""
from __future__ import annotations

import copy
import json
import os
import re
from datetime import datetime, timezone

DEFAULT_PATH = "memory.json"

# The four evidence-tier bands — the ONLY allowed confidence labels (spec Crack 1).
# Never a percentage, never a binary "validated". Ordered thinnest -> strongest.
TIERS = ["Untested", "Weak signal", "Contested", "Supported"]

# Models sometimes prepend the tier to the belief text itself, e.g.
# "Untested — students find it hard…" or "[Weak signal] …". The tier is shown as a
# separate badge, so a baked-in label renders as "(Untested) Untested — …" and goes
# stale when the badge changes. Strip it deterministically at ingestion / display.
_TIER_PREFIX = re.compile(
    r"^\s*(?:"
    r"[\[(]\s*(?:untested|weak\s*signal|contested|supported)\s*[\])]"   # [Untested] / (Weak signal)
    r"|(?:untested|weak\s*signal|contested|supported)(?=\s*[—–\-:])"     # bare label + separator
    r")\s*[—–\-:]*\s*",
    re.IGNORECASE,
)


def strip_tier_prefix(text: str) -> str:
    """Remove a leading evidence-tier label a model baked into the belief text."""
    return _TIER_PREFIX.sub("", (text or "").strip()).strip()

# fatal-if-false levels, ordered.
FATAL_LEVELS = ["low", "medium", "high"]

# A pristine, empty ledger. Always deep-copied before use so callers never share
# the module-level template.
EMPTY_LEDGER: dict = {
    "current_session": 1,
    "idea": {"current": "", "history": []},
    "riskiest_assumption_id": None,
    "assumptions": [],
    "evidence": [],
    "decisions": [],
    "kill_criteria": [],
    "snapshots": [],
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Load / save
# ---------------------------------------------------------------------------
def load(path: str = DEFAULT_PATH) -> dict:
    """Return the ledger at `path`, or a fresh empty ledger if none exists."""
    if not os.path.exists(path):
        return copy.deepcopy(EMPTY_LEDGER)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save(ledger: dict, path: str = DEFAULT_PATH) -> None:
    """Write the ledger to `path` as human-readable UTF-8 JSON.

    Writes to a temp file then replaces, so an interrupted run can't leave a
    half-written ledger behind.
    """
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# IDs
# ---------------------------------------------------------------------------
def _next_id(ledger: dict, key: str, prefix: str) -> str:
    """Stable, human-readable id: a1, a2, ... per collection."""
    return f"{prefix}{len(ledger[key]) + 1}"


# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------
def get_assumption(ledger: dict, assumption_id: str) -> dict | None:
    return next((a for a in ledger["assumptions"] if a["id"] == assumption_id), None)


def open_assumptions(ledger: dict) -> list[dict]:
    return [a for a in ledger["assumptions"] if a["status"] == "open"]


def last_snapshot(ledger: dict) -> dict | None:
    return ledger["snapshots"][-1] if ledger["snapshots"] else None


# ---------------------------------------------------------------------------
# Mutators
# ---------------------------------------------------------------------------
def set_idea(ledger: dict, text: str) -> None:
    """Set the current idea. If it replaces a different prior idea, the old one
    is pushed onto history so pivots are remembered (this is the moat)."""
    text = text.strip()
    prev = ledger["idea"]["current"]
    if prev and prev != text:
        ledger["idea"]["history"].append(prev)
    ledger["idea"]["current"] = text


def add_assumptions(
    ledger: dict, items: list[dict], source: str, session: int
) -> list[str]:
    """Append assumptions (from extraction or pre-mortem) to the ledger.

    `items` are the raw dicts from a prompt. Extraction items carry
    `belief`/`why_load_bearing`/`fatal_if_false`; pre-mortem items carry
    `testable_assumption` (+ optional `failure_mode`). Both shapes are accepted.
    De-dupes on exact belief text so the pre-mortem doesn't re-add what
    extraction already surfaced. Returns the ids of the assumptions actually
    added.
    """
    existing = {a["belief"].strip().lower() for a in ledger["assumptions"]}
    new_ids: list[str] = []
    for item in items:
        belief = strip_tier_prefix(item.get("belief") or item.get("testable_assumption") or "")
        if not belief or belief.lower() in existing:
            continue
        why = item.get("why_load_bearing") or item.get("failure_mode") or ""
        fatal = item.get("fatal_if_false", "medium")
        if fatal not in FATAL_LEVELS:
            fatal = "medium"
        aid = _next_id(ledger, "assumptions", "a")
        ledger["assumptions"].append(
            {
                "id": aid,
                "belief": belief,
                "why_load_bearing": why,
                "fatal_if_false": fatal,
                "tier": "Untested",
                "source": source,
                "status": "open",
                "evidence_ids": [],
                "created_session": session,
                "last_updated_session": session,
            }
        )
        existing.add(belief.lower())
        new_ids.append(aid)
    return new_ids


def add_evidence(
    ledger: dict,
    raw: str,
    session: int,
    touches: list[str] | None = None,
    interpretation: str = "",
    false_positive_flag: str = "",
) -> str:
    """Log a piece of evidence and link it to the assumptions it bears on."""
    touches = touches or []
    eid = _next_id(ledger, "evidence", "e")
    ledger["evidence"].append(
        {
            "id": eid,
            "session": session,
            "raw": raw,
            "interpretation": interpretation,
            "touches_assumptions": touches,
            "false_positive_flag": false_positive_flag,
            "logged_at": _now(),
        }
    )
    for aid in touches:
        a = get_assumption(ledger, aid)
        if a and eid not in a["evidence_ids"]:
            a["evidence_ids"].append(eid)
    return eid


def update_tier(ledger: dict, assumption_id: str, tier: str, session: int) -> None:
    """Move an assumption to a new evidence tier. Rejects anything outside the
    four sanctioned bands so a stray percentage can never leak in."""
    if tier not in TIERS:
        raise ValueError(f"Invalid tier {tier!r}; must be one of {TIERS}")
    a = get_assumption(ledger, assumption_id)
    if a is None:
        raise KeyError(f"No assumption {assumption_id!r}")
    a["tier"] = tier
    a["last_updated_session"] = session


def set_riskiest(ledger: dict, assumption_id: str) -> None:
    if get_assumption(ledger, assumption_id) is None:
        raise KeyError(f"No assumption {assumption_id!r}")
    ledger["riskiest_assumption_id"] = assumption_id


def retire_assumption(ledger: dict, assumption_id: str) -> None:
    """Mark an assumption no longer in play (e.g. after a pivot)."""
    a = get_assumption(ledger, assumption_id)
    if a is None:
        raise KeyError(f"No assumption {assumption_id!r}")
    a["status"] = "retired"


def add_decision(
    ledger: dict, decision: str, rationale: str, session: int, kind: str = "test_choice"
) -> str:
    """Record a decision and the reasoning behind it, at the moment it was made
    (Annie Duke's decision journal — lets a bad outcome from a good decision be
    told apart from a bad decision later, uncontaminated by hindsight)."""
    did = _next_id(ledger, "decisions", "d")
    ledger["decisions"].append(
        {
            "id": did,
            "session": session,
            "type": kind,
            "decision": decision,
            "rationale": rationale,
            "timestamp": _now(),
        }
    )
    return did


def add_kill_criterion(
    ledger: dict, assumption_id: str, criterion: str, session: int
) -> str:
    """Pre-commit, in advance, to what evidence would make the founder walk away."""
    kid = _next_id(ledger, "kill_criteria", "k")
    ledger["kill_criteria"].append(
        {
            "id": kid,
            "assumption_id": assumption_id,
            "criterion": criterion,
            "status": "open",
            "set_session": session,
        }
    )
    return kid


def set_kill_status(ledger: dict, assumption_id: str, status: str) -> None:
    """Flip the status (open|crossed) of any kill criteria on an assumption —
    used when the founder's evidence trips a pre-set quit signal."""
    if status not in ("open", "crossed"):
        raise ValueError(f"Invalid kill status {status!r}")
    for k in ledger["kill_criteria"]:
        if k["assumption_id"] == assumption_id:
            k["status"] = status


# ---------------------------------------------------------------------------
# Snapshots
# ---------------------------------------------------------------------------
def take_snapshot(ledger: dict, summary: str = "") -> dict:
    """Append a snapshot of the session's key state. The change-detector diffs
    the live ledger against the most recent snapshot to find what's new."""
    snap = {
        "session": ledger["current_session"],
        "timestamp": _now(),
        "idea": ledger["idea"]["current"],
        "riskiest_assumption_id": ledger["riskiest_assumption_id"],
        "assumptions": [
            {
                "id": a["id"],
                "belief": a["belief"],
                "tier": a["tier"],
                "status": a["status"],
                "fatal_if_false": a["fatal_if_false"],
            }
            for a in ledger["assumptions"]
        ],
        "summary": summary,
    }
    ledger["snapshots"].append(snap)
    return snap
