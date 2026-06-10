# Chat test prompts — exercising every routing case

Run `python -m modelpilot.demo --prompts 0`, open `/modelpilot/chat`, and keep
the dashboard (via the **dashboard ↗** link, pinned to your session) in a
second tab. Default baseline = `claude-fable-5` ($10/$50 per MTok), so simple
work saves ~90% (→ haiku) and even hard work right-sizes ~50% (→ opus).

## 1. High-confidence switches (⚡ amber chip → green "saved")

| # | Prompt | Expect |
|---|---|---|
| 1 | `Classify this review as positive or negative: 'great product, fast shipping'` | ⚡ haiku · classification · conf 0.85 |
| 2 | `Extract all email addresses from this text as JSON: contact sara@acme.com or bill@foo.io for access.` | ⚡ haiku · extraction |
| 3 | `Translate to French: The meeting has moved to Thursday at 3pm.` | ⚡ haiku · translation |
| 4 | `What is the capital of Australia?` | ⚡ haiku · short_qa |
| 5 | `Summarize in one sentence: The team shipped the redesign in February; activation rose 14% and day-30 retention improved from 21% to 26%.` | ⚡ haiku · summarization_short |
| 6 | `Fix the grammar: me and the team has went over the numbers and they wasn't matching.` | ⚡ haiku · rewrite_format |

Ticker climbs with each; dashboard session strip updates within ~5s.

## 2. Hard work right-sizes, never below its floor

With the Fable baseline these switch to **opus** (50% off — hard work still
saves, it just never drops below the tier it needs):

| # | Prompt | Expect |
|---|---|---|
| 7 | `Refactor the billing module across multiple files to use an event-driven architecture.` | ⚡ opus · codegen_complex |
| 8 | `Debug why my nightly job intermittently fails with a deadlock under load.` | ⚡ opus · debugging |
| 9 | `Prove that there is no largest prime number.` | ⚡ opus · math_logic |
| 10 | `What are the trade-offs of building vs buying a feature-flag system for a 15-person team?` | ⚡ opus · analysis_strategy (starts with "What" but the complex signal wins) |

**To see the 🛡 "quality protected, saved $0.00" case:** set the baseline
dropdown to `claude-opus-4-8` and resend any of 7–10 — they stay put because
opus *is* their floor.

## 3. Below-the-gate advice (💡 — recommends, doesn't touch)

| # | Prompt | Expect |
|---|---|---|
| 11 | `Write a Python function that reverses a linked list.` | 💡 recommends sonnet, conf 0.55 < 0.80 gate → runs opus |
| 12 | `Help me brainstorm names for my new app.` | 💡 recommends sonnet, conf 0.50 → runs opus |

These show the confidence gate doing its job — uncertain cases don't get touched.

## 4. The honest blind spots (good for credibility, know them before a customer finds them)

| # | Prompt | What happens & the story |
|---|---|---|
| 13 | `Summarize this incident in two sentences for a status page: 09:02 deploy of build 4811. 09:14 p95 latency on /checkout rises to 2.4s. 09:21 errors hit 11% (pool exhaustion in payments-svc). 09:31 rollback complete but errors persist. 09:55 traffic shifted off the mis-provisioned read replica; normal by 10:02.` | ⚡ switches to haiku — this is the **known v0 false-downgrade** from calibration (judge said sonnet). Router v1 fixes it with content-difficulty features. |
| 14 | `Prove that the sum of two even numbers is even.` | ⚡ lands on opus (from Fable) — calibration says haiku handles it, so this is a **deliberately conservative miss**. Money left on the table beats a quality incident. |

## 5. Multi-turn + session economics

| # | Do | Expect |
|---|---|---|
| 15 | After several messages, send a follow-up: `Now classify this one: 'arrived broken, slow support'` | Still ⚡ haiku; history rides along; ticker keeps accumulating |
| 16 | Click **dashboard ↗** mid-conversation | Lands on THIS SESSION pinned, numbers matching the ticker; your session tops the Recent sessions table |

## 6. Baseline selector (header dropdown)

| # | Do | Expect |
|---|---|---|
| 17 | Set baseline to `claude-haiku-4-5`, send prompt #1 | 🛡 stays — "already at or below floor"; saved $0 (nothing cheaper exists) |
| 18 | Set baseline to `claude-opus-4-8`, send prompt #1 then #7 | #1 still ⚡ haiku (smaller saving than from Fable); #7 now 🛡 stays with explicit saved $0.00 |

## 7. Edge behavior

| # | Do | Expect |
|---|---|---|
| 19 | Send a one-word prompt like `hello` | conversation, low conf → 💡 or 🛡; no reckless switch |
| 20 | Paste a very long text (several pages) + `Summarize the key points` | Watch the confidence drop / tier bump from the large-context penalty in the chip rationale |

## What "all green" looks like

Every ⚡ chip's estimated saving is replaced by a realized number; prompts
7–10 land on opus (never lower); both 💡 cases run the baseline; ticker total
≈ session strip on the dashboard; #17 saves exactly $0; #18's resent #7 shows
the 🛡 saved-$0.00 line. If any of those don't hold, that's a bug — capture
the chip text and the prompt.
