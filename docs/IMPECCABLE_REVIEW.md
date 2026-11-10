# MerchantOS — Impeccable design review

Date: 10 November 2026  
Scope: public landing page, interactive product preview, access section, sign-in surface, and signed-in workspace shell.

## Product intent

The public site must persuade a merchant to understand the operational value of MerchantOS, inspect a truthful product preview, and enter or create a workspace. The signed-in product must prioritize operational clarity over marketing decoration.

## Design direction retained

Editorial industrial: deep ink, restrained forest green, paper surfaces, and a signal-lime accent. Manrope is reserved for display hierarchy; DM Sans carries interface and reading text. The product preview is explicitly sample data. No invented customers, logos, testimonials, certifications, prices, uptime, integrations, or production claims.

## Review passes applied

### Critique and shape
- Kept the product interface as the hero's visual proof instead of generic stock imagery.
- Strengthened the hero's hierarchy and line length; tightened display tracking and balanced wrapping.
- Preserved the asymmetric editorial composition and removed the need for a logo strip or unsupported social proof.
- Replaced implied commercial tiers with honest pilot paths: demo exploration, PayPal Sandbox validation, and deployment-readiness review. Public pricing and general availability are explicitly not offered.

### Layout and typeset
- Standardized spacing and control-radius tokens.
- Improved hero and section heading rhythm, reading measure, and responsive stacking.
- Increased the legibility of dense labels and low-contrast light-surface copy.
- Retained deliberate negative space and avoided nested-card repetition.

### Interaction and harden
- Added a skip-to-content link and explicit navigation label.
- Added `aria-expanded` / `aria-controls` to the mobile navigation trigger.
- Added tablist, tab, tabpanel, selected-state, and live-status semantics to the workflow preview.
- Added visible keyboard focus treatment and reduced-motion handling.
- Added sticky-nav scroll offsets and horizontal-overflow resilience for dense code/table regions.
- Corrected access CTA wording so actions no longer imply a separate request-access process when they lead to the same account flow. The landing page now states the single-merchant pilot limitation.
- Corrected the sign-in helper text: credentials are not prefilled in the form.

### Polish
- Aligned the signed-in sidebar and controls with the public brand palette.
- Refined control geometry, hover feedback, borders, and surface depth.
- Kept motion short and purposeful; hover lift is disabled for reduced-motion users and touch layouts.

## Automated checks completed

- TypeScript/TSX syntax transpilation: PASS for App.tsx, Pages.tsx, main.tsx, and api.ts.
- CSS brace balance: PASS.
- Responsive breakpoints present: PASS (1100px, 760px, 420px).
- Reduced-motion rules present: PASS.
- Navigation and workflow accessibility hooks present: PASS.

## Not yet verified

- Full dependency-backed `tsc -b` and Vite production build: not run; dependency installation did not complete in this environment.
- Live browser visual inspection and interaction testing: pending.
- Screen-reader testing and formal WCAG audit: pending.
- Production readiness, provider integration behavior, and deployment configuration: outside this design pass.

## Shipping checklist

1. Run `npm install` in `frontend/` and commit the resulting lockfile.
2. Run `npm run typecheck` and `npm run build`.
3. Test the landing page at 1440px, 1024px, 768px, 390px, and 320px.
4. Keyboard-test navigation, workflow tabs, sign-in, and account creation.
5. Verify the sample-data disclaimer remains visible at all breakpoints.
6. Replace demo credentials/configuration and verify all production claims before launch.

## Follow-up workspace build — 10 November 2026

Scope: signed-in React workspace shell and root-cause intelligence route.

- Reorganized navigation into Workspace, Financial Operations, and Operations & Control groups.
- Added a responsive mobile navigation drawer with scrim, explicit close control, and route-close behavior.
- Added a keyboard-accessible quick navigator (`Ctrl/Cmd + K`, Escape to close) for the actual workspace routes.
- Added a real `/root-cause` route backed by the existing `/api/root-cause` endpoint; the page explicitly distinguishes correlation from causation and includes a meaningful empty state.
- Retained the established editorial-industrial visual system and existing operational page implementations.
- Tuned desktop, tablet, and narrow-mobile workspace layout, control sizing, semantic focus, and reduced-motion behavior.

Verification in this environment:
- TypeScript/TSX transpilation syntax checks: PASS for all frontend source entry files.
- CSS brace balance: PASS.
- Responsive breakpoints and reduced-motion rules: PASS.
- Full dependency-backed TypeScript/Vite build: NOT RUN successfully; `npm install` timed out and `npm run build` confirms dependencies such as React, React Router, and Lucide are not installed in this environment.
- Browser screenshots, live interaction testing, and screen-reader testing: pending in a dependency-enabled browser environment.
