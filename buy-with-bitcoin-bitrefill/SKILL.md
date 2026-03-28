---
name: agent-checkout
description: Automate e-commerce checkout via Playwright browser automation and Shopify Storefront API. Supports Shopify (~30% of e-commerce), Stripe Hosted Checkout (~15%), and WooCommerce (~20%). Use when buying products online, completing checkout forms, detecting e-commerce platforms, getting real checkout totals (with shipping/tax), or testing discount codes. Covers platform detection, Shopify cart creation via API (no browser needed), discount code validation, and multi-platform form filling. Requires Python 3.8+ and Playwright. Not for payment processing or wallet management — this skill handles the checkout step only.
---

# Agent Checkout

Automate e-commerce purchases using hardcoded selectors for the three platforms that cover ~65% of online stores. For Shopify stores, the Storefront API enables cart creation, exact pricing, and discount code testing with zero browser interaction.

## Prerequisites

Install before first use:

```bash
# Python packages
pip install playwright

# Browser (Chromium — or use an existing Chromium-based browser like Brave/Chrome)
playwright install chromium

# Verify
python3 -c "from playwright.sync_api import sync_playwright; print('Playwright ready')"
```

**Browser configuration:** Scripts default to Brave Browser on macOS. To use a different browser, set the `BROWSER_PATH` environment variable:

```bash
export BROWSER_PATH="/usr/bin/chromium-browser"           # Linux
export BROWSER_PATH="/usr/bin/google-chrome-stable"       # Chrome on Linux
export BROWSER_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"  # Chrome on macOS
```

Or edit the `BRAVE_PATH` constant in each script. Headed mode (`headless=False`) is recommended — headless mode hangs with some browsers.

## Architecture

```
URL → detect_platform.py → identify platform + product data + storefront token
    → shopify_cart_create() → exact total, shipping options, discount validation (API, ~1s)
    → [platform]_checkout.py → fill form + submit order (browser, ~15s)
```

The agent orchestrates the modules — no monolithic pipeline. This allows handling edge cases (unexpected shipping, free shipping thresholds, wrong variants) with judgment.

## Platform Detection

Run `detect_platform.py` first. Identifies the platform via lightweight HTTP probes (no browser needed):

```bash
python3 scripts/detect_platform.py https://store.example.com/products/widget
```

Returns: `platform`, `confidence`, `checkout_module`, `product` (with variants), `store_domain`, `storefront_token` (Shopify).

**Detection methods by platform:**
- **Shopify**: Probes `/cart.js` + `/products/{handle}.json`, extracts storefront token from homepage
- **WooCommerce**: Probes `/wp-json/wc/store/v1/cart` + HTML class detection
- **Stripe Hosted**: URL pattern matching (`checkout.stripe.com`)
- **Fallback**: HTML analysis for BigCommerce, Squarespace, embedded Stripe Elements

## Shopify Storefront API (the big advantage)

For Shopify stores (~30% of e-commerce), the Storefront API eliminates the need for a browser to get pricing:

```bash
# Get exact total with shipping, test discount codes — all via HTTP
python3 scripts/detect_platform.py URL --cart --variant 41325780664503 --discount HUBERMAN20
```

### What the API provides (no browser needed)

- **Exact checkout total** including shipping — subtotal, shipping cost, tax, total
- **All shipping options** with costs (e.g., Standard $8, 2-Day $16.99)
- **Discount code validation** — test codes instantly, see if they apply + savings amount
- **Pre-built checkout URL** — opens in browser with address already pre-filled
- **Cart management** — add/remove items, update quantities

### How storefront tokens work

Storefront API tokens are **public by design** — they're embedded in every Shopify store's JavaScript. They grant:
- ✅ Read access to products, collections, cart
- ✅ Cart creation with shipping address, discount codes
- ✅ Shipping rate calculation
- ❌ Payment submission (requires private token)

The `detect_platform.py` script extracts the token automatically from the store's homepage.

### Key functions

```python
from detect_platform import shopify_cart_create, shopify_test_discount_codes

# Create cart with exact pricing
cart = shopify_cart_create(
    store_url='https://www.livemomentous.com',
    storefront_token='8a6e727e18e71aa26257d8d2410f3cd3',
    variant_id=41325780664503,
    shipping_address={'firstName': 'John', 'lastName': 'Doe',
                      'address1': '123 Main St', 'city': 'New York',
                      'province': 'New York', 'zip': '10001', 'country': 'US'},
    discount_codes=['SAVE20']
)
# Returns: checkout_url, subtotal, shipping, total, shipping_options, discount status

# Test multiple discount codes at once
results = shopify_test_discount_codes(
    store_url, token, variant_id,
    codes=['HUBERMAN', 'SAVE10', 'WELCOME', 'PODCAST']
)
# Returns sorted list: [{code, applicable, total, savings}, ...]
```

### Card tokenization

Shopify's card vault at `deposit.shopifycs.com` accepts card details and returns a session ID:

