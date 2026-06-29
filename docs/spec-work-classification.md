# Feature spec — Work vs. non-work compute classification + stop non-work

Customers want to (1) see what share of their AI compute is doing the **company's
work** vs. **personal / non-work** use, and (2) **stop** the non-work usage by their
teams. This specs that **without breaking Outlay's moat** — metadata-only, read-only,
prompts/keys never leave the customer's box.

## The posture problem (and how we keep it)

The request, taken literally, conflicts with the architecture:
- *"based on context and prompts"* — reading prompt content server-side would
  violate **metadata-only**.
- *"stop all non-work compute"* — blocking requests means sitting **in the request
  path** — the gateway posture Outlay differentiates *against*.

Both are resolved the same way the rest of the product is built:

1. **Classification is metadata-first, prompt-second (and prompts stay local).**
   - **Tier 1 — metadata (no prompt):** a request joined to a work item (ticket /
     branch / session) or on a **registered work key/repo** is `work`. Outlay
     already computes the join. A key the customer flags personal is `non_work`.
   - **Tier 2 — client-side label:** for the unjoined remainder, an optional
     classifier runs **on the customer's box** (the `router_classify` pattern),
     reads the prompt locally, and emits only a one-word label (`work`/`non_work`).
     The **label is metadata; the prompt never leaves the environment.** Outlay
     consumes the label, not the text.
   - **Fidelity-honest:** unjoined + unlabeled spend is `unknown`, **not** `non_work`.
     Most untracked spend is just untracked *work* — guessing would burn trust.
     (Strict mode, opt-in, can treat unknown as non-work.)

2. **Stopping non-work is the opt-in gateway, not a posture change.** Outlay stays
   read-only and emits an allow/deny **policy**; the customer who wants hard blocking
   runs the **existing opt-in gateway** in their own path, which applies
   `gateway_decision()`. Read-only is the default; enforcement is a choice.

## Engine (shipped)

`outlay/worktype.py` — pure, stdlib + engine:
- `WorkType` = `work | non_work | unknown`.
- `WorkPolicy` — `work_api_keys`, `non_work_api_keys`, `treat_unknown_as_non_work`,
  `block_non_work`, `block_unknown`. The customer's rules.
- `classify_event(event, joined_to_work, work_label, policy)` — one event → WorkType,
  in the precedence above (personal key → work join/key → client label → unknown).
- `classify_usage(events, joined_ids, labels, policy)` → `WorkSplit` (work/non-work/
  unknown $ + event counts + per-user and per-key rollups + `non_work_share`).
- `gateway_decision(...)` → allow/deny for the **opt-in** gateway (never blocks `work`;
  blocks `non_work` only when `block_non_work`; blocks `unknown` only in strict mode).
- `format_worktype(split, policy)` — CLI readout. Wired as `outlay --worktype`.

## Surfaces (next)

- **Console — "Work vs non-work" card** on Spend/Governance: the split, top non-work
  spenders, and a key/repo registry editor. Visibility for everyone (read-only).
- **The stop control** (opt-in): a per-account/per-team toggle that sets
  `block_non_work` (and optional strict `block_unknown`), enforced by the gateway —
  surfaced clearly as in-path enforcement the customer turns on, with an audit trail
  (reuses the existing program-enforcement rails).
- **Client-side classifier** ships with the thin client (`modelpilot/router_classify`
  pattern): labels prompts locally, emits labels only.

## Risks / honesty

- **Don't over-claim non-work.** Default is conservative (`unknown`, not `non_work`).
  The non-work number is only as good as the labels/registry the customer provides —
  surface that, like the attribution fidelity tier.
- **Privacy of the classification itself.** The label is metadata, but "this engineer's
  spend is X% non-work" is sensitive — keep per-individual views to the individual /
  their manager, aggregate for leadership (same rule as cost attribution).
- **Enforcement is the customer's call and the customer's path.** Outlay recommends and
  reports; it never blocks. Blocking lives in the opt-in gateway they run.
