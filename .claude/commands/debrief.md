---
description: Daily 6 PM PT debrief — review the day, identify learnings, recommend strategy adjustments based on news
---

Run the daily options bot debrief. The daemon already generated the structured analysis at 16:10 ET — your job is to surface it cleanly, augment with live data + news intelligence, and drive the conversation.

**Step 1 — Read the latest debrief.** Read the LAST line of `logs/debriefs.jsonl` (use `tail -1`). Render the title and body sections, exactly as the daemon produced them. Keep it tight.

**Step 2 — Pull live state to add color the daemon couldn't see.**
- Use the Alpaca trading API to check current open positions (use `paper_trader._client()`)
- For each open spread, compute current unrealized P&L (entry_credit - current_liability via real chain quotes)
- Flag any position with: unrealized loss > 50% of credit, DTE ≤ 10, or spread liability that has moved >25% since entry
- Check today's submitted orders for any that didn't fill

**Step 3 — News-driven analysis.** This is the core value of the live debrief.

  3a. **Read today's news log**: `tail -100 logs/news.jsonl | jq -r '.headline + " [" + (.symbols // [] | join(",")) + "]"'`. Filter to articles relevant to our universe (`config.TICKERS`).

  3b. **Use WebSearch for fresh signal** — search for any of:
      - "AI infrastructure stocks news today"
      - "[ticker] news" for tickers showing high material counts in the debrief
      - "trending semiconductor stocks today"
      - "earnings calendar this week semiconductor"

  3c. **For each ticker with material news, analyze and recommend:**
      - Is the news bullish, bearish, or neutral relative to our open positions?
      - Should we adjust strategy? E.g., if SNDK got a price-target raise, the bull put is even safer — could increase qty next time. If a downgrade, consider closing early.
      - Any catalysts coming up (earnings, product launches, regulatory) that change risk?

  3d. **New ticker discovery** — based on news flow, suggest 1-3 tickers NOT currently in `config.TICKERS` that might be worth adding. Criteria:
      - Mentioned multiple times in AI/semi news this week
      - Has liquid options chain (verify with Alpaca)
      - Falls into AI infrastructure theme: chipmakers, AI-services, data centers, networking, equipment, foundries
      - Examples to consider: PLTR, SOXL, INTC, QCOM, TXN, ASML, KLAC, AMAT, LRCX, IBM, ORCL, CRWD

**Step 4 — Propose 1-3 specific actions.** Categories:
  - Position-level: "Close X early because of news Y"
  - Sleeve-level: "Reduce trend qty on Z given regime softening"
  - Universe-level: "Add ticker A; remove ticker B"
  - Parameter-level: "Loosen SPREAD_LIMIT_FILL_FRAC to 0.85 — fills are slipping"

Present each action with:
  - WHY (data point or news that supports it)
  - WHAT to change (specific config field or position)
  - HOW to apply (which file to edit, whether agent reload needed)

**Step 5 — Wait for user input.** Do NOT make changes in this step. Only after explicit approval:
  - Edit the relevant file
  - Reload the launchd agent: `launchctl unload ~/Library/LaunchAgents/com.options-bot.live.plist && launchctl load -w ~/Library/LaunchAgents/com.options-bot.live.plist`
  - Confirm: `tail -3 ~/options-bot/logs/live.out.log`

Keep the recap under 250 words. Detailed analysis only when we drill into a specific question.
