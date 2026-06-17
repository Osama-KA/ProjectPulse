"""Day 1 deliverable: run the two reasoning prompts against Adam's Session 1 idea.

Run:  ./.venv/Scripts/python.exe test_prompts.py
"""
import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

from llm import ask
from prompts import ADAM_SESSION_1, ASSUMPTION_EXTRACTION, PRE_MORTEM


def parse_json(text: str) -> dict:
    """Tolerant JSON extraction — strips ``` fences or stray prose if present."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start : end + 1])


def run_assumptions():
    print("=" * 70)
    print("PROMPT 1 — ASSUMPTION EXTRACTION")
    print("=" * 70)
    data = parse_json(ask(ASSUMPTION_EXTRACTION, ADAM_SESSION_1))
    items = data["assumptions"]
    for i, a in enumerate(items, 1):
        print(f"\n{i}. [{a['fatal_if_false'].upper()}] {a['belief']}")
        print(f"   why it matters: {a['why_load_bearing']}")

    # Did it catch the buried, fatal one — that finding a job is even the real pain?
    blob = json.dumps(items).lower()
    caught = any(k in blob for k in ("real pain", "primary pain", "actually hard",
                                     "hard to find", "finding a job", "even a problem",
                                     "is finding"))
    print(f"\n>> {len(items)} assumptions extracted.")
    print(f">> Buried 'is finding a job even the real pain?' caught: "
          f"{'YES' if caught else 'NO — needs another iteration'}")


def run_premortem():
    print("\n" + "=" * 70)
    print("PROMPT 2 — PRE-MORTEM")
    print("=" * 70)
    data = parse_json(ask(PRE_MORTEM, ADAM_SESSION_1))
    failures = data["failures"]
    for i, f in enumerate(failures, 1):
        print(f"\n{i}. FAILURE: {f['failure_mode']}")
        print(f"   -> TEST:  {f['testable_assumption']}")

    # Flag any generic, non-idea-specific failure that slipped through.
    banned = ["ran out of money", "ran out of runway", "poor marketing",
              "team disagree", "bad execution", "didn't raise", "funding"]
    blob = json.dumps(failures).lower()
    hits = [b for b in banned if b in blob]
    print(f"\n>> {len(failures)} failure modes generated.")
    print(f">> Generic-advice leakage: {', '.join(hits) if hits else 'none — all idea-specific'}")


if __name__ == "__main__":
    run_assumptions()
    run_premortem()
