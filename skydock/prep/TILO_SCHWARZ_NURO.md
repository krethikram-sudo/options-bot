# Prep: Tilo Schwarz — VP Engineering, Nuro Driver

**LinkedIn:** linkedin.com/in/tilo-schwarz-42289b166/
**Outreach variant:** A (technical engineering leader)
**Why he's top of the priority list:** Nuro is in the middle of an aggressive scaling moment (CA + Nevada driverless permits in last 30 days; Uber/Lucid late-2026 launch ramping). When orgs are scaling, validation infrastructure becomes a real budget item. Tilo personally owns the Nuro Driver perception stack as VP Eng.

---

## Bio refresher

- VP Engineering, Nuro Driver (their AV stack product)
- Background sourceable on LinkedIn — verify before call
- Active publicly: recently attended 2025 Traffic Safety Summit with Zero Fatalities Nevada
- Reports to Andrew Clare (CTO) and Jiajun Zhu (co-founder, CEO)

## Recent context (last 6 months — very active)

| Date | Item | Relevance |
|---|---|---|
| CES Jan 2026 | Lucid + Nuro + Uber unveiled "global robotaxi" — Lucid Gravity SUV with Nuro Driver stack | Major product launch; perception validation is now front-and-center for safety case |
| Dec 2025 | Autonomous on-road testing began in SF Bay Area | Real-world deployment, not just closed circuit |
| May 5, 2026 | Nuro received Nevada driverless testing permit (TechCrunch) | Driverless = no safety driver = perception confidence is do-or-die |
| Recent | California driverless permit also granted | Two-state operation expanding |
| Forward | Late 2026: first commercial Uber-app robotaxi rides in a major US city | 6-month window to commercial launch |
| Forward | 20,000+ robotaxi fleet over 6 years per partnership | Massive scaling = perception failures at scale = validation budget likely |

## Technical context to know

- Nuro Driver is their **AV software stack** — distinct from their original autonomous delivery vehicle hardware
- Operating environment: **Lucid Gravity SUV** (passenger robotaxi, not the original Nuro pod). This is a major architectural pivot — passenger occupancy means different safety case than empty delivery vehicle.
- Sensor stack on Lucid Gravity: high-res cameras + solid-state LiDAR + radars
- Perception architecture: per the company, built on a "unified foundation model — simple, performant, scalable"
- Operating cities: starting in SF Bay Area; Las Vegas proving ground for closed-circuit testing
- Test methodology: prototype vehicles with safety operators (now transitioning to driverless under the new permit)

## Specific questions to ask HIM (vs. generic)

1. **"Going from closed-circuit at Vegas to public-road driverless in CA is a massive perception validation jump — what's your current methodology for proving the perception stack is good enough for that transition?"** → opens the validation pain directly
2. **"The unified foundation model approach makes interpretability harder — when perception fails in the field, how do you triangulate whether it's a sensor issue, a model issue, or a data-coverage issue? Do you currently use any out-of-distribution ground-truth signal?"** → probes whether they'd value an independent reference
3. **"Lucid Gravity has a specific sensor configuration — does that constrain or free you on perception training data sources? Can you reuse Nuro pod-era data, or is it a fresh start?"** → tests whether they have a data-diversity gap during the platform pivot
4. **"With 20,000 vehicles planned over 6 years across multiple US cities, you'll be operating in cities you've never had a fleet in. How are you planning to bootstrap perception for those new cities?"** → directly tests Thesis C (geographic diversity)

## Red flags / sensitive areas

- **Nuro has had layoffs before** (2022, 2023). Don't make assumptions about team size or budget — let him tell you.
- **The Uber partnership is the story.** Lead questions through the lens of "what changes with Uber+Lucid+commercial launch" — that's the strategic context he's living in.
- **Tilo's title is VP Eng, Nuro Driver — not VP Perception.** He owns perception but it's nested within the broader Driver stack. Don't pitch as if perception is the only thing he cares about.
- **Safety-case sensitivity.** Driverless = regulatory exposure. Don't suggest their current validation is inadequate; ask how they validate, listen.

## What success looks like

**Minimum viable:** 30-min call in next 3 weeks. Tilo characterizes Nuro's current validation methodology and confirms or denies whether independent ground-truth has value.

**Stretch:** Tilo connects you to Nuro's procurement / pilot eval contact for AV-data tooling.

**Home run:** "We'd consider a pilot once we have data quality requirements written. Send us what you've delivered so far." Even a "send us a sample of capture data for [specific Bay Area intersection]" is gold — that's a concrete next step.

## Suggested follow-up after call

Within 24h: thank-you + summary + the referral ask + an offer ("happy to share our simulation framework / a sample capture if it'd help you internally evaluate"). Within 2 weeks: a tailored 1-page write-up of "what aerial capture looks like for the SF Bay Area corridors Nuro is testing" — proves you've translated the conversation into specifics.

---

*Prep compiled May 2026. Sources: TechCrunch (May 5 2026), Lucid Motors press, Nuro company page, CES 2026 coverage.*
