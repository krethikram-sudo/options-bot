# Voluntary Product Accessibility Template (VPAT®) — Accessibility Conformance Report

**Product:** Outlay — AI/LLM spend-attribution & FinOps console
**Version:** current (rolling SaaS)
**Report date:** June 2026
**VPAT version:** 2.5 (WCAG 2.1, Revised Section 508, EN 301 549)
**Contact:** hello@outlay-ai.com

> **Status: DRAFT / self-assessment.** This ACR is produced from the team's own
> testing (automated axe-core audits passing with zero violations, plus manual
> keyboard and screen-reader spot checks). It has not yet been validated by an
> independent third-party accessibility auditor. We will commission an
> independent VPAT before final state-government submission. Maryland procurement
> note: this report explicitly covers **Nonvisual Access (NTIAA / COMAR
> 14.33.02)** expectations alongside WCAG 2.1 AA and Section 508.

## Conformance levels used in this report

- **Supports** — meets the criterion across the product.
- **Partially Supports** — meets some functionality / some content.
- **Does Not Support** — majority does not meet the criterion.
- **Not Applicable** — criterion does not apply to the product.

## Scope of evaluation

The Outlay web console (`/app/*`): authentication, overview, spend attribution,
budgets, programs, estimate, accuracy, connect, settings, security, and audit
surfaces. Server-rendered HTML; no native mobile app. Evaluated on current
Chromium/Firefox/Safari with keyboard-only navigation and screen-reader spot
checks; automated checks via axe-core.

---

## Table 1 — Success Criteria, Level A (WCAG 2.1)

| Criteria | Conformance | Remarks |
|---|---|---|
| 1.1.1 Non-text Content | Supports | Icons are decorative or have text equivalents; informative images carry `alt`/ARIA labels. |
| 1.2.1–1.2.3 Time-based Media | Not Applicable | No audio/video content. |
| 1.3.1 Info and Relationships | Supports | Semantic headings, lists, `<table>` with headers; form fields have associated labels (`aria-label`). |
| 1.3.2 Meaningful Sequence | Supports | DOM order matches visual reading order. |
| 1.3.3 Sensory Characteristics | Supports | Instructions don't rely on shape/position/color alone. |
| 1.4.1 Use of Color | Supports | Color is not the sole means of conveying status; text/badges accompany color (e.g. over/warn/ok tags carry words). |
| 1.4.2 Audio Control | Not Applicable | No auto-playing audio. |
| 2.1.1 Keyboard | Supports | All interactive controls reachable and operable by keyboard. |
| 2.1.2 No Keyboard Trap | Supports | No focus traps; modals/dialogs return focus. |
| 2.1.4 Character Key Shortcuts | Not Applicable | No single-character key shortcuts. |
| 2.2.1 Timing Adjustable | Supports | No time limits on tasks (sessions are generous and re-authable). |
| 2.2.2 Pause, Stop, Hide | Not Applicable | No moving/auto-updating content. |
| 2.3.1 Three Flashes | Supports | No flashing content. |
| 2.4.1 Bypass Blocks | Supports | Landmark regions / consistent nav allow bypass. |
| 2.4.2 Page Titled | Supports | Every page sets a descriptive `<title>`. |
| 2.4.3 Focus Order | Supports | Logical, predictable focus order. |
| 2.4.4 Link Purpose (In Context) | Supports | Link text is descriptive; ambiguous "→" links carry surrounding context/labels. |
| 2.5.1–2.5.4 Pointer / Motion | Supports | No path-based gestures or motion actuation. |
| 3.1.1 Language of Page | Supports | `<html lang="en">`. |
| 3.2.1 On Focus | Supports | Focus does not trigger context changes. |
| 3.2.2 On Input | Supports | Input does not auto-submit/redirect unexpectedly. |
| 3.3.1 Error Identification | Supports | Form errors are identified in text. |
| 3.3.2 Labels or Instructions | Supports | Inputs have labels/placeholders/instructions. |
| 4.1.1 Parsing | Supports | Valid, well-formed HTML. |
| 4.1.2 Name, Role, Value | Supports | Controls expose name/role/state to assistive tech. |

