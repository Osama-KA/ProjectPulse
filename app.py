"""Project Pulse — Streamlit chat UI (Day 3, Person A).

A single natural-language chat (main column) over a compact LIVE LEDGER sidebar:
the session number, the pinned riskiest assumption, every assumption with its
evidence-tier badge, and kill-criteria status. Mode (Start / Wrap) is an explicit
choice — never guessed from phrasing (spec Crack 2). engine.py does the reasoning;
this file only renders and routes.

Run:  ./.venv/Scripts/streamlit run app.py
"""
import os

import streamlit as st

import change_detector
import engine
import memory
from llm import get_client
from prompts import ADAM_SESSION_1, ADAM_SESSION_2, ADAM_SESSION_3

st.set_page_config(page_title="Project Pulse", page_icon="📍", layout="centered")

START_LABEL = "▶ Start session"
WRAP_LABEL = "■ Wrap session"

# Heading accent colors per card type — a cyan-teal family built around #A7DAE2,
# with two warm accents kept for meaning (the loud decision, false-positive alerts).
ACCENT = {
    "blue": "#0e7490",    # deep teal — riskiest, approval
    "indigo": "#0891b2",  # cyan — what changed
    "amber": "#b45309",   # warm — the loud persevere/pivot moment (intentional contrast)
    "rose": "#be123c",    # warm — false-positive alerts (intentional contrast)
    "green": "#0d9488",   # teal-green — the one move, decision #1
}


