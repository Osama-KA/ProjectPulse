## The Adam demo persona (full scenario)

This is the canonical scenario. Every prompt is tested against it; the demo and video follow it beat for beat. Keep the exact details consistent everywhere (7 interviews, 5 dismissive, Jordan and Sam as the friend-bias names, 60 visitors / 2 signups, 3 people raising the post-hire pain) — drift between artifacts looks sloppy to a judge.

### The persona
**Adam, 20, second-year university student.** He works part-time himself and has watched friends juggle jobs around their timetables. He's technical enough to build an app (or to use AI tools to build one), has no money to spend, and no users yet — just an idea he's excited about and a tendency, like most first-time builders, to assume the problem he sees is the problem everyone has. He's the user the brief describes: stalled at the gap between an idea and a real first step, at risk of building something nobody asked for.

### Session 1 — The idea (what Adam types into Pulse)
> "I want to build an app that helps students find part-time jobs that fit around their class timetable. Right now job hunting is painful for students because normal job listings completely ignore your schedule — you apply, you get hired, and then you find out the shifts clash with your lectures. My app would let students enter their timetable and only show them jobs with shifts that actually fit. I think this would save students a ton of stress and stop them taking jobs they have to quit two weeks later."

**Underneath (what the prompts should catch):** Adam states one belief explicitly — that scheduling conflict is the core pain. But the idea rests on several *unstated* assumptions: that finding a job is hard in the first place; that students don't already cope fine with existing tools; that timetable-fit is the thing they'd switch apps for; that employers would list jobs on a student-specific platform; and that he can reach students at the right moment. The assumption-extraction prompt should surface these — especially the first, which turns out to be fatal.

This session, Pulse should: extract the assumptions, run the pre-mortem, name the **riskiest** one ("students feel enough pain around *finding* a schedule-friendly job to adopt a new app for it"), propose the cheapest test (a small batch of interviews + a fake-door landing page), and ask Adam to set a kill criterion. **Decision moment #1:** Adam confirms which assumption to test first.

### Session 2 — The evidence (what Adam reports back a few days later)
> "Okay, I did the interviews and put up the landing page. Here's what happened.
>
> I talked to 7 students. 5 of them basically said finding a job isn't the hard part — they already use Indeed, the college job board, or local WhatsApp and Facebook groups, and they manage fine. A couple of them looked at me a bit blankly, like they didn't get what problem I was solving. The 2 who were really into the idea were Jordan and Sam — but they're both on my course, I've known them for a year, and honestly they might just have been being nice.
>
> The landing page got 60 visitors (I shared it in a few student groups) and 2 people signed up with their email.
>
> But here's the thing I didn't expect. Three different people, totally separately, brought up something I never asked about: the real nightmare isn't *getting* the job, it's *after* you're hired. Managers roster you during exam week, there's no clean way to swap a shift or tell them your availability has changed, and you end up either losing pay or risking your grades. One of them said the existing apps — Indeed, the job board, the group chats — all stop being useful the *second* you're hired. Nobody's helping with the part that actually hurts."

**Underneath (what the prompts should do):**
- Weaken the core assumption hard — 5 of 7 say finding a job isn't a real pain. The assumption "finding a schedule-friendly job is a strong pain" should drop to **Weak signal**.
- Flag the **false positive**: the only two enthusiastic responses came from Jordan and Sam, Adam's coursemates and friends — a biased sample, not market signal. Catching *why* the two yeses don't count (not just "two yeses") is the whole point of the evidence-interpretation prompt.
- Treat the landing page as weak too: 2 signups from 60 visitors is a low signal, not validation.
- Surface the **new assumption that emerged**: the real, unserved pain is *post-hire* — shift swapping, availability changes, exam-week rostering — and incumbents abandon students the moment they're hired. That "incumbents stop the second you're hired" line is what turns a problem into an *opportunity*, so keep it in.

**Decision moment #2** lives here. Pulse presents a clear **persevere vs pivot** call and steelmans both — *persevere:* the sample is tiny, maybe refine targeting; *pivot:* the evidence points consistently to a sharper, unserved pain. It does **not** choose. Adam decides to explore the pivot.

### Session 3 — The pivot (what Adam says at the start of his next session)
> "I've been thinking about it and I want to chase the after-hired angle — helping students who already have jobs manage their shifts around exams and swap shifts easily. Where does my idea stand now, and what should I do next?"

**Underneath (the payoff beat):** Pulse reconstructs the arc from memory: two weeks ago the riskiest assumption was about *finding* schedule-friendly jobs; the evidence pushed it down to Weak signal; a stronger signal pointed to *post-hire* pain; Adam has now pivoted there. It shows the kill-criteria status on the old direction, frames the new riskiest assumption to test — *"do employed students actually want a third-party tool for shift-swapping, or do they just grumble and absorb it?"* — and flags the obvious competitive question: employer-facing shift-scheduling tools already exist, but none are student-facing.

That re-brief is the money shot — the thing no on-demand chatbot can do, because it requires remembering the journey. **End the demo here.**

---