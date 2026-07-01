# LinkedIn outreach — finance leaders (KG)

Founder-run, manual. Staged so each send is ~15 seconds. **Do not automate** —
bulk-scripted invites get the account restricted/banned, and it's the founder
account during launch.

## 1. Search URLs (paste into the address bar, signed in)

Each is pre-filtered: **finance-leader titles · United States · 3rd-degree only
(= no mutual connections) · Amazon/AWS excluded**. Work down the list.

**A — Broad (all finance leaders):**
```
https://www.linkedin.com/search/results/people/?keywords=%28%22CFO%22%20OR%20%22Chief%20Financial%20Officer%22%20OR%20%22VP%20Finance%22%20OR%20%22Head%20of%20Finance%22%20OR%20%22FinOps%22%20OR%20%22Controller%22%20OR%20%22VP%20FP%26A%22%29%20NOT%20Amazon%20NOT%20AWS&geoUrn=%5B%22103644278%22%5D&network=%5B%22O%22%5D&origin=FACETED_SEARCH
```

**B — CFO only (highest signal):**
```
https://www.linkedin.com/search/results/people/?keywords=%28%22CFO%22%20OR%20%22Chief%20Financial%20Officer%22%29%20NOT%20Amazon&geoUrn=%5B%22103644278%22%5D&network=%5B%22O%22%5D&origin=FACETED_SEARCH
```

**C — FinOps / cloud-financial (feels the AI-spend pain first):**
```
https://www.linkedin.com/search/results/people/?keywords=%28%22FinOps%22%20OR%20%22Head%20of%20FinOps%22%20OR%20%22Cloud%20Financial%22%29%20NOT%20Amazon&geoUrn=%5B%22103644278%22%5D&network=%5B%22O%22%5D&origin=FACETED_SEARCH
```

Why `network=["O"]`: LinkedIn degrees — 1st = connected, **2nd = you share a
mutual connection**, **3rd+ = you don't**. `O` filter returns 3rd-degree only, so
every result satisfies "no mutual connections." (2nd-degree accept at higher
rates, but you asked for none-shared — this honors it.)

**Bullseye within the list:** a finance leader at a **50–500-person software/SaaS
company** (our ICP). Skip enterprise giants and anyone still showing an Amazon/AWS
current role (the `NOT` catches most; eyeball the rest).

## 2. The note (paste, then swap the first name — 300-char cap, this fits)

> Hi ____, I built outlay-ai.com to help finance leaders track, forecast &
> budget AI compute spend the same way you manage CapEx/OpEx for the quarter.
> Would love to chat and share more!
>
> -KG

Flow: **Connect → Add a note → paste → change `____` to their first name → Send.**
(Tightened your draft: removed the doubled "spend budgets".)

## 3. Volume & cadence — the guardrails that keep the account alive

- **Free LinkedIn caps note-invites at ~5–10/month** (the note field just stops
  appearing). If you're committing to this channel, **1 month of Sales Navigator
  removes the note cap** and adds better title/seniority filters — worth it.
- Weekly invite ceiling is ~100–200 even for normal use. **Stay at 10–20/day.**
  Consistency beats bursts; bursts trip the spam heuristic.
- Best accept rates: **Tue–Thu, 8–10am** their time.
- If LinkedIn shows a "you've sent too many invites" warning, **stop for the week.**

## 4. After they accept

Reply-thread goal is one thing: get them to **outlay-ai.com** / a read-only pilot.
Every resulting signup shows on `/admin` → **Time to value (Outlay)**; the
"stalled — worth a nudge" list tells you who to follow up with. Log sends in
`sales/outreach-tracker.csv`.

## 5. Note A/B variants (rotate per batch; keep the CapEx/OpEx hook)

1. *(primary — above)* CapEx/OpEx framing.
2. Curiosity: `Hi ____, quick one — can your team break the AI/LLM bill down by team or project today? I built outlay-ai.com to itemize + budget it like any other line. Would love your read. -KG`
3. Peer/ask: `Hi ____, building outlay-ai.com (AI compute spend, tracked & forecast like CapEx/OpEx) and getting finance leaders' gut checks. Mind if I share what it does? -KG`
