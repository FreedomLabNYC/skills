# Shopify Checkout Selectors

## New Checkout (2024+, most stores)

### Contact & Shipping Fields
```
Email:       get_by_label('Email').first
First name:  get_by_label('First name').first
Last name:   get_by_label('Last name').first
Address:     #shipping-address1  (or get_by_label('Address').first)
Apt/Suite:   get_by_label('Apartment, suite, etc.').first
City:        get_by_label('City').first
State:       get_by_label('State').first.select_option(label='New York')
ZIP:         get_by_label('ZIP code').first
```

**Critical:** Always append `.first` to `get_by_label()` — Shopify renders hidden autofill duplicate fields. Without `.first`, Playwright's strict mode throws because it finds 2+ matches.

**Address autocomplete:** After filling the address field, press `Escape` to dismiss the autocomplete dropdown before filling city/state/zip.

### Card Iframes (new checkout)

Card fields are inside iframes, but Shopify's iframes allow programmatic filling.

**Iframe selectors:**
```
Card number:  iframe[title="Field container for: Card number"]
Expiration:   iframe[title*="Expiration"]
Security:     iframe[title="Field container for: Security code"]
Name on card: iframe[title="Field container for: Name on card"]
```

**Inside each iframe:**
```python
frame = page.frame_locator('iframe[title="Field container for: Card number"]')
frame.get_by_role("textbox", name="Card number").fill("4111111111111111")
```

⚠️ Do NOT use generic `input` selector inside iframes — there are 8 inputs per iframe (honeypot/hidden fields). Use `get_by_role("textbox", name="...")` to target the correct one.

### Cart Management (AJAX API)
```python
# Clear cart
page.evaluate("fetch('/cart/clear.js', {method: 'POST'})")

# Add item
page.evaluate("""
    fetch('/cart/add.js', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({items: [{id: VARIANT_ID, quantity: 1}]})
    }).then(r => r.json())
""")

# Check cart
page.evaluate("fetch('/cart.js').then(r => r.json())")
```

### Product JSON API
```
GET /products/{handle}.json → full product data with all variants
GET /cart.js → current cart contents
```

### Actions
```
Pay button:    button containing text "pay now" (case-insensitive)
Continue:      button containing text "continue" (between steps)
Payment radio: #basic-creditCards (select credit card payment)
```

## Classic Checkout (pre-2024)

### Shipping Fields
```
#checkout_email
#checkout_shipping_address_first_name
#checkout_shipping_address_last_name
#checkout_shipping_address_address1
#checkout_shipping_address_address2
#checkout_shipping_address_city
#checkout_shipping_address_province (select)
#checkout_shipping_address_zip
#checkout_shipping_address_country (select)
#checkout_shipping_address_phone
```

### Card Iframes (classic)
```
iframe.card-fields-iframe  (indexed 0-3)
  [0] → #number        (card number)
  [1] → #name          (cardholder name)
  [2] → #expiry        (MM / YY)
  [3] → #verification_value  (CVV)
```

### Actions
```
Continue: #continue_button
```