```python
from detect_platform import shopify_tokenize_card
session_id = shopify_tokenize_card('4111...', 'John Doe', 12, 2030, '123')
# Returns: "east-47e563920924c8234ddf7a942e5a3411"
```

Note: Completing payment via API (`cartPaymentUpdate`) requires a private app token, not the public storefront token. The browser checkout step is still needed for payment.

## Checkout Modules

### Shopify (`shopify_checkout.py`)

Supports both classic (pre-2024) and new (2024+) Shopify checkout.

**Key patterns:**
- Add to cart via AJAX: `POST /cart/add.js` with variant ID
- Clear cart first: `POST /cart/clear.js` (prevents stale items)
- Duplicate fields: always use `.first` on `get_by_label()` calls (hidden autofill fields)
- Address autocomplete: dismiss with `Escape` key after filling
- Card fields are in iframes — but Shopify's iframes ARE fillable ✅

**Optimized flow with Storefront API:**
1. `shopify_cart_create()` → get `checkout_url` with address pre-filled
2. Open `checkout_url` in browser → shipping already selected
3. Only need to fill: card details + click Pay
4. Saves ~20-30s vs navigating product page → add to cart → fill address

See `references/shopify-selectors.md` for complete selector reference.

### Stripe Hosted (`stripe_checkout.py`)

The easiest to automate — all fields are standard DOM elements, no iframes.

**Selectors:**
```
#email, #cardNumber, #cardExpiry, #cardCvc, #billingName
#billingCountry (select), #billingPostalCode
button.SubmitButton
```

⚠️ **Stripe Elements (embedded)** is different from Stripe Hosted. Stripe Elements blocks programmatic card entry. If a site embeds Stripe on their own domain (not redirecting to checkout.stripe.com), card fields cannot be filled.

### WooCommerce (`woocommerce_checkout.py`)

Field IDs are hardcoded in WooCommerce core — consistent across all stores.

**Selectors:** `#billing_first_name` through `#billing_email`, `#place_order`

**Payment gateways:**
- **Braintree**: Card iframes ARE fillable ✅
- **Stripe Elements**: Card iframes BLOCKED ⚠️
- **PayPal**: Redirects to PayPal (out of scope)

## Browser Setup

All checkout modules use Playwright with a Chromium-based browser in headed mode.

**Critical settings:**
- `headless=False` — always (headless hangs with some browsers)
- `--disable-blink-features=AutomationControlled` — bypass bot detection
- `ignore_default_args=['--enable-automation']` — remove automation indicators
- Fresh browser context per purchase — prevents cart contamination (the #1 failure mode)

## Approval Gates

Build two pause points into the purchase flow:

1. **Before payment**: Show item, shipping, tax, total → get approval
2. **Before checkout submission**: Screenshot the filled form → get approval

## Error Handling

- Screenshots saved to a `purchases/` directory on every step
- Each module returns a result dict: `{success, total, error, screenshots, elapsed}`
- Cart contamination: always clear cart or use fresh browser context
- Stripe Elements blocking: detect early, report to user, suggest alternative

## Limitations

- **Stripe Elements (embedded)**: Cannot fill card fields — Stripe blocks this intentionally
- **Shop Pay**: Requires phone number + saved card — impractical with single-use cards
- **CAPTCHA**: Detected but not solved
- **Custom platforms (~35%)**: Not covered
- **Shopify API payment**: `cartPaymentUpdate` needs private token — browser still needed for card entry

## Discount Code Finder

`coupon_finder.py` searches multiple sources for discount codes, then validates them via the Shopify Storefront API:

```bash
python3 scripts/coupon_finder.py "https://www.livemomentous.com" "Momentous" \
    --variant 41325780664503 --token 8a6e727e18e71aa26257d8d2410f3cd3
```

**Sources searched:**
1. Google (`"[store] coupon code [year]"`, `"[store] promo code"`)
2. Store homepage (banner codes, popup codes, data attributes)
3. Influencer/podcast codes (`"[brand] podcast code"`, `"[brand] sponsor code"`)
4. Coupon aggregator sites via Playwright (RetailMeNot, CouponFollow, Coupons.com)

**Validation:** For Shopify stores, each code is tested via the Storefront API (~0.5s per code). The API returns whether the code is applicable and the adjusted total, so savings are calculated precisely.

**Output:** Sorted list of codes by savings (highest first). Working codes shown with savings amount.

Use `--no-browser` to skip Playwright-based aggregator scraping (faster, still gets Google + homepage + influencer codes).

## File Reference

| File | Purpose |
|------|---------|
| `scripts/detect_platform.py` | Platform detection + Storefront API + price/discount checking |
| `scripts/coupon_finder.py` | Multi-source coupon code discovery + API validation |
| `scripts/shopify_checkout.py` | Shopify checkout (classic + new) |
| `scripts/stripe_checkout.py` | Stripe Hosted Checkout |
| `scripts/woocommerce_checkout.py` | WooCommerce checkout |
| `references/shopify-selectors.md` | Complete Shopify selector reference |
| `references/platform-coverage.md` | Platform market share, capabilities, known limitations |