## Table 2 — Success Criteria, Level AA (WCAG 2.1)

| Criteria | Conformance | Remarks |
|---|---|---|
| 1.2.4 Captions (Live) | Not Applicable | No live media. |
| 1.2.5 Audio Description | Not Applicable | No video. |
| 1.3.4 Orientation | Supports | Responsive; works in portrait and landscape, no orientation lock. |
| 1.3.5 Identify Input Purpose | Supports | Autocomplete tokens on identifying fields (email, etc.). |
| 1.4.3 Contrast (Minimum) | Supports | Text/UI meets ≥ 4.5:1 (≥ 3:1 large); color tokens were hand-tuned for AA (muted/faint/amber/warn). |
| 1.4.4 Resize Text | Supports | Content reflows and remains usable at 200% zoom. |
| 1.4.5 Images of Text | Supports | Text is real text, not images. |
| 1.4.10 Reflow | Supports | No horizontal scroll at 320px; verified 0 horizontal overflow on mobile/tablet. |
| 1.4.11 Non-text Contrast | Supports | UI component and graphical-object contrast ≥ 3:1. |
| 1.4.12 Text Spacing | Supports | No loss of content with increased spacing. |
| 1.4.13 Content on Hover/Focus | Supports | Tooltips dismissible/persistent; no hover-only critical content. |
| 2.4.5 Multiple Ways | Supports | Nav + Explore hub + contextual links provide multiple paths to each surface. |
| 2.4.6 Headings and Labels | Supports | Descriptive headings and labels. |
| 2.4.7 Focus Visible | Supports | Visible focus indicator on all interactive elements. |
| 3.1.2 Language of Parts | Not Applicable | Single-language UI. |
| 3.2.3 Consistent Navigation | Supports | Nav is consistent across pages. |
| 3.2.4 Consistent Identification | Supports | Components with the same function are labeled consistently. |
| 3.3.3 Error Suggestion | Supports | Errors include correction guidance (e.g. "type: delete"). |
| 3.3.4 Error Prevention (Legal/Financial) | Supports | Destructive/financial actions require explicit confirmation (typed confirm + `confirm()` dialog). |
| 4.1.3 Status Messages | Supports | Post-action confirmations (settings saved, data erased, 2FA on/off, plan activated) carry `role=status` (implicit `aria-live=polite`) so they're announced without a focus change; async sync reports success via navigation and errors via an alert dialog. |

## Table 3 — Revised Section 508 / EN 301 549

- **Chapter 3 (Functional Performance Criteria):** Supports — usable without vision (screen-reader + keyboard), without perception of color, and without fine motor control.
- **Chapter 4 (Hardware):** Not Applicable — software-only SaaS.
- **Chapter 5 (Software):** Supports — see Tables 1–2.
- **Chapter 6 (Support Documentation & Services):** Supports — documentation is accessible HTML/Markdown; support via email.

## Maryland Nonvisual Access (NTIAA / COMAR 14.33.02)

The console is operable end-to-end **without vision**: every workflow (connect a
source, view spend, set a budget, export a report, manage the account) is
reachable by keyboard and announced by a screen reader, with no information
conveyed by color or shape alone. This satisfies the intent of Maryland's
Nonvisual Access standards for procured IT.

## Known gaps & remediation plan

1. **Independent audit** — commission a third-party VPAT validation before final
   Maryland submission; replace the "DRAFT / self-assessment" banner on sign-off.

*Resolved since first draft: 4.1.3 Status Messages — post-action confirmations
now use `role=status` and are announced to assistive tech.*

---

*VPAT® is a registered trademark of the Information Technology Industry Council
(ITI). This report follows the VPAT 2.5 template format.*