def inject_css():
    """Friendly font and a cyan-teal palette built around the sidebar (#A7DAE2)."""
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

    html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"],
    .stMarkdown, .stChatMessage, input, textarea, button, select, .stButton button {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }

    /* Canvas — a soft teal wash, less white */
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(180deg, #e3f3f6 0%, #cfe9ee 100%);
    }
    h1 { color: #0b5563 !important; font-weight: 800 !important; letter-spacing: -0.5px; }
    h2, h3, h4 { color: #0e7490 !important; font-weight: 700 !important; }

    /* Sidebar — the requested cyan-teal, no border */
    [data-testid="stSidebar"] {
        background: #A7DAE2;
        border-right: none;
    }
    [data-testid="stSidebar"] hr { border-color: #6fbecb !important; }
    [data-testid="stSidebar"] .stButton button {
        background: #0e7490; color: #fff; border: none; font-weight: 600;
    }
    [data-testid="stSidebar"] .stButton button:hover { background: #0b5563; color: #fff; }

    /* Chat bubbles — teal-family cards */
    [data-testid="stChatMessage"] {
        background: #e6f4f7; border: 1px solid #bfe2e9;
        border-radius: 16px; padding: 0.5rem 0.9rem; box-shadow: 0 1px 3px rgba(14,116,144,0.10);
    }
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
        background: #d7edf2; border-left: 5px solid #0e7490;
    }
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
        background: #d6f0ea; border-left: 5px solid #0d9488;
    }

    /* Cards (st.container(border=True)) — light teal tint + soft shadow */
    [data-testid="stVerticalBlockBorderWrapper"] {
        background: #eef8fa; border-radius: 14px;
        box-shadow: 0 1px 4px rgba(14,116,144,0.10);
    }

    /* Primary buttons a touch bolder */
    .stButton button[kind="primary"] { font-weight: 700; }
    </style>
    """, unsafe_allow_html=True)


def heading(text: str, color_key: str = "blue", level: int = 4):
    """Colored card heading (st.markdown headings can't be inline-colored)."""
    md(f"<h{level} style='color:{ACCENT[color_key]};margin:0.2rem 0'>{text}</h{level}>")

# Evidence tiers — the only confidence labels, never a percentage.
TIER_COLORS = {
    "Untested": "#64748b",      # slate
    "Weak signal": "#f59e0b",   # amber
    "Contested": "#fb7185",     # rose (mixed both ways)
    "Supported": "#16a34a",     # green
}
FATAL_COLORS = {"high": "#dc2626", "medium": "#d97706", "low": "#65a30d"}
FATAL_ORDER = {"high": 0, "medium": 1, "low": 2}  # most-fatal-first sort key
ASSUMPTIONS_VISIBLE = 6  # cap before the "show more" expander (extraction + pre-mortem = ~13)


# ---------------------------------------------------------------------------
# Small render helpers
# ---------------------------------------------------------------------------
def tier_badge(tier: str) -> str:
    c = TIER_COLORS.get(tier, "#64748b")
    return (f"<span style='background:{c};color:#fff;padding:1px 8px;border-radius:10px;"
            f"font-size:0.72rem;font-weight:600;white-space:nowrap'>{tier}</span>")


def fatal_chip(level: str) -> str:
    c = FATAL_COLORS.get(level, "#6b7280")
    return (f"<span style='border:1px solid {c};color:{c};padding:0 6px;border-radius:8px;"
            f"font-size:0.66rem;font-weight:600'>fatal-if-false: {level}</span>")


def md(html: str):
    st.markdown(html, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
@st.cache_resource
def client():
    return get_client()


def save():
    memory.save(st.session_state.ledger)


def init_state():
    if "ledger" not in st.session_state:
        st.session_state.ledger = memory.load(memory.DEFAULT_PATH)
        st.session_state.transcript = []      # [{role, kind, data}]
        st.session_state.stage = "idle"        # idle | await_decision1 | await_approval | await_decision2
        st.session_state.pending_input = None  # text queued for processing
        st.session_state.pending_pivot = False # explicit pivot flag for the queued text
        st.session_state.work = None           # (text, mode, pivot) being processed this run
    # Seed the mode toggle once so the widget never carries both a default and a
    # session-state value (which Streamlit warns about).
    st.session_state.setdefault("mode_seg", START_LABEL)


def reset_demo():
    if os.path.exists(memory.DEFAULT_PATH):
        os.remove(memory.DEFAULT_PATH)
    for k in ("ledger", "transcript", "stage", "pending_input", "pending_pivot",
              "work", "mode_seg", "pivot_chk"):
        st.session_state.pop(k, None)


# ---------------------------------------------------------------------------
# Sidebar — the compact live ledger
# ---------------------------------------------------------------------------
def render_sidebar() -> str:
    L = st.session_state.ledger
    with st.sidebar:
        st.markdown("### 📍 Project Pulse")
        st.caption("Find out what's worth building.")
        session_no = len(L["snapshots"]) + 1
        st.markdown(f"**Session {session_no}**")

        mode_label = st.segmented_control(
            "Session mode", [START_LABEL, WRAP_LABEL], key="mode_seg")
        mode = "wrap" if mode_label == WRAP_LABEL else "start"

        st.divider()

        riskiest = memory.get_assumption(L, L["riskiest_assumption_id"])
        if riskiest:
            st.markdown("**📌 Riskiest assumption**")
            md(tier_badge(riskiest["tier"]))
            st.markdown(f"<small>{riskiest['belief']}</small>", unsafe_allow_html=True)
            st.divider()

        open_a = memory.open_assumptions(L)
        st.markdown(f"**Assumptions · {len(open_a)}**")
        if not open_a:
            st.caption("None yet — start a session with your idea.")

        def _sidebar_row(a):
            star = "📌 " if a["id"] == L["riskiest_assumption_id"] else ""
            belief = a["belief"] if len(a["belief"]) <= 90 else a["belief"][:88] + "…"
            md(f"<div style='margin:.35rem 0'>{tier_badge(a['tier'])} "
               f"<small>{star}{belief}</small></div>")

        # Riskiest pinned first, then most-fatal-first; cap the visible list.
        ordered = sorted(open_a, key=lambda a: (a["id"] != L["riskiest_assumption_id"],
                                                FATAL_ORDER.get(a["fatal_if_false"], 1)))
        for a in ordered[:8]:
            _sidebar_row(a)
        if len(ordered) > 8:
            with st.expander(f"Show {len(ordered) - 8} more"):
                for a in ordered[8:]:
                    _sidebar_row(a)
        retired = [a for a in L["assumptions"] if a["status"] == "retired"]
        if retired:
            with st.expander(f"Retired · {len(retired)}"):
                for a in retired:
                    st.markdown(f"<small style='color:#94a3b8;text-decoration:line-through'>"
                                f"{a['belief']}</small>", unsafe_allow_html=True)

        st.divider()
        st.markdown("**Kill criteria**")
        if not L["kill_criteria"]:
            st.caption("None set yet.")
        for k in L["kill_criteria"]:
            icon = "🔴 crossed" if k["status"] == "crossed" else "🟢 open"
            st.markdown(f"<small>{icon} — {k['criterion']}</small>", unsafe_allow_html=True)

        st.divider()
        disabled = st.session_state.stage != "idle"
        st.caption("Demo — Adam scenario")
        if st.button("① Idea", use_container_width=True, disabled=disabled):
            queue(ADAM_SESSION_1, START_LABEL)
        if st.button("② Evidence", use_container_width=True, disabled=disabled):
            queue(ADAM_SESSION_2, WRAP_LABEL)
        if st.button("③ Pivot", use_container_width=True, disabled=disabled):
            queue(ADAM_SESSION_3, START_LABEL, pivot=True)
        if st.button("↻ Reset demo", use_container_width=True):
            reset_demo()
            st.rerun()
    return mode


def queue(text: str, mode_label: str, pivot: bool = False):
    """Queue input for processing and align the mode toggle to it.

    The mode toggle is applied at the top of main() on the next run — BEFORE the
    segmented_control is instantiated — because Streamlit forbids writing a
    widget's state key after the widget exists in the same run. `pivot` is the
    explicit redirect signal (the ③ demo button passes True).
    """
    st.session_state.pending_mode_label = mode_label
    st.session_state.pending_input = text
    st.session_state.pending_pivot = pivot
    st.rerun()


# ---------------------------------------------------------------------------
# Transcript rendering
# ---------------------------------------------------------------------------
def render_entry(e: dict):
    role, kind, d = e["role"], e["kind"], e["data"]
    with st.chat_message("user" if role == "user" else "assistant",
                         avatar="🧑‍💻" if role == "user" else "📍"):
        if kind == "text":
            st.write(d["text"])
        elif kind == "first_briefing":
            render_first_briefing(d)
        elif kind == "test_artifact":
            render_test_artifact(d)
        elif kind == "evidence_result":
            render_evidence_result(d)
        elif kind == "decision_moment":
            render_decision_moment(d)
        elif kind == "returning_briefing":
            render_returning_briefing(d)


def _assumption_row(a: dict):
    md(f"<div style='margin:.4rem 0'>{tier_badge(a['tier'])} &nbsp;{fatal_chip(a['fatal'])}"
       f"<br><span>{a['belief']}</span></div>")
    with st.expander("Why this is load-bearing"):
        st.write(a["why"])


def render_first_briefing(d: dict):
    st.markdown("Here's what your idea quietly depends on. I've surfaced the hidden "
                "assumptions and ranked the **single riskiest** one to test first.")
    # Most fatal-if-false first; show a focused few, the rest behind an expander
    # (extraction + pre-mortem merge to ~13, too many to dump on the money shot).
    items = sorted(d["assumptions"], key=lambda a: FATAL_ORDER.get(a.get("fatal", "medium"), 1))
    top, rest = items[:ASSUMPTIONS_VISIBLE], items[ASSUMPTIONS_VISIBLE:]
    st.markdown(f"**Assumptions this idea rests on · {len(items)}** (most fatal-if-false first)")
    for a in top:
        _assumption_row(a)
    if rest:
        with st.expander(f"Show {len(rest)} more assumptions"):
            for a in rest:
                _assumption_row(a)
    r = d["riskiest"]
    if r:
        with st.container(border=True):
            heading("📌 Riskiest assumption — test this first", "blue")
            md(f"{tier_badge(r['tier'])} &nbsp;{fatal_chip(r['fatal'])}")
            st.markdown(f"**{r['belief']}**")
            if d.get("why_riskiest"):
                st.markdown(f"<small>{d['why_riskiest']}</small>", unsafe_allow_html=True)


def render_test_artifact(d: dict):
    st.markdown("✅ **Approved — here's your test, drafted.** Run it as-is; nothing is sent for you.")
    st.markdown(f"**Cheapest test**\n\n{d.get('cheapest_test','')}")
    if d.get("interview_script"):
        st.markdown("**Interview script** (non-leading — about real past behaviour)")
        for q in d["interview_script"]:
            st.markdown(f"- {q}")
    fd = d.get("fake_door") or {}
    if fd:
        with st.container(border=True):
            st.markdown(f"**Fake-door landing page**")
            st.markdown(f"### {fd.get('headline','')}")
            st.markdown(f"_{fd.get('subhead','')}_")
            st.button(fd.get("cta", "Sign up"), disabled=True, key=f"fd_{id(d)}")
            st.caption(f"What a signup means: {fd.get('what_a_signup_means','')}")
    if d.get("survey"):
        with st.expander("Optional short survey"):
            for q in d["survey"]:
                st.markdown(f"- {q}")
    st.markdown(f"**What would falsify it:** {d.get('what_would_falsify','')}")
    st.markdown(f"**Suggested kill criterion:** {d.get('suggested_kill_criterion','')}")
    st.success("✓ Validation tasks created · next check-in scheduled  _(mocked — no real integrations)_")
    st.caption("Pulse never contacts anyone or publishes anything. It only drafts, "
               "and only after you approve.")


def render_evidence_result(d: dict):
    st.markdown(f"**Here's the honest read of what you gathered.**\n\n{d.get('evidence_summary','')}")
    updates = d.get("assumption_updates", [])
    if updates:
        st.markdown("**Evidence-tier updates**")
        for u in updates:
            md(f"<div style='margin:.4rem 0'>{tier_badge(u.get('old_tier','Untested'))} "
               f"→ {tier_badge(u.get('new_tier','Untested'))} &nbsp;"
               f"<span>{memory.strip_tier_prefix(u.get('belief',''))}</span></div>")
            with st.expander("Why this tier"):
                st.write(u.get("reasoning", ""))
                if u.get("evidence_cited"):
                    st.caption(f"Rests on: {u['evidence_cited']}")
    flags = d.get("false_positive_flags", [])
    if flags:
        with st.container(border=True):
            heading("⚠️ False-positive checks — why some 'positive' evidence may not count", "rose", level=5)
            for f in flags:
                st.markdown(f"- **{f.get('concern','')}** — {f.get('why','')}")
    new = d.get("new_assumptions", [])
    if new:
        st.markdown("**New assumption(s) that emerged**")
        for n in new:
            md(f"<div style='margin:.3rem 0'>{fatal_chip(n.get('fatal_if_false','medium'))} "
               f"<span>{memory.strip_tier_prefix(n.get('belief',''))}</span></div>")


def render_decision_moment(d: dict):
    with st.container(border=True):
        heading("⚖️ This is your call — persevere, pivot, or stop", "amber", level=3)
        st.markdown(d.get("situation", ""))
        if d.get("kill_criteria_status"):
            st.markdown(f"**Kill-criteria status:** {d['kill_criteria_status']}")
        cols = st.columns(2 if not d.get("case_for_stop") else 3)
        cols[0].markdown("**Case for persevere**")
        cols[0].markdown(f"<small>{d.get('case_for_persevere','')}</small>", unsafe_allow_html=True)
        cols[1].markdown("**Case for pivot**")
        cols[1].markdown(f"<small>{d.get('case_for_pivot','')}</small>", unsafe_allow_html=True)
        if d.get("case_for_stop"):
            cols[2].markdown("**Case for stop**")
            cols[2].markdown(f"<small>{d['case_for_stop']}</small>", unsafe_allow_html=True)
        if d.get("what_each_would_mean"):
            st.caption(f"What each would mean: {d['what_each_would_mean']}")
        st.info(f"🧭 {d.get('this_is_your_call','Pulse does not decide this — you do.')} "
                "_This is a decision input, not a verdict._")


def render_returning_briefing(d: dict):
    b = d["briefing"]
    st.markdown(f"**Where your idea stands**\n\n{b.get('where_it_stands','')}")
    with st.container(border=True):
        heading("🔄 What changed since last session", "indigo", level=5)
        st.markdown(b.get("what_changed", ""))
        if d.get("changes_text"):
            with st.expander("Detected changes (from memory)"):
                st.code(d["changes_text"], language=None)
    if b.get("risk_picture"):
        st.markdown("**Risk picture**")
        for r in b["risk_picture"]:
            md(f"<div style='margin:.4rem 0'>{tier_badge(r.get('tier','Untested'))} "
               f"<span>{memory.strip_tier_prefix(r.get('belief',''))}</span></div>")
            if r.get("why_tier"):
                st.markdown(f"<small style='color:#475569'>{r['why_tier']}</small>",
                            unsafe_allow_html=True)
    m = b.get("the_one_move") or {}
    if m:
        with st.container(border=True):
            heading("🎯 The one move", "green")
            st.markdown(m.get("action", ""))
            if m.get("assumption_targeted"):
                st.caption(f"Targets: {m['assumption_targeted']}")
            if m.get("reasoning"):
                st.markdown(f"<small>{m['reasoning']}</small>", unsafe_allow_html=True)
            if m.get("expected_signal"):
                st.markdown(f"**Expected signal:** {m['expected_signal']}")
    if b.get("decision_moment"):
        st.info(f"⚖️ {b['decision_moment']}")


# ---------------------------------------------------------------------------
# Input processing
# ---------------------------------------------------------------------------
def add(role: str, kind: str, data: dict):
    st.session_state.transcript.append({"role": role, "kind": kind, "data": data})


def run(label: str, fn, *args):
    """Run an engine call with a spinner and a demo-safe error net."""
    try:
        with st.spinner(label):
            return fn(*args)
    except Exception as e:  # never let a transient model hiccup crash the demo
        add("assistant", "text",
            {"text": f"⚠️ I hit a snag talking to the model ({e}). Nothing was lost — "
                     "try that step again."})
        return None


def do_processing(text: str, mode: str, pivot: bool = False):
    """Run the LLM work for a queued turn. The user message is already on the
    transcript; this only appends Pulse's response(s). Called from the work zone
    just above the input, so its spinner is always in view. `pivot` is the
    explicit redirect flag passed through to engine.start_return."""
    L = st.session_state.ledger

    if mode == "wrap":
        if not memory.open_assumptions(L) and not L["idea"]["current"]:
            add("assistant", "text",
                {"text": "Let's start with your idea first — switch to **Start session** "
                         "and tell me what you want to build."})
            return
        res = run("Reading your evidence, re-rating the assumptions…", engine.wrap, L, text, client())
        if res is None:
            return
        save()
        add("assistant", "evidence_result", res["interpretation"])
        if res.get("decision"):
            add("assistant", "decision_moment", res["decision"])
            st.session_state.stage = "await_decision2"
        return

    # Start mode
    first = not L["snapshots"]
    if first:
        res = run("Extracting hidden assumptions, running the pre-mortem, ranking the riskiest…",
                  engine.start_first, L, text, client())
        if res is None:
            return
        save()
        r = res["riskiest"]
        add("assistant", "first_briefing", {
            "assumptions": [{"belief": a["belief"], "tier": a["tier"],
                             "fatal": a["fatal_if_false"], "why": a["why_load_bearing"]}
                            for a in res["assumptions"]],
            "riskiest": {"belief": r["belief"], "tier": r["tier"],
                         "fatal": r["fatal_if_false"]} if r else None,
            "why_riskiest": res.get("why_riskiest", ""),
        })
        st.session_state.stage = "await_decision1"
    else:
        res = run("Reconstructing the arc, checking what changed, re-ranking the riskiest…",
                  engine.start_return, L, text, client(), pivot)
        if res is None:
            return
        save()
        add("assistant", "returning_briefing", {
            "briefing": res["briefing"],
            "changes_text": change_detector.format_changes(L, res["diff"]),
        })


# ---------------------------------------------------------------------------
# Stage controls (rendered after the transcript)
# ---------------------------------------------------------------------------
def render_stage_controls():
    L = st.session_state.ledger
    stage = st.session_state.stage

    if stage == "await_decision1":
        with st.container(border=True):
            heading("✅ Decision moment #1 — which assumption do you test first?", "green")
            st.caption("Pulse proposes the riskiest. You confirm or override — your call.")
            open_a = memory.open_assumptions(L)
            labels = [a["belief"] for a in open_a]
            default_idx = next((i for i, a in enumerate(open_a)
                                if a["id"] == L["riskiest_assumption_id"]), 0)
            choice = st.selectbox("Assumption to test first", labels, index=default_idx)
            kill = st.text_input("Set a kill criterion — what result would make you walk away?",
                                 placeholder="e.g. if 4+ of 7 interviewees say finding a job isn't a real pain")
            if st.button("Confirm & lock it in", type="primary"):
                chosen = open_a[labels.index(choice)]
                memory.set_riskiest(L, chosen["id"])
                memory.add_decision(L, f"Test first: {chosen['belief']}",
                                    "Founder confirmed which assumption to test first.",
                                    L["current_session"], kind="test_choice")
                if kill.strip():
                    memory.add_kill_criterion(L, chosen["id"], kill.strip(), L["current_session"])
                save()
                add("assistant", "text",
                    {"text": f"Locked in. We'll test: **{chosen['belief']}**"
                             + (f"\n\nKill criterion set: _{kill.strip()}_" if kill.strip() else "")})
                st.session_state.stage = "await_approval"
                st.rerun()

    elif stage == "await_approval":
        with st.container(border=True):
            heading("✍️ Want me to draft the test?", "blue")
            st.caption("Pulse never sends or publishes anything — it only drafts, after you approve.")
            c1, c2 = st.columns(2)
            if c1.button("✍️ Draft the test for me", type="primary"):
                riskiest = memory.get_assumption(L, L["riskiest_assumption_id"])
                art = run("Designing the cheapest falsification test…",
                          engine.draft_test, L, riskiest["belief"], client())
                if art is not None:
                    save()
                    add("assistant", "test_artifact", art)
                    st.session_state.stage = "idle"
                st.rerun()
            if c2.button("Not now"):
                add("assistant", "text", {"text": "No problem — the test is ready whenever you are."})
                st.session_state.stage = "idle"
                st.rerun()

    elif stage == "await_decision2":
        with st.container(border=True):
            heading("⚖️ Your call — record your decision", "amber")
            st.caption("Pulse laid out the strongest case for each. It does not decide — you do.")
            lean = st.radio("Which way are you leaning?", ["Persevere", "Pivot", "Stop"],
                            horizontal=True)
            rationale = st.text_input("Why? (recorded to your decision journal)")
            if st.button("Record my decision", type="primary"):
                memory.add_decision(L, f"Lean {lean}", rationale or "(no rationale given)",
                                    L["current_session"], kind="persevere_pivot_stop")
                if lean in ("Pivot", "Stop"):
                    memory.set_kill_status(L, L["riskiest_assumption_id"], "crossed")
                save()
                add("assistant", "text",
                    {"text": f"Recorded: **{lean}**. {rationale or ''}\n\n"
                             "That reasoning is now in your journal — so a good decision and a "
                             "good outcome can be told apart later."})
                st.session_state.stage = "idle"
                st.rerun()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    init_state()
    inject_css()
    # Apply any queued mode change BEFORE the mode widget is instantiated — writing
    # a widget's state key is only allowed before the widget exists this run.
    if st.session_state.get("pending_mode_label"):
        st.session_state["mode_seg"] = st.session_state.pop("pending_mode_label")
    mode = render_sidebar()

    # When new input arrives, record the USER turn now and defer the LLM work to the
    # work zone below — so the spinner renders just above the input, always in view.
    if st.session_state.pending_input is not None and st.session_state.stage == "idle":
        st.session_state.work = (st.session_state.pending_input, mode,
                                 st.session_state.pending_pivot)
        st.session_state.pending_input = None
        st.session_state.pending_pivot = False
        add("user", "text", {"text": st.session_state.work[0]})

    st.title("Project Pulse")
    st.caption("Your reasoning partner for figuring out what's actually worth building — "
               "it surfaces the riskiest belief, designs the cheapest test, and remembers the journey.")

    legend_l, legend_r = st.columns(2)
    with legend_l:
        with st.expander("🛡️ How Pulse stays honest"):
            st.markdown(
                "- **Evidence-tiered confidence, not percentages** — every assumption shows a tier "
                "(Untested / Weak signal / Contested / Supported) defined by *what evidence exists*, "
                "never a fake-precise number or a binary \"validated\".\n"
                "- **Show your work** — every judgment links to the specific evidence behind it, so you "
                "can audit it instead of trusting a black box.\n"
                "- **Steelman the opposite** — on any persevere/pivot call, Pulse argues the strongest "
                "case for *each* option. It's a decision input, not a verdict.")
    with legend_r:
        with st.expander("🧭 Built on four decision-science methods"):
            st.markdown(
                "- **Riskiest Assumption Test (RAT)** — test the belief most fatal-if-wrong and "
                "least-supported *before* building anything (Ries / Blank).\n"
                "- **Pre-mortem** (Gary Klein) — imagine it's six months out and the idea failed, then "
                "ask why — surfacing failure modes and hidden assumptions up front.\n"
                "- **Kill criteria / pivot-or-persevere** (Annie Duke; Lean Startup) — pre-commit to the "
                "evidence that would make you walk away, to fight sunk-cost bias.\n"
                "- **Decision journal** (Annie Duke) — record your reasoning *at the moment you decide*, "
                "so a good decision and a good outcome can be told apart later.")

    if not st.session_state.transcript:
        with st.chat_message("assistant", avatar="📍"):
            st.markdown("Tell me the idea you're thinking about building, and I'll surface the "
                        "hidden assumptions it rests on. Use **Start session** to begin, or the "
                        "**Demo** buttons in the sidebar to walk Adam's scenario.")

    for e in st.session_state.transcript:
        render_entry(e)

    render_stage_controls()

    # Work zone — sits at the bottom of the content, directly above the pinned chat
    # input, so its spinner is always visible without scrolling up.
    if st.session_state.work is not None:
        text, wmode, wpivot = st.session_state.work
        st.session_state.work = None
        do_processing(text, wmode, wpivot)
        st.rerun()

    disabled = st.session_state.stage != "idle" or st.session_state.work is not None
    if mode == "wrap":
        placeholder = "Log what you learned — interviews, signups, a competitor sighting…"
    elif st.session_state.ledger["snapshots"]:
        placeholder = "Where do I stand?"
    else:
        placeholder = "Describe the idea you want to build…"
    text = st.chat_input(placeholder, disabled=disabled)
    if text:
        st.session_state.pending_input = text
        # Pivot is an EXPLICIT action (the ③ Pivot button), never guessed from a
        # typed message — so a normal "where do I stand?" can't overwrite the idea.
        st.session_state.pending_pivot = False
        st.rerun()


main()
