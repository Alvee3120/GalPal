# Taste

- Prefers extending and reusing the existing architecture over building parallel or duplicate systems ("reuse the existing architecture", "do not create a duplicate discount or pricing system", "do not rewrite unrelated features"); new features should slot into existing models, services, and UI patterns/conventions (e.g. existing components, global styles). Confidence: 0.7
- Wants pricing/discount math to be authoritative on the backend: recompute and validate offers server-side at checkout/order creation and never trust discount amounts or totals sent by the frontend. Confidence: 0.6
