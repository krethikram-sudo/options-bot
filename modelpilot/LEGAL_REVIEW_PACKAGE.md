# ModelPilot — Legal Document Review Package
*Updated 2026-06-17 (second-pass revisions applied). Source: `modelpilot/site/legal/`. Still NOT final/counsel-reviewed — draft banners stay until an attorney signs off.*

## Revision status
**Pass 1 (resolved):** Delaware governing law (Terms §11/MSA §11); §10 indemnity rewritten to make no representation about Anthropic's indemnity; hosted-gateway carve-outs across all six docs; liability-cap split flagged intentional; explicit AUP Usage-Policy suspension right.
**Pass 2 (this revision):** Tightened hosted-mode wording everywhere from "transits our systems" to **"processed in memory solely to route the request (read by our classifier to select a model) and not persisted"** — accurate to how routing actually inspects the prompt. Added a self-hosted confirmation that classification runs locally and no ModelPilot system inspects prompt content (DPA §2); scoped DPA §5 architecture claim to default deployment; added a hosted-mode note to the cloud-hosting subprocessor row.

**Still pending — founder:** subprocessor vendor names (hosting + email); entity name / signatures / effective dates (blocked on the DE C-corp).
**Still pending — attorney:** SCC module/annexes (DPA §10); California enforceability of the AUP "competing service" clause; final sign-off.

---

# 1. Terms of Service

*(source: `legal/terms.html`)*

Terms of Service (template) — ModelPilot

### Terms of Service

Template / draft. Published for review; not legal advice and not yet
counsel-reviewed. Have a qualified attorney finalize before you rely on it.

#### 1. The service

ModelPilot ("we") provides a drop-in proxy and hosted console that route Claude API requests
to cost-efficient models and report savings ("Service"). You ("Customer") use the Service with
your own Anthropic account and API key; we are not a party to your agreement with Anthropic and
do not resell model usage.

#### 2. Accounts & acceptable use

You are responsible for your account, your users, and keeping credentials secure. Your use must
comply with our Acceptable Use Policy, applicable law, and
Anthropic's usage policies.

#### 3. Fees

After any free trial, fees are 20% of the realized savings the Service delivers in a
billing cycle, billed via our payment processor. "Realized savings" is the metered difference
between the baseline cost (the model you requested) and the actual cost of the model that ran, as
computed by the Service. If no savings are delivered, no fee is owed for that usage. Taxes are
your responsibility where applicable.

#### 4. Savings disclaimer

Savings figures are estimates measured from your traffic, not guarantees. Actual results
depend on your workload, prompts, cache state, and model availability. We do not warrant any
particular savings percentage or dollar amount. Routing aims to preserve quality but model
outputs are probabilistic; you remain responsible for evaluating outputs for your use case.

#### 5. Availability

The proxy is designed to fail open — if the Service is unreachable, requests pass through
to the Claude API unrouted. We do not guarantee uninterrupted operation and, except where a
separate written SLA applies, the Service is provided without uptime commitments.

#### 6. Warranties

THE SERVICE IS PROVIDED "AS IS" AND "AS AVAILABLE" WITHOUT WARRANTIES OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND NON-INFRINGEMENT, TO
THE MAXIMUM EXTENT PERMITTED BY LAW.

#### 7. Limitation of liability

TO THE MAXIMUM EXTENT PERMITTED BY LAW, WE WILL NOT BE LIABLE FOR INDIRECT, INCIDENTAL, SPECIAL,
CONSEQUENTIAL, OR PUNITIVE DAMAGES, OR LOST PROFITS/DATA. OUR TOTAL LIABILITY FOR ANY CLAIM IS
LIMITED TO THE FEES YOU PAID US IN THE THREE (3) MONTHS BEFORE THE EVENT GIVING RISE TO THE
CLAIM. You are responsible for your own Anthropic/model-provider charges. (This three-month cap
applies to self-serve customers on these Terms; customers under a negotiated
MSA have a separate, twelve-month cap — the difference is intentional.)

#### 8. Data

