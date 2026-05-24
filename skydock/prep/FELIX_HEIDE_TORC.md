# Prep: Felix Heide — Head of AI, Torc Robotics

**LinkedIn:** linkedin.com/in/felix-heide-7b7bb889/
**Outreach variant:** A (technical engineering leader)
**Why he's top of the priority list:** Most academically-accessible target on the list. Active on LinkedIn. Responds to technical pitches. Dual-affiliation means he engages publicly more than typical industry leads.

---

## Bio refresher

- Princeton CS Assistant Professor — leads Princeton Computational Imaging Lab
- Head of AI at Torc Robotics (Daimler Truck's autonomy subsidiary)
- Founded Algolux — perception startup acquired by Torc 2024
- PhD UBC; postdoc Stanford; undergrad Siegen
- NSF CAREER Award 2021; Sony Young Faculty Award 2021
- Research intersection: optics, machine learning, computer vision

## Recent context (last 12 months)

| Item | Detail | Relevance to thesis |
|---|---|---|
| ICCV 2025 paper | "Self-Supervised Sparse Sensor Fusion for Long Range Perception" — extends camera-LiDAR perception to 250m; +26.6% mAP, -30.5% Chamfer Distance on LiDAR forecasting | Long-range perception is exactly where independent overhead ground-truth helps. Hook this. |
| CES 2026 demo | Torc demoed "Hallucination-Free Video Generation" for AV training | Major signal: Torc is investing in *generated* training data, but is interested in *hallucination-free*. Real aerial captures are the anti-hallucination input source. |
| CVPR 2024 | 9 papers from Torc-Princeton team | Heavy academic output → he engages with technical conversations seriously |
| Algolux acquisition | Closed late 2023 / early 2024 | He sold his startup; understands founder discovery calls. Will not be condescending. |

## Technical context to know

- Torc is **truck-focused** autonomy (Daimler Freightliner Cascadia). Long-range (highway speeds), repetitive routes, smaller operating envelope than passenger AVs.
- Operating envelope: hub-to-hub freight in the Southwest US (Texas, NM, AZ). Phoenix, Albuquerque, El Paso, Dallas, Fort Worth.
- Sensor stack: lidar + cameras + radar. They acquired **Algolux** for low-light camera ISP / perception, and **Innoviz** is their LiDAR partner.
- Their perception challenge: **long-range detection at highway speeds**. A truck at 65mph traveling on I-10 needs 250m+ confident detection to brake in time. Most overhead aerial captures wouldn't help long-range (drone field-of-view is fixed) — but might help at the highway-junction edge cases.

## Specific questions to ask HIM (vs. generic)

1. **"Your ICCV paper extended perception to 250m — at highway speeds in a truck application, is the gap now confidence/precision in that 250m envelope, or extending it further?"** → tells you whether validation pain exists at long-range
2. **"The CES 2026 hallucination-free video generation demo was interesting — what's the real-data input feeding that pipeline today? Is it Torc's own fleet drives, or are you augmenting with external sources?"** → directly tests whether aerial real-data is plausibly useful as a hallucination-prevention input
3. **"Trucks have a relatively small operating envelope vs. robotaxis — does that change the geographic-diversity question? Do you need data from cities you don't operate in?"** → tests Thesis C in a truck-specific frame
4. **"As a former founder, what would you have wanted to hear from a vendor doing customer discovery on you at the Algolux stage?"** → gold-mine question, gets you mentorship-mode advice

## Red flags / sensitive areas

- **Algolux was acquired by Torc.** Don't pitch a product that looks like "you should buy us" — he just sold his last company; he's the buyer side now, not the seller side.
- **Don't compare to Algolux** unless he brings it up. Algolux did camera ISP, not aerial capture; the analogy is weak.
- **Princeton vs. Torc context-switching.** He has both academic and industry hats. Lead with the academic framing (you read his paper) but make sure the questions are industry-grounded.

## What success looks like

**Minimum viable:** 30-min Zoom in next 4 weeks. Felix gives an honest "yes pain exists" or "no, synthetic+self-labels are sufficient" answer to question 2.

**Stretch:** Felix offers to introduce you to (a) the Torc perception engineering manager who would own a pilot procurement, or (b) one other AV company's perception lead in his network.

**Home run:** Felix says "we'd run a 5-capture pilot at $X to test this if you can deliver hub-to-hub I-10 corridor captures."

## Suggested follow-up after call

Within 24h: thank-you email + 3-sentence summary of what you heard him say + ask the referral question. Within 1 week: send him the relevant ICCV-paper-adjacent figure from your simulation work, framed as "you said X about long-range, here's what we modeled."

---

*Prep compiled May 2026. Sources: Torc Robotics publications, CES 2026 LinkedIn posts, Princeton CS faculty page, ICCV 2025 proceedings.*
