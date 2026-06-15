# Launch checklist (INTERNAL)

What's done in the product vs. what's **yours to do** before taking real customers/money.
Not legal/tax advice — run the legal + financial items past a startup attorney and a CPA
(a few hours now is cheap insurance).

## Done in the repo
- [x] Customer legal docs (templates — **need counsel review**): Terms, Privacy Policy,
      Acceptable Use, DPA, Master Services Agreement (enterprise), Subprocessors list,
      Security/Trust page — all under `modelpilot/site/legal/` + `/security`.
- [x] Signup records **Terms + Privacy consent** (timestamp on the account).
- [x] Early-access/beta notice on signup + in the Terms.
- [x] Privacy-by-architecture: prompts/outputs/API key never reach us; endpoints reject
      sensitive payloads (422); aggregate-only metering; opt-in metadata logs.
- [x] Status page (`/status`), fails-open routing, API keys, spend caps, audit trails.
- [x] One-command deploy (`docker-compose.yml` + `deploy/`).

## Legal / corporate — YOURS TO DO
- [ ] **Form the entity.** LLC to bootstrap; **Delaware C-corp** if you'll raise VC (decide
      early — converting later is painful). Then EIN + business bank account; keep finances
      separate (the entity is what shields personal assets, not the disclaimers).
- [ ] **Have counsel finalize the templates** above and set governing law/venue.
- [ ] **Verify the model provider's terms** allow a hosted proxy using the customer's own key
      (we don't resell tokens — but confirm Anthropic's commercial/API terms permit this). **Load-bearing.**
- [ ] **Trademark:** knockout-search "ModelPilot" (may be taken); file a word mark if clear.
- [ ] **IP:** strategy is trade-secret (split architecture keeps routing IP server-side) +
      contractor IP-assignment/NDAs. A provisional patent only if a genuinely novel method is
      worth it — otherwise skip and keep shipping. Code copyright is automatic.

## Finance / ops — YOURS TO DO
- [ ] **Sales tax / VAT** on SaaS (turn on Stripe Tax; confirm nexus with your CPA).
- [ ] **Tech E&O + cyber-liability insurance** before prod traffic routes through you.
- [ ] **Stripe** live keys + a metered price (1 unit = $1 savings @ $0.20); webhook secret.

## Security / go-live — YOURS TO DO
- [ ] **Rotate the Anthropic API key** pasted in chat earlier (treat as compromised).
- [ ] Buy a real **domain**; replace the `app.modelpilot.app` / `modelpilot.pages.dev`
      placeholders; serve the console over **HTTPS** + `CONSOLE_SECURE_COOKIES=1`.
- [ ] Change the **seeded admin password**; set a strong `CONSOLE_SECRET`.
- [ ] Back up the `braindata` / `ingestdata` / `consoledata` volumes (accounts, billing,
      metering — no prompt data).

## When a deal/regulation requires it
- [ ] **SOC 2 Type II** (start the process when an enterprise prospect asks).
- [ ] **HIPAA + BAA** only if you'll handle PHI (today: "not yet" — keep it accurate).
- [ ] SSO/SCIM are built; wire to the customer's IdP per deal.

## Marketing honesty (ongoing)
- [ ] Keep savings claims substantiated ("typically 20–40%, measured on your traffic") — never
      inflate (FTC truth-in-advertising). The site copy already does this.