Our handling of data is described in the Privacy Policy and, for
personal data processed on your behalf, the DPA. In the default
self-hosted / thin-client deployment, prompt content, model outputs, and your API key are not
transmitted to us by the proxy. If you opt into a hosted-gateway deployment, your API key
and request content are processed in memory solely to route the request (read by our classifier to
select a model) and are not persisted — handled as your processor under the DPA; we do not store
prompt content or model outputs.

#### 9. Term & termination

You may stop using and cancel at any time. We may suspend or terminate for breach (including AUP
violations) or non-payment. Sections that by their nature should survive (fees accrued, warranty
disclaimers, liability limits) survive termination.

#### 9a. Early access

The Service is offered as an early-access product. Features may change, and we may adjust or
deprecate functionality as we improve it; we'll communicate material changes. Enterprise customers
can request a negotiated MSA with support and (optionally) SLA terms.

#### 10. Your Anthropic agreement & related disclosures

You use the Service with your own Anthropic account and API key, under your own
agreement with Anthropic (their
Commercial Terms, Usage Policy, and Service Specific Terms). We are not a party to that agreement
and do not resell model access. You remain responsible for complying with it, including:

Usage Policy compliance flows through to you. Anthropic's Usage Policy applies to all
inputs, including those reaching the model through a passthrough/proxy. Where you operate a
High-Risk Use Case (e.g., legal, healthcare, insurance, finance, employment or housing,
academic testing, or journalistic content), Anthropic requires a qualified human in the
loop and an AI-involvement disclosure to your end users. Any consumer-facing chatbot
or interactive agent must disclose to users that they are interacting with AI. You are
responsible for meeting these requirements.

- Anthropic's IP indemnity is governed solely by your agreement with Anthropic. Your
agreement with Anthropic — not ModelPilot — determines the scope of any copyright or
IP indemnity Anthropic provides, including any exclusions (for example, exclusions that can apply
where outputs result from modifications to, or combination of, the Services with technology not
provided by Anthropic). ModelPilot makes no representation or warranty as to whether any
feature of the Service does or does not affect that indemnity. Because the Service offers
optional features (e.g., model substitution, response caching, semantic caching, fallbacks) that
you can enable or disable, you are responsible for determining — and confirming directly
with Anthropic — whether your configuration affects your coverage. This paragraph is a
disclosure for your awareness; it is not legal advice and is not a statement about your coverage.

- Anthropic's own data handling is outside our control. Our privacy commitments describe
only what ModelPilot does (in the default self-hosted deployment, the proxy does not
transmit your prompts, outputs, or API key to us). Anthropic's handling of your data is governed by your Anthropic agreement —
for example, Anthropic may retain inputs and outputs for safety review on certain models even
where zero-data-retention would otherwise apply, and Anthropic's Development Partner / data
opt-in setting permits training on your content if you enable it. Do not enable that setting
unless you intend that result; we never enable it on your behalf.

#### 11. Changes; governing law

We may update the Service and these terms; material changes will be communicated. These terms are
governed by the laws of the State of Delaware, without regard to its conflict-of-laws rules,
and the parties submit to the exclusive jurisdiction of the state and federal courts located in
Delaware (final venue language to be confirmed in counsel review). If any provision is
unenforceable, the rest remain in effect.

Questions: krethikram@gmail.com
· Privacy · Acceptable Use ·

---

# 2. Privacy Policy

*(source: `legal/privacy.html`)*

Privacy Policy (template) — ModelPilot

### Privacy Policy

Template / draft. Published for review; not legal advice. Finalize
with counsel for your jurisdiction (GDPR/CCPA specifics, etc.).

The short version: in the default self-hosted / thin-client deployment, your
prompts, model outputs, and API key never reach us — we process only account details and aggregate,
metadata-only usage figures. If you opt into the hosted-gateway deployment, your request
content and API key are processed in memory solely to route the request (read by our classifier to
select a model) and are not persisted (handled as your processor under the
DPA); we do not store prompt content or model outputs.

#### What we collect

Account data: name/email/company of authorized users; authentication data (password
hashes, not plaintext).

- Operational metadata: task category, token counts, model identifiers, cost/savings
figures, status and routing flags — and any opt-in per-request metadata you send.

- Billing data: handled by our payment processor; we store usage amounts and invoices.

