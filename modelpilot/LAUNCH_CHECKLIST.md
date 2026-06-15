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
      - Finding — **verified against the actual Commercial Terms of Service, eff. June 17, 2025**
        (full text read; not legal advice — still confirm with counsel + Anthropic in writing):
        - **Nothing in the Commercial Terms prohibits a BYOK proxy.** The *only* use restrictions
          (§D.4) are: no building a **competing** product / training competing models, no **reselling**
          the Services (except as Anthropic approves), no reverse-engineering, and no **supporting a
          third party** doing those. We do **none** of these — we route/optimize, we don't resell
          Claude (customer pays Anthropic directly on their own key; we bill 20% of *savings*).
        - **§A.1 expressly blesses our customers' use:** Anthropic permits Customer to use the Services
          "**including to power products and services Customer makes available to its own customers and
          end users**." A customer optimizing its own Claude traffic is squarely inside this grant.
        - **§D.5 anchors the liability the right way:** "**Customer is responsible for all activity
          under its account.**" A customer choosing to run our software against its own key keeps that
          responsibility — which is exactly the BYOK posture we want.
        - **§E.2 permits routing Customer Content to us as a processor:** Customer Content (Inputs/
          Outputs) is the Customer's Confidential Information, and the Customer may share its own
          Confidential Information with "**agents … that have a need to know**" who are bound to
          confidentiality. Our DPA/MSA make us that confidentiality-bound processor.
        - **The Feb-2026 crackdown is a *different document*.** §D.2 incorporates the **Usage Policy**
          and **Service Specific Terms** by reference; the "authentication & credential use" ban lives
          there and targets **Claude.ai subscription (Free/Pro/Max) credentials**, not API keys. Re-read
          those two policies, but BYOK-over-API is not what they restrict. We must **never** touch
          subscription credentials.
        - **Architecture is our strongest defense:** in thin-client / self-hosted mode the key and
          prompts **never leave the customer's box** — we're just software they run against their own
          key (like LiteLLM/Kong AI Gateway), which no term reaches.
      - **CATCH worth a customer disclosure — §K.3 indemnity exclusions.** Anthropic's copyright-
        indemnity to a customer (§K.1) is **excluded** to the extent a claim arises from "(a)
        **modifications made by Customer to the Services**" or "(b) the **combination of the Services
        or Outputs with technology … not provided by Anthropic**." Routing to a cheaper model is still
        "use of the Services," but **caching / fallbacks / semantic dedup could be argued as
        modification/combination** that narrows that indemnity. Action: add a one-line disclosure in
        our Terms that using ModelPilot may affect the scope of Anthropic's IP indemnity, and let
        customers disable cache/transforms if indemnity coverage matters to them. (Have counsel weigh.)
      - **Open risk to close before GA — the *fully hosted* gateway mode**, where customer traffic +
        key transit our servers. The Terms don't forbid it (we'd be the customer's §E.2 agent and they
        stay responsible under §D.5), **but** the customer is disclosing its key to us, and Anthropic's
        separate key best-practices guidance discourages key sharing. Steps: (1) keep the **default**
        deployment self-hosted/thin-client; (2) for hosted mode, contractually make the customer
        responsible for use under its key + name us an authorized processor (MSA/DPA already lean this
        way — confirm with counsel); (3) **email Anthropic** (sales/legal) describing the BYOK-proxy
        model and get written confirmation; (4) **never** touch subscription credentials; (5) note
        §M.4 — using a processor is not a prohibited "assignment" (customer stays the contracting
        party), so no consent needed on that basis.
      - **Usage Policy (eff. 2025-09-15) — read in full.** Two findings: (a) its scope line expressly
        names *"**passthrough access**"* as a recognized access mode — Anthropic's own policy
        contemplates requests reaching the Services through an intermediary; it only binds the end
        users to the content rules, it does **not** prohibit the proxy. (b) It imposes **flow-through
        customer obligations** we should restate in our Terms: High-Risk Use Cases (legal, healthcare,
        insurance, finance, employment/housing, academic testing, journalism) need **human-in-the-loop
        + AI-involvement disclosure**; any consumer-facing chatbot/agent must disclose it's AI. *Caveat:
        the "Do Not Abuse our Platform" sub-bullets render as a collapsed accordion — not yet read;
        that's the only spot left where a rate-limit-evasion / systematic-extraction clause could live.
        We don't evade limits or scrape, so low risk, but read it to be thorough.*
      - **Service Specific Terms (eff. 2026-06-08) — read in full. RESOLVES the API-specific question:
        there is NO authentication/credential-use, no anti-proxy, and no API resale clause** beyond
        Commercial §D.4. Notable adjacent items: §E **Development Partner Mode** is an opt-in that lets
        Anthropic **train on Customer Content** — ensure customers don't enable it unknowingly; §F
        **Covered Models** lets Anthropic **retain Inputs/Outputs for safety review even under ZDR** —
        so our privacy claims must be scoped to *our* systems (we don't see prompts), not to Anthropic's
        own retention, which we don't control.
      - **API Key Best Practices (eff. 2026-03-16) — guidance, not contract — and it's permissive:** it
        does **not** forbid giving your key to a third-party tool. It says *"exercise caution with
        third-party tools … you are giving the developer of that tool access to your Console account …
        if you don't trust their reputation, don't trust them with your key,"* and *"always add your API
        key as an **encrypted secret**."* This frames hosted/BYOK-to-a-vendor as a **permitted trust/
        security decision the customer makes** — exactly our hosted mode — provided we store keys
        encrypted and earn the trust. (Also: GitHub secret-scanning → Anthropic auto-deactivates leaked
        keys; reinforces rotating the leaked key + our .gitignore discipline.)
      - **CONCLUSION: the BYOK-proxy model is permitted across all incorporated docs.** Default stays
        self-hosted (no term even reaches it); hosted mode is consistent with the key-guidance if keys
        are encrypted + customer-chosen. Residual to-dos: (1) read the one collapsed Usage-Policy
        section; (2) add flow-through Usage-Policy + §K.3-indemnity + ZDR/Covered-Models disclosures to
        our customer Terms; (3) optional written Anthropic confirmation for enterprise hosted comfort;
        (4) never touch subscription credentials.
      - Sources (all read in full): **Commercial Terms eff. 2025-06-17 (§§A.1, D.2, D.4, D.5, E.2,
        K.1/K.3, M.4); Usage Policy eff. 2025-09-15; Service Specific Terms eff. 2026-06-08; API Key
        Best Practices support article eff. 2026-03-16.** Plus the Feb-2026 third-party-access
        clarification (subscription-credential ban — a different access path, not API BYOK).
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

## Compliance readiness (SOC 2 / HIPAA) — the #1 ICP unlock
Our beachhead (healthcare, legal, fintech — see `ICP.md`) buys on this. The architecture already
gives us the strongest possible story ("PHI/prompts physically can't reach us"), but regulated
buyers also want a paper trail. This is a **founder + auditor process**, not code — sequence it so
spend tracks real demand (don't pay for SOC 2 before a prospect asks). Do **not** claim any cert
we don't hold; the `/healthcare` page and `/security` page stay honest until each box is checked.

Order of operations:
- [ ] **Form the entity first.** SOC 2 / BAAs are signed by a legal entity; the audit scopes to it.
      (Gated by the S-corp/LLC item above.)
- [ ] **Designate a security owner** (you, to start) and write the baseline **security policies**
      a SOC 2 needs: access control, change management, incident response (we have
      `INCIDENT_RESPONSE.md` — adopt it formally), vendor management, data classification,
      business continuity, acceptable use. Most are short.
- [ ] **Adopt a compliance automation tool** (Vanta / Drata / Secureframe) — they give the policy
      templates, evidence collection, and an auditor network. Budget ~$7–15k/yr + audit fee.
- [ ] **Scope SOC 2 Type I first** (point-in-time; ~weeks) to get a report in hand for sales, then
      **Type II** (observation window, typically 3–6 months) when a deal needs it.
- [ ] **Get an independent pen-test** of the console + brain; keep a shareable **summary** (not the
      raw findings) for security questionnaires.
- [ ] **HIPAA path (only when handling PHI):** complete a **HIPAA gap assessment**, stand up a
      **BAA template** (counsel-reviewed), and confirm **Anthropic will sign a BAA** with us for the
      downstream model calls (or document that PHI in prompts is the customer's direct relationship
      with Anthropic under their key — which is our actual architecture). Keep the `/healthcare`
      "not yet certified, ask us about a BAA" language until the BAA + assessment exist.
- [ ] **Build a reusable security questionnaire response** (SIG-lite / CAIQ): data flow diagram
      showing prompts/keys never transit us, subprocessor list, encryption-at-rest/in-transit,
      retention, deletion, breach notification. This unblocks most mid-market reviews **before**
      a full SOC 2.
- [ ] **On-prem / VPC brain deploy** option for the most paranoid enterprises (max privacy = max
      moat; see `ICP.md` moat-hardening #2).
