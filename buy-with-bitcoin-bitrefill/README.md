# Buy With Bitcoin (Bitrefill)

Spend Bitcoin at any online store. Your AI agent handles the entire flow: Lightning payment → Bitrefill Visa → automated checkout across 65% of e-commerce.

**The pipeline:** `URL → detect platform → find coupons → get exact total → approval → buy Visa via Lightning → fill checkout → confirm`

See [freedomlab.nyc/resources/buy-with-bitcoin](https://freedomlab.nyc/resources/buy-with-bitcoin/) for full details.

## What's Included

- `SKILL.md` — Full skill instructions for AI agents
- `scripts/detect_platform.py` — Platform detection + Shopify Storefront API
- `scripts/coupon_finder.py` — 7-source coupon discovery + API validation
- `scripts/shopify_checkout.py` — Shopify checkout automation
- `scripts/stripe_checkout.py` — Stripe Hosted Checkout automation
- `scripts/woocommerce_checkout.py` — WooCommerce checkout automation
- `references/shopify-selectors.md` — Complete Shopify selector reference
- `references/platform-coverage.md` — Platform market share and capabilities

## Prerequisites

- Python 3.8+ with Playwright (`pip install playwright && playwright install chromium`)
- A Lightning wallet (we use [phoenixd](https://phoenix.acinq.co/server))
- A [Bitrefill](https://www.bitrefill.com) account (no KYC required)
- A Chromium-based browser (Brave recommended)

## Platform Coverage

| Platform | Market Share | Status |
|----------|-------------|--------|
| Shopify | ~30% | ✅ Full support |
| Stripe Hosted | ~15% | ✅ Full support |
| WooCommerce + Braintree | ~20% | ✅ Full support |
| WooCommerce + Stripe | ~20% | ⚠️ Partial (Stripe blocks card iframes) |