- We do NOT store prompt text or model outputs. In the default self-hosted deployment the
proxy never transmits them (or your API key) to us, and our endpoints reject payloads that
contain them. In the optional hosted-gateway deployment they are processed in memory only to route
the request (read by our classifier to select a model) and are not persisted.

#### How we use it

To provide and secure the Service, compute savings and billing, send service communications
(e.g. password resets, budget/review alerts, invoices), and improve routing in aggregate. We do
not sell personal data.

#### Sharing & subprocessors

We share data only with the service providers needed to run the Service (hosting, payments,
email), listed at /legal/subprocessors, under appropriate
data-protection terms. In the default self-hosted deployment your prompt content goes from your
infrastructure directly to Anthropic with your key — not via us; in the hosted-gateway deployment
it is processed in memory only to route the request (read by our classifier to select a model) and
is not persisted.

#### Retention & your rights

We retain account and aggregate billing data for as long as your account is active and as needed
for legal/operational purposes. You can export your data from the console and request access,
correction, or deletion by emailing krethikram@gmail.com.
Where applicable (GDPR/UK GDPR/CCPA), you have rights to access, rectify, delete, port, and object;
for personal data we process on your behalf as a processor, see the
DPA.

#### Cookies

The console uses a single, HMAC-signed session cookie to keep you signed in. No third-party
advertising or tracking cookies.

#### Security & contact

Security practices are described at /security (TLS, encryption at
rest, hashed credentials, least-privilege access). Questions or requests:
krethikram@gmail.com.

Terms ·
DPA · Subprocessors ·

---

# 3. Acceptable Use Policy (AUP)

*(source: `legal/aup.html`)*

Acceptable Use Policy (template) — ModelPilot

### Acceptable Use Policy

Template / draft. Published for review; not legal advice.

To keep the Service safe and reliable for everyone, you agree not to:

use the Service unlawfully, or in violation of Anthropic's usage policies or any
model provider's terms;

- attempt to probe, scan, or breach the Service or its security; circumvent entitlement,
billing, or rate limits; or interfere with other customers;

- resell, sublicense, or provide the Service to third parties except as permitted in writing;

- reverse engineer or attempt to extract non-public routing logic, or use the Service to build
a competing service;

- send malware, conduct denial-of-service, or generate traffic designed to abuse the Service;

- infringe others' rights, or process data you are not authorized to process.

You are responsible for content you send through your own API key to the model provider. We may
suspend or terminate access for violation of this Policy — including violations of Anthropic's Usage
Policy or any model provider's terms — with notice where practicable. Report abuse to
krethikram@gmail.com.

Terms ·

---

# 4. Master Services Agreement (MSA)

*(source: `legal/msa.html`)*

Master Services Agreement (template) — ModelPilot

### Master Services Agreement

Template / draft for enterprise deals. Self-serve customers are covered
by the click-through Terms; this MSA is for negotiated contracts.
Not legal advice — have counsel finalize before signing.

#### 1. Agreement & order forms

This MSA governs Customer's use of the ModelPilot service ("Service"). Specific subscriptions,
volumes, and pricing are set out in one or more mutually executed Order Forms that
incorporate this MSA. If an Order Form conflicts with this MSA, the Order Form controls for that order.

#### 2. The Service & responsibilities

We provide the routing proxy + hosted console described in our docs. Customer uses the Service with
its own model-provider account and API key, is responsible for its users and content, and will
comply with the Acceptable Use Policy and applicable law. We are not a
party to, and do not resell, Customer's model-provider usage.

#### 3. Fees, taxes & payment

Fees are as stated in the Order Form (typically 20% of realized savings, metered as the
baseline-minus-actual cost the Service delivers), invoiced per the stated cycle with net terms.
Fees are exclusive of taxes, which are Customer's responsibility except for taxes on our income.
Late amounts may accrue interest as permitted by law.

#### 4. Confidentiality

Each party will protect the other's Confidential Information with reasonable care, use it only to
perform under this MSA, and disclose it only to personnel/advisors bound by confidentiality. This
does not cover information that is public, independently developed, or rightfully received from a third party.

#### 5. Intellectual property

