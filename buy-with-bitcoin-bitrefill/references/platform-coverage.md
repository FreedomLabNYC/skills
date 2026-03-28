# Platform Coverage & Capabilities

## Market Share (approximate, 2025-2026)

| Platform | Share | Module | Card Fillable? |
|----------|-------|--------|----------------|
| Shopify | ~30% | shopify_checkout.py | ✅ Yes (iframes allow it) |
| WooCommerce | ~20% | woocommerce_checkout.py | ⚠️ Depends on gateway |
| Stripe Hosted | ~10-15% | stripe_checkout.py | ✅ Yes (DOM elements) |
| Squarespace | ~5% | None | ❌ Uses Stripe Elements |
| BigCommerce | ~3% | None | Not tested |
| Custom/Other | ~30-35% | None | Varies |

**Total coverage with three modules: ~60-65% of e-commerce.**

## Shopify

**Detection:** `/cart.js` endpoint always responds. `window.Shopify` in browser JS. Server header contains "shopify".

**Strengths:**
- Standardized product JSON API (`/products/{handle}.json`)
- AJAX cart API (`/cart/add.js`, `/cart/clear.js`, `/cart.js`)
- Card iframes allow programmatic filling
- Both classic and new checkout styles have known selectors

**Limitations:**
- CAPTCHA on some stores (rare for normal checkout)
- Shop Pay prompt can intercept flow (dismiss or bypass)
- Some stores use custom checkout apps that change selectors

**Who uses it:** Most DTC brands, Allbirds, Gymshark, Momentous, Blockstream Store, thousands of small-medium stores.

## Stripe Hosted Checkout

**Detection:** URL contains `checkout.stripe.com` or `pay.stripe.com`.

**Strengths:**
- All fields are standard DOM `<input>` elements — simplest to automate
- No iframes for card fields
- Consistent selectors across all merchants

**Limitations:**
- Merchant must redirect to Stripe-hosted page (many embed instead)
- "Link" express checkout may intercept after email entry
- Some merchants require specific shipping info fields

**Who uses it:** SaaS (Cursor, Vercel), digital goods, Payment Links, some physical goods brands.

**⚠️ Stripe Elements (embedded) is different:** When merchants embed Stripe on their own domain, the card fields are in `.__PrivateStripeElement` iframes that BLOCK programmatic input. This is an intentional Stripe security measure. Only shipping/contact fields can be filled. Detect via `js.stripe.com` in page source.

## WooCommerce

**Detection:** `/wp-json/wc/store/v1/cart` endpoint. `woocommerce` class in body. `wp-content/plugins/woocommerce` in HTML.

**Strengths:**
- Field IDs hardcoded in WooCommerce core (never change)
- Consistent across all themes
- AJAX cart updates via `wc-ajax`

**Limitations:**
- Payment depends on gateway plugin:
  - **Braintree**: ✅ Card iframes fillable
  - **Stripe**: ⚠️ Blocked (same as Stripe Elements)
  - **PayPal**: Redirects to PayPal
  - **Square**: Untested
- Select2 dropdowns for country/state (handled by module)
- Some stores use checkout plugins that override default fields

**Who uses it:** WordPress-based stores, many small businesses, niche/independent retailers.

## Not Covered

**Shop Pay:** Requires phone number for account creation + SMS verification at every checkout. Single-use prepaid cards make saved payment useless (re-register every time).

**Amazon:** Custom platform, heavily bot-protected. Use Amazon gift cards directly.

**Demandware/Salesforce Commerce:** Adidas, Puma, Under Armour. Vendor-specific, not general-purpose enough.

**eBay, Walmart, Target:** Custom platforms with strong bot detection. Not practical for agent checkout.

## Approach Comparison

| Approach | Speed | Cost | Reliability |
|----------|-------|------|-------------|
| Hardcoded selectors (this skill) | 10-40s | $0 | High for known platforms |
| LLM-driven navigation (Browser Use, MultiOn) | 60-120s | $0.05-0.50/checkout | Medium (hallucination risk) |
| SneakerBot-style tools | 5-15s | $0 | High but vendor-specific |

Hardcoded selectors are the industry standard (sneaker bot community, 800+ stars on GitHub). LLM-driven navigation is slower, more expensive, and less reliable — but handles unknown platforms. The two approaches complement each other: hardcoded for known platforms, LLM fallback for edge cases.
