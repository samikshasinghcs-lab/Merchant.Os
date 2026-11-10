# MerchantOS v6.5 — Executive Product Finish

## Intent

This pass raises product coherence and operational polish without pretending the product was built by a larger team or claiming capabilities that have not been verified. The design target is a mature financial-operations console: restrained, information-dense, deliberate, and accountable.

## Changes

- Route-aware workspace header: the top bar now identifies the active workspace section and page instead of repeating a generic title on every route.
- Corrected the root-cause intelligence navigation target to `/root-cause`.
- Tightened navigation hierarchy, workspace identity truncation, table behavior, metric typography, empty/error states, and command palette interaction styling.
- Preserved the editorial-industrial visual system: ink, mineral paper, forest green, and restrained signal-lime.
- Preserved explicit pilot and sample-data language. No fake customer logos, testimonials, uptime claims, team-size claims, certifications, or live integration claims were introduced.

## Quality boundary

This is a frontend presentation and navigation-coherence pass. It does not change payment execution, authorization, tenant isolation, or persistence behavior.

The frontend dependencies were not installed in the build environment during this pass. Therefore the Vite production build, browser screenshot review, responsive device QA, and interactive route verification remain pending. Do not represent this pass as production certification.