Each party retains all rights in its pre-existing IP. We retain all rights in the Service and its
underlying technology (including routing logic); Customer retains all rights in its data and
applications. If Customer provides feedback, it grants us a perpetual, royalty-free license to use it.

#### 6. Data protection

The DPA and Privacy Policy are
incorporated by reference. In the default self-hosted / thin-client deployment, prompt content,
model outputs, and Customer's API key are not transmitted to us; in the optional hosted-gateway
deployment they are processed in memory only to route the request (read by our classifier to select
a model), are not persisted, and are handled per the DPA. Security measures are described at
/security.

#### 7. Warranties & disclaimer

We warrant we will provide the Service in a professional manner. EXCEPT AS EXPRESSLY STATED, THE
SERVICE IS PROVIDED "AS IS" WITHOUT WARRANTIES OF ANY KIND. Savings figures are estimates measured
from Customer's traffic, not guarantees; model outputs are probabilistic and Customer is responsible
for evaluating them.

#### 8. Indemnification

We will defend Customer against third-party claims that the Service, as provided, infringes that
party's IP, and Customer will defend us against claims arising from Customer's data, content, or use
in breach of this MSA — each subject to prompt notice, control of defense, and cooperation.

#### 9. Limitation of liability

NEITHER PARTY IS LIABLE FOR INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES OR
LOST PROFITS/DATA. EXCEPT FOR EXCLUDED CLAIMS (e.g., confidentiality breach, indemnity, Customer's
payment obligations), EACH PARTY'S TOTAL LIABILITY IS CAPPED AT THE FEES PAID OR PAYABLE IN THE
TWELVE (12) MONTHS BEFORE THE CLAIM. (This twelve-month cap is for negotiated/enterprise customers
under this MSA; self-serve customers on the click-through Terms have a
separate, three-month cap — the difference is intentional.)

#### 10. Term, termination & survival

This MSA runs for the term of the Order Form(s). Either party may terminate for uncured material
breach (30 days' notice). On termination, Customer stops using the Service and we delete or return
Customer personal data per the DPA. Sections that should survive (fees, confidentiality, IP,
warranty disclaimers, liability limits) survive.

#### 11. General

Optional: uptime SLA, support tier, and security commitments (e.g., SOC 2) may be attached as
exhibits. This MSA is governed by the laws of the State of Delaware, without regard to its
conflict-of-laws rules, and the parties submit to the exclusive jurisdiction of the state and federal
courts located in Delaware. Insurance, publicity/logo use, assignment, and force majeure terms
to be completed with counsel.

Enterprise terms: krethikram@gmail.com
· Terms · DPA ·

---

# 5. Data Processing Addendum (DPA)

*(source: `legal/dpa.html`)*

Data Processing Addendum (template) — ModelPilot

### Data Processing Addendum

This DPA governs ModelPilot's processing of personal data on your behalf.

Template / draft. This is a starting point published for your review — it
is not legal advice and is not yet a counsel-reviewed, executable contract. For a signed DPA (or to
redline this one), email krethikram@gmail.com.

#### 1. Roles & definitions

"Customer" is the controller of the personal data; "ModelPilot" (the provider of the ModelPilot
service, the "Service") acts as processor on Customer's documented instructions. "Personal data,"
"processing," "controller," "processor," and "data subject" have the meanings given under applicable
data-protection law (incl. the GDPR/UK GDPR and CCPA where relevant). This DPA forms part of the
agreement between the parties for use of the Service.

#### 2. Scope & nature of processing

The Service routes Claude API requests to cost-efficient models. In the default self-hosted /
thin-client deployment, prompt content, model outputs, and Customer's API keys are not transmitted to
or processed by ModelPilot — they pass from Customer's infrastructure directly to Anthropic using
Customer's key, and any task classification runs locally on Customer's own infrastructure (no
ModelPilot system inspects prompt content). (In the optional hosted-gateway deployment,
Customer's request content and API key are processed in memory solely to route the request — read by
ModelPilot's classifier to select a model — and are not persisted; ModelPilot acts as processor for
that processing and does not store prompt content or model outputs.) Apart from that transient
routing in hosted mode, ModelPilot processes only:

account data (e.g. the email address and company of authorized users);

- operational metadata (task category, token counts, model identifiers, cost/savings figures, status
and routing flags) — including any opt-in per-request metadata Customer chooses to send; and

- aggregate usage figures used to calculate billing.

Duration of processing is the term of the agreement; the subject matter is provision of the Service;
categories of data subjects are Customer's authorized users.

#### 3. Customer instructions

ModelPilot processes personal data only on Customer's documented instructions (including via the
Service's configuration), unless required by law, in which case ModelPilot will inform Customer where
legally permitted.

#### 4. Confidentiality

ModelPilot ensures persons authorized to process the personal data are bound by appropriate
confidentiality obligations.

#### 5. Security

ModelPilot implements appropriate technical and organizational measures, including TLS in transit,
encryption at rest, hashed credentials, scoped/revocable API keys, least-privilege access, and (in the default self-hosted deployment) an
architecture in which prompt content never reaches ModelPilot. Current measures are described at
/security.

#### 6. Subprocessors

Customer authorizes ModelPilot to engage the subprocessors listed at
/legal/subprocessors. ModelPilot imposes data-protection
obligations on subprocessors no less protective than this DPA, remains responsible for their
performance, and will give Customer notice of intended changes with a reasonable opportunity to object.

#### 7. Data subject rights

Taking into account the nature of the processing, ModelPilot assists Customer with appropriate
technical and organizational measures, insofar as possible, to respond to data-subject requests
(access, rectification, erasure, portability, objection).

#### 8. Personal data breach

ModelPilot notifies Customer without undue delay after becoming aware of a personal data breach
affecting Customer's personal data, with information reasonably available to assist Customer's own
obligations.

#### 9. Deletion & return

On termination, and at Customer's choice, ModelPilot deletes or returns the personal data it processes
on Customer's behalf, except where retention is required by law. Customer may also export data and
request deletion during the term.

#### 10. International transfers

Where processing involves transfers of personal data subject to GDPR/UK GDPR to a country without an
adequacy decision, the parties agree the applicable Standard Contractual Clauses (and UK Addendum,
where relevant) are incorporated by reference and completed with the details in this DPA and the
subprocessors page.

#### 11. Audit & information

ModelPilot makes available information reasonably necessary to demonstrate compliance with this DPA
and, on reasonable request and subject to confidentiality, supports audits consistent with applicable
law.

#### 12. General

If there is a conflict between this DPA and the agreement on data-protection matters, this DPA
prevails. Liability is subject to the limitations in the agreement.

To execute or redline this DPA, contact
krethikram@gmail.com. ·
Security · Subprocessors

---

# (Supporting) Subprocessors

*(source: `legal/subprocessors.html`)*

Subprocessors — ModelPilot

### Subprocessors

The third-party services ModelPilot relies on to deliver the product. We'll keep this
page current and give notice of material changes.

Important: in the default self-hosted / thin-client deployment, your prompt
content goes directly from your infrastructure to Anthropic using your own API key — it does not
pass through ModelPilot, so Anthropic is your model provider, not ModelPilot's subprocessor for prompt
content. In the optional hosted-gateway deployment, request content is processed in memory by
ModelPilot only to route it (read by our classifier to select a model) and is not persisted. Except
for that transient routing in hosted mode, the services below process only account data and
aggregate/opt-in metadata.

SubprocessorPurposeData processed

AnthropicClaude model inference (called directly by your gateway with your key)Your prompts & outputs — sent by you, not via ModelPilot

Cloud hosting provider
(our brain / console / ingest)Runs ModelPilot's backend servicesAccount data, aggregate savings, opt-in metadata — no prompt content. In hosted-gateway mode, also transiently processes request content in memory for routing (not stored).

StripePayments & subscription billingBilling contact & payment details (held by Stripe), usage amounts

Email provider
(transactional email, if configured)Password resets, budget & review alertsEmail address, message content of the notification

This list reflects our current architecture. We will list the specific hosting and
email vendors by name here before onboarding any customer that requires a named-subprocessor list
(e.g., under GDPR Art. 28); contact us for the specifics applicable to your account. To be notified of
changes, email krethikram@gmail.com.

← Security & trust ·

---