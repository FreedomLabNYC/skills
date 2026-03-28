#!/usr/bin/env python3
"""
E-Commerce Platform Detector + Shopify Storefront API

Detects whether a website uses Shopify, WooCommerce, Stripe, or other platforms.
For Shopify stores, uses the Storefront API for:
  - Exact checkout totals with shipping/tax (no browser needed)
  - Shipping method selection
  - Discount code validation
  - Pre-built checkout URLs with address pre-filled

Usage:
    from detect_platform import detect_platform, shopify_cart_create
    
    result = detect_platform('https://www.livemomentous.com/products/tongkat')
    # Returns: platform, product data, storefront token, etc.
    
    cart = shopify_cart_create(
        store_url='https://www.livemomentous.com',
        storefront_token='8a6e727e18e71aa26257d8d2410f3cd3',
        variant_id=41325780664503,
        shipping_address={...},
        discount_codes=['HUBERMAN20']
    )
    # Returns: checkoutUrl, exact total, shipping options, discount status

CLI:
    python3 detect_platform.py https://www.livemomentous.com/products/tongkat
    python3 detect_platform.py URL --cart --variant 41325780664503
    python3 detect_platform.py URL --cart --variant ID --discount HUBERMAN20
"""

import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import urllib.parse


BRAVE_PATH = os.environ.get(
    'BROWSER_PATH',
    '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser'
)
BRAVE_ARGS = [
    '--no-first-run', '--no-default-browser-check', '--disable-extensions',
    '--disable-component-extensions-with-background-pages', '--disable-brave-update',
    '--disable-brave-extension', '--disable-component-update',
    '--disable-blink-features=AutomationControlled'
]

DEFAULT_SHIPPING = {
    'firstName': 'Harrison', 'lastName': 'Friedes',
    'company': 'Fat Cat Fab Lab',
    'address1': '224 West 4th Street',
    'city': 'New York', 'province': 'New York',
    'zip': '10014', 'country': 'US'
}


# ============================================================
# Platform Detection
# ============================================================

def detect_platform(url, use_browser=False):
    """
    Detect e-commerce platform for a given URL.
    
    Tries lightweight HTTP checks first (no browser needed).
    Falls back to browser detection if needed.
    
    Returns dict:
        platform: 'shopify' | 'woocommerce' | 'stripe_hosted' | 'bigcommerce' | 
                  'squarespace' | 'custom' | 'unknown'
        confidence: 'high' | 'medium' | 'low'
        store_domain: base URL
        product: product metadata if available
        checkout_module: which checkout module to use
        storefront_token: Shopify Storefront API token (if Shopify)
        details: platform-specific details
    """
    parsed = urllib.parse.urlparse(url)
    base_url = f'{parsed.scheme}://{parsed.netloc}'
    
    result = {
        'url': url,
        'store_domain': base_url,
        'platform': 'unknown',
        'confidence': 'low',
        'checkout_module': None,
        'product': None,
        'storefront_token': None,
        'details': {}
    }
    
    # ---- Check 1: Stripe hosted checkout (URL pattern) ----
    if 'checkout.stripe.com' in url or 'pay.stripe.com' in url or 'buy.stripe.com' in url:
        result['platform'] = 'stripe_hosted'
        result['confidence'] = 'high'
        result['checkout_module'] = 'stripe_checkout.py'
        return result
    
    # ---- Check 2: Shopify (API probe — no browser needed) ----
    shopify = _check_shopify(base_url, url)
    if shopify:
        result.update(shopify)
        return result
    
    # ---- Check 3: WooCommerce (API probe) ----
    woo = _check_woocommerce(base_url, url)
    if woo:
        result.update(woo)
        return result
    
    # ---- Check 4: BigCommerce ----
    bc = _check_bigcommerce(base_url)
    if bc:
        result.update(bc)
        return result
    
    # ---- Check 5: Browser-based detection (fallback) ----
    if use_browser:
        browser_result = _check_browser(url, base_url)
        if browser_result:
            result.update(browser_result)
            return result
    
    # ---- Check 6: HTTP header / HTML hints ----
    html_result = _check_html(url)
    if html_result:
        result.update(html_result)
        return result
    
    return result


def _check_shopify(base_url, product_url):
    """Check if site is Shopify by probing standard endpoints."""
    
    # Shopify always responds to /cart.js
    try:
        req = urllib.request.Request(
            f'{base_url}/cart.js',
            headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
        )
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read())
        
        if 'token' in data or 'items' in data:
            result = {
                'platform': 'shopify',
                'confidence': 'high',
                'checkout_module': 'shopify_checkout.py',
                'details': {
                    'cart_token': data.get('token', ''),
                    'cart_items': data.get('item_count', 0),
                    'currency': data.get('currency', 'USD'),
                }
            }
            
            # Try to get product info
            product = _get_shopify_product(base_url, product_url)
            if product:
                result['product'] = product
            
            # Extract Storefront API token from homepage
            token = _get_storefront_token(base_url)
            if token:
                result['storefront_token'] = token
                result['details']['storefront_api'] = True
            
            return result
    except:
        pass
    
    # Secondary: check meta tags
    try:
        req = urllib.request.Request(base_url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=5)
        html = resp.read().decode('utf-8', errors='ignore')[:20000]
        
        if 'cdn.shopify.com' in html or 'Shopify.theme' in html or 'myshopify.com' in html:
            token = _extract_storefront_token(html)
            return {
                'platform': 'shopify',
                'confidence': 'high',
                'checkout_module': 'shopify_checkout.py',
                'storefront_token': token,
                'details': {
                    'detected_via': 'html_hints',
                    'storefront_api': token is not None
                }
            }
    except:
        pass
    
    return None


def _get_storefront_token(base_url):
    """Extract Storefront API token from store's homepage.
    
    Storefront tokens are PUBLIC and designed to be embedded in client-side JS.
    They grant read access to products/cart and write access to cart operations.
    """
    try:
        req = urllib.request.Request(base_url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=5)
        html = resp.read().decode('utf-8', errors='ignore')[:50000]
        return _extract_storefront_token(html)
    except:
        return None


def _extract_storefront_token(html):
    """Extract storefront token from HTML source."""
    patterns = [
        r'storefrontAccessToken["\'\s:]+([a-f0-9]{32})',
        r'Storefront-Access-Token["\'\s:]+([a-f0-9]{32})',
        r'accessToken["\'\s:]+([a-f0-9]{32})',
        r'"storefront_digest":"([a-f0-9]{32})"',
    ]
    for p in patterns:
        m = re.search(p, html, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def _get_shopify_product(base_url, product_url):
    """Get product details from Shopify's JSON API."""
    match = re.search(r'/products/([^/?#]+)', product_url)
    if not match:
        return None
    
    handle = match.group(1)
    
    try:
        req = urllib.request.Request(
            f'{base_url}/products/{handle}.json',
            headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
        )
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read())
        product = data.get('product', {})
        
        variants = []
        for v in product.get('variants', []):
            variants.append({
                'id': v['id'],
                'title': v.get('title', ''),
                'price': v.get('price', ''),
                'available': v.get('available', True),
                'sku': v.get('sku', ''),
            })
        
        return {
            'id': product.get('id'),
            'title': product.get('title', ''),
            'handle': handle,
            'vendor': product.get('vendor', ''),
            'product_type': product.get('product_type', ''),
            'variants': variants,
            'images': [img.get('src', '') for img in product.get('images', [])[:3]],
        }
    except:
        pass
    
    return None


def _check_woocommerce(base_url, product_url):
    """Check if site is WooCommerce."""
    try:
        req = urllib.request.Request(
            f'{base_url}/wp-json/wc/store/v1/cart',
            headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}
        )
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read())
        
        return {
            'platform': 'woocommerce',
            'confidence': 'high',
            'checkout_module': 'woocommerce_checkout.py',
            'details': {
                'cart_items': len(data.get('items', [])),
                'currency': data.get('totals', {}).get('currency_code', 'USD'),
                'detected_via': 'store_api'
            }
        }
    except:
        pass
    
    try:
        req = urllib.request.Request(base_url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=5)
        html = resp.read().decode('utf-8', errors='ignore')[:15000]
        
        woo_signals = [
            'woocommerce' in html.lower(),
            'wp-content/plugins/woocommerce' in html,
            'wc-ajax' in html,
            'add_to_cart' in html and 'wp-' in html,
        ]
        
        if sum(woo_signals) >= 2:
            gateway = 'unknown'
            if 'stripe' in html.lower():
                gateway = 'stripe'
            elif 'braintree' in html.lower():
                gateway = 'braintree'
            elif 'paypal' in html.lower():
                gateway = 'paypal'
            
            return {
                'platform': 'woocommerce',
                'confidence': 'medium',
                'checkout_module': 'woocommerce_checkout.py',
                'details': {
                    'detected_via': 'html_hints',
                    'payment_gateway': gateway,
                    'signals': sum(woo_signals)
                }
            }
    except:
        pass
    
    return None


def _check_bigcommerce(base_url):
    """Check if site is BigCommerce."""
    try:
        req = urllib.request.Request(base_url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=5)
        html = resp.read().decode('utf-8', errors='ignore')[:10000]
        
        if 'bigcommerce.com' in html or 'BigCommerce' in html or 'stencil' in html.lower():
            return {
                'platform': 'bigcommerce',
                'confidence': 'medium',
                'checkout_module': None,
                'details': {'detected_via': 'html_hints'}
            }
    except:
        pass
    return None


def _check_html(url):
    """Generic HTML-based platform detection."""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=5)
        html = resp.read().decode('utf-8', errors='ignore')[:15000]
        headers = dict(resp.headers)
        
        if 'squarespace.com' in html or 'static.squarespace.com' in html:
            return {
                'platform': 'squarespace',
                'confidence': 'high',
                'checkout_module': None,
                'details': {'note': 'Squarespace uses Stripe under the hood'}
            }
        
        server = headers.get('server', '').lower()
        if 'shopify' in server:
            return {
                'platform': 'shopify',
                'confidence': 'high',
                'checkout_module': 'shopify_checkout.py',
                'details': {'detected_via': 'server_header'}
            }
        
        if 'wp-content' in html and 'woocommerce' not in html.lower():
            return {
                'platform': 'wordpress',
                'confidence': 'medium',
                'checkout_module': None,
                'details': {'note': 'WordPress without WooCommerce'}
            }
        
        if 'js.stripe.com' in html:
            return {
                'platform': 'stripe_elements',
                'confidence': 'medium',
                'checkout_module': 'stripe_checkout.py',
                'details': {
                    'note': 'Stripe Elements embedded — card iframes may be blocked',
                    'detected_via': 'stripe_js'
                }
            }
    except:
        pass
    
    return None


def _check_browser(url, base_url):
    """Browser-based detection for JS-rendered sites."""
    from playwright.sync_api import sync_playwright
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=BRAVE_PATH, headless=False,
            args=BRAVE_ARGS, ignore_default_args=['--enable-automation']
        )
        ctx = browser.new_context()
        page = ctx.new_page()
        
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=15000)
            page.wait_for_timeout(3000)
            
            platform = page.evaluate("""() => {
                if (window.Shopify || window.ShopifyAnalytics) return 'shopify';
                if (document.body.classList.contains('woocommerce') || 
                    document.querySelector('.woocommerce')) return 'woocommerce';
                if (window.BCData || window.stencilUtils) return 'bigcommerce';
                if (window.Squarespace) return 'squarespace';
                if (document.querySelector('[data-stripe]') || 
                    document.querySelector('iframe[src*="stripe"]')) return 'stripe_elements';
                return null;
            }""")
            
            if platform:
                modules = {
                    'shopify': 'shopify_checkout.py',
                    'woocommerce': 'woocommerce_checkout.py',
                    'stripe_elements': 'stripe_checkout.py',
                }
                return {
                    'platform': platform,
                    'confidence': 'high',
                    'checkout_module': modules.get(platform),
                    'details': {'detected_via': 'browser_js'}
                }
        finally:
            browser.close()
    
    return None


# ============================================================
# Shopify Storefront API
# ============================================================

def shopify_cart_create(store_url, storefront_token, variant_id, quantity=1,
                        shipping_address=None, email=None, discount_codes=None):
    """
    Create a Shopify cart via the Storefront GraphQL API.
    
    Returns exact checkout total (with shipping), all shipping options,
    discount code status, and a pre-built checkout URL with address pre-filled.
    
    NO BROWSER NEEDED — pure HTTP.
    
    Args:
        store_url: base URL (e.g., 'https://www.livemomentous.com')
        storefront_token: public Storefront API access token (32-char hex)
        variant_id: Shopify variant ID (integer)
        quantity: number of items
        shipping_address: dict with firstName, lastName, address1, city, province, zip, country
        email: buyer email
        discount_codes: list of discount codes to try
        
    Returns dict:
        checkout_url: URL to open in browser (address pre-filled)
        cart_id: Shopify cart ID (for subsequent mutations)
        subtotal: product price
        shipping: shipping cost
        total: subtotal + shipping
        shipping_options: list of {title, cost} dicts
        selected_shipping: currently selected shipping method
        discount_codes: list of {code, applicable} dicts
        tax: tax amount (if calculated)
    """
    store_url = store_url.rstrip('/')
    shipping = shipping_address or DEFAULT_SHIPPING
    email = email or 'wrencole.nyc@gmail.com'
    discount_codes = discount_codes or []
    
    # Build address block
    addr_fields = []
    for key in ['firstName', 'lastName', 'company', 'address1', 'address2', 
                'city', 'province', 'zip', 'country']:
        val = shipping.get(key, '')
        if val:
            addr_fields.append(f'{key}: "{val}"')
    addr_str = ', '.join(addr_fields)
    
    # Build discount codes
    discount_str = ''
    if discount_codes:
        codes_json = json.dumps(discount_codes)
        discount_str = f', discountCodes: {codes_json}'
    
    query = f"""mutation {{
        cartCreate(input: {{
            lines: [{{ merchandiseId: "gid://shopify/ProductVariant/{variant_id}", quantity: {quantity} }}]
            {discount_str}
            buyerIdentity: {{
                email: "{email}"
                countryCode: US
                deliveryAddressPreferences: [{{
                    deliveryAddress: {{ {addr_str} }}
                }}]
            }}
        }}) {{
            cart {{
                id
                checkoutUrl
                cost {{
                    totalAmount {{ amount currencyCode }}
                    subtotalAmount {{ amount }}
                    totalTaxAmount {{ amount }}
                }}
                discountCodes {{ code applicable }}
                discountAllocations {{ discountedAmount {{ amount }} }}
                deliveryGroups(first: 5) {{
                    edges {{
                        node {{
                            deliveryOptions {{
                                title
                                estimatedCost {{ amount }}
                            }}
                            selectedDeliveryOption {{
                                title
                                estimatedCost {{ amount }}
                            }}
                        }}
                    }}
                }}
            }}
            userErrors {{ field message }}
        }}
    }}"""
    
    data = _storefront_query(store_url, storefront_token, query)
    
    if not data:
        return {'error': 'Storefront API request failed'}
    
    errors = data.get('errors', [])
    if errors:
        return {'error': errors[0].get('message', str(errors))}
    
    cart_data = data.get('data', {}).get('cartCreate', {})
    user_errors = cart_data.get('userErrors', [])
    if user_errors:
        return {'error': user_errors[0].get('message', str(user_errors))}
    
    cart = cart_data.get('cart', {})
    if not cart:
        return {'error': 'No cart returned'}
    
    cost = cart.get('cost', {})
    
    # Parse shipping options
    shipping_options = []
    selected_shipping = None
    delivery_groups = cart.get('deliveryGroups', {}).get('edges', [])
    for group in delivery_groups:
        node = group.get('node', {})
        for opt in node.get('deliveryOptions', []):
            shipping_options.append({
                'title': opt.get('title', ''),
                'cost': float(opt.get('estimatedCost', {}).get('amount', 0))
            })
        sel = node.get('selectedDeliveryOption')
        if sel:
            selected_shipping = {
                'title': sel.get('title', ''),
                'cost': float(sel.get('estimatedCost', {}).get('amount', 0))
            }
    
    # Parse discount status
    discount_status = []
    for dc in cart.get('discountCodes', []):
        discount_status.append({
            'code': dc.get('code', ''),
            'applicable': dc.get('applicable', False)
        })
    
    discount_savings = 0
    for alloc in cart.get('discountAllocations', []):
        discount_savings += float(alloc.get('discountedAmount', {}).get('amount', 0))
    
    subtotal = float(cost.get('subtotalAmount', {}).get('amount', 0))
    total = float(cost.get('totalAmount', {}).get('amount', 0))
    tax_data = cost.get('totalTaxAmount')
    tax = float(tax_data.get('amount', 0)) if tax_data else None
    shipping_cost = selected_shipping['cost'] if selected_shipping else None
    
    return {
        'checkout_url': cart.get('checkoutUrl', ''),
        'cart_id': cart.get('id', ''),
        'subtotal': subtotal,
        'shipping': shipping_cost,
        'tax': tax,
        'total': total,
        'currency': cost.get('totalAmount', {}).get('currencyCode', 'USD'),
        'shipping_options': shipping_options,
        'selected_shipping': selected_shipping,
        'discount_codes': discount_status,
        'discount_savings': discount_savings,
    }


def shopify_test_discount_codes(store_url, storefront_token, variant_id,
                                  codes, shipping_address=None):
    """
    Test multiple discount codes against a Shopify store via API.
    
    Tests each code individually and returns which ones work + savings amount.
    ~0.5-1s per code, pure HTTP.
    
    Args:
        store_url: base URL
        storefront_token: Storefront API token
        variant_id: product variant ID
        codes: list of discount code strings to test
        shipping_address: optional shipping address dict
        
    Returns:
        list of {code, applicable, total, savings} sorted by savings (highest first)
    """
    results = []
    
    # First, get baseline price without any code
    baseline = shopify_cart_create(
        store_url, storefront_token, variant_id,
        shipping_address=shipping_address
    )
    if 'error' in baseline:
        return [{'error': baseline['error']}]
    
    baseline_total = baseline['total']
    
    for code in codes:
        cart = shopify_cart_create(
            store_url, storefront_token, variant_id,
            shipping_address=shipping_address,
            discount_codes=[code]
        )
        
        if 'error' in cart:
            results.append({
                'code': code, 'applicable': False,
                'total': baseline_total, 'savings': 0,
                'error': cart['error']
            })
            continue
        
        dc_status = cart.get('discount_codes', [{}])
        applicable = dc_status[0].get('applicable', False) if dc_status else False
        
        results.append({
            'code': code,
            'applicable': applicable,
            'total': cart['total'],
            'savings': round(baseline_total - cart['total'], 2) if applicable else 0,
        })
    
    # Sort by savings (highest first), then applicable codes first
    results.sort(key=lambda r: (-r['savings'], not r['applicable']))
    
    return results


def shopify_tokenize_card(card_number, card_name, exp_month, exp_year, cvv):
    """
    Tokenize a credit card via Shopify's card vault (deposit.shopifycs.com).
    
    Returns a session ID that can be used with cartPaymentUpdate.
    Note: cartPaymentUpdate requires a PRIVATE storefront token (not public).
    The session ID is still useful as it works with the browser checkout
    flow to pre-fill card details.
    
    Args:
        card_number: card number string
        card_name: cardholder name
        exp_month: expiration month (int)
        exp_year: expiration year (int, 2-digit or 4-digit)
        cvv: security code
        
    Returns:
        session ID string or None
    """
    payload = json.dumps({
        'credit_card': {
            'number': card_number,
            'name': card_name,
            'month': int(exp_month),
            'year': int(exp_year),
            'verification_value': cvv
        }
    }).encode()
    
    try:
        req = urllib.request.Request(
            'https://deposit.shopifycs.com/sessions',
            data=payload,
            headers={'Content-Type': 'application/json'}
        )
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        return data.get('id')
    except Exception as e:
        print(f'Card tokenization failed: {e}')
        return None


def _storefront_query(store_url, token, query):
    """Execute a Shopify Storefront API GraphQL query."""
    payload = json.dumps({'query': query}).encode()
    
    try:
        req = urllib.request.Request(
            f'{store_url}/api/2025-01/graphql.json',
            data=payload,
            headers={
                'Content-Type': 'application/json',
                'X-Shopify-Storefront-Access-Token': token
            }
        )
        resp = urllib.request.urlopen(req, timeout=10)
        return json.loads(resp.read())
    except Exception as e:
        print(f'Storefront API error: {e}')
        return None


# ============================================================
# Legacy Browser-Based Price Check (for non-Shopify stores)
# ============================================================

def get_checkout_total(store_url, variant_id=None, product_url=None,
                       platform='shopify', shipping_address=None,
                       storefront_token=None):
    """
    Get the real checkout total with shipping and tax.
    
    For Shopify stores with a storefront token: uses the Storefront API
    (no browser needed, ~1s).
    
    For other stores: opens a browser, navigates to checkout, fills address,
    and reads the calculated total (~30s).
    """
    # Fast path: Shopify Storefront API
    if platform == 'shopify' and storefront_token and variant_id:
        shipping = shipping_address or DEFAULT_SHIPPING
        return shopify_cart_create(
            store_url, storefront_token, variant_id,
            shipping_address=shipping
        )
    
    # Slow path: browser-based
    from playwright.sync_api import sync_playwright
    
    subprocess.run(['pkill', '-9', '-f', 'Brave'], capture_output=True)
    time.sleep(1)
    
    shipping = shipping_address or {
        'first_name': 'Harrison', 'last_name': 'Friedes',
        'company': 'Fat Cat Fab Lab',
        'address1': '224 West 4th Street',
        'city': 'New York', 'state': 'New York', 'zip': '10014'
    }
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=BRAVE_PATH, headless=False,
            args=BRAVE_ARGS, ignore_default_args=['--enable-automation']
        )
        ctx = browser.new_context()
        page = ctx.new_page()
        page.set_default_timeout(15000)
        
        try:
            if platform == 'shopify':
                return _shopify_price_check(page, store_url, variant_id, shipping)
            elif platform == 'woocommerce':
                return _woo_price_check(page, store_url, product_url, shipping)
            else:
                return {'error': f'Price check not implemented for {platform}'}
        except Exception as e:
            return {'error': str(e)}
        finally:
            browser.close()


def _shopify_price_check(page, store_url, variant_id, shipping):
    """Browser-based Shopify price check (fallback if no storefront token)."""
    page.goto(f'{store_url}/products', wait_until='domcontentloaded', timeout=15000)
    page.wait_for_timeout(2000)
    
    page.evaluate("fetch('/cart/clear.js', {method: 'POST'})")
    page.wait_for_timeout(500)
    
    page.evaluate(f"""
        fetch('/cart/add.js', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{items: [{{id: {variant_id}, quantity: 1}}]}})
        }}).then(r => r.json())
    """)
    page.wait_for_timeout(500)
    
    cart = page.evaluate("fetch('/cart.js').then(r => r.json())")
    subtotal = cart.get('total_price', 0) / 100
    
    page.goto(f'{store_url}/checkout', wait_until='domcontentloaded', timeout=15000)
    page.wait_for_timeout(5000)
    
    try:
        page.get_by_label('Email').first.fill('wrencole.nyc@gmail.com')
        page.get_by_label('First name').first.fill(shipping['first_name'])
        page.get_by_label('Last name').first.fill(shipping['last_name'])
        
        addr_input = page.locator('#shipping-address1')
        if addr_input.count() > 0:
            addr_input.fill(shipping['address1'])
        else:
            page.get_by_label('Address').first.fill(shipping['address1'])
        
        page.wait_for_timeout(1500)
        page.keyboard.press('Escape')
        page.wait_for_timeout(500)
        
        page.get_by_label('City').first.fill(shipping['city'])
        page.get_by_label('State').first.select_option(label=shipping['state'])
        page.get_by_label('ZIP code').first.fill(shipping['zip'])
    except:
        try:
            page.locator('#checkout_email').fill('wrencole.nyc@gmail.com')
            page.locator('#checkout_shipping_address_zip').fill(shipping['zip'])
            page.locator('#checkout_shipping_address_city').fill(shipping['city'])
        except:
            pass
    
    page.wait_for_timeout(5000)
    
    prices = page.evaluate(r"""() => {
        const text = document.body.innerText;
        const result = {};
        const patterns = {
            'subtotal': /Subtotal\s*\$?([\d,.]+)/i,
            'shipping': /Shipping\s*\$?([\d,.]+)/i,
            'tax': /Tax\s*\$?([\d,.]+)/i,
            'total': /(?:Updated total price:|Total)\s*\$?([\d,.]+)/i,
        };
        for (const [key, pattern] of Object.entries(patterns)) {
            const match = text.match(pattern);
            if (match) result[key] = match[1].replace(',', '');
        }
        return result;
    }""")
    
    return {
        'subtotal': float(prices.get('subtotal', subtotal)),
        'shipping': float(prices.get('shipping', 0)) if prices.get('shipping') else None,
        'tax': float(prices.get('tax', 0)) if prices.get('tax') else None,
        'total': float(prices.get('total', 0)) if prices.get('total') else None,
        'currency': cart.get('currency', 'USD'),
        'cart_subtotal': subtotal,
    }


def _woo_price_check(page, store_url, product_url, shipping):
    """Browser-based WooCommerce price check."""
    if product_url:
        url = product_url if product_url.startswith('http') else f'{store_url}{product_url}'
        page.goto(url, wait_until='domcontentloaded', timeout=15000)
        page.wait_for_timeout(3000)
        page.locator('button.single_add_to_cart_button').first.click()
        page.wait_for_timeout(3000)
    
    page.goto(f'{store_url}/checkout/', wait_until='domcontentloaded', timeout=15000)
    page.wait_for_timeout(5000)
    
    page.locator('#billing_first_name').fill(shipping['first_name'])
    page.locator('#billing_last_name').fill(shipping['last_name'])
    page.locator('#billing_address_1').fill(shipping['address1'])
    page.locator('#billing_city').fill(shipping['city'])
    page.locator('#billing_postcode').fill(shipping['zip'])
    page.locator('#billing_email').fill('wrencole.nyc@gmail.com')
    
    page.wait_for_timeout(5000)
    
    prices = page.evaluate(r"""() => {
        const result = {};
        const parse = el => el ? el.textContent.replace(/[^0-9.]/g, '') : null;
        result.subtotal = parse(document.querySelector('.cart-subtotal .amount, .cart-subtotal bdi'));
        result.shipping = parse(document.querySelector('.shipping .amount, #shipping_method .amount'));
        result.tax = parse(document.querySelector('.tax-total .amount'));
        result.total = parse(document.querySelector('.order-total .amount, .order-total bdi'));
        return result;
    }""")
    
    return {
        'subtotal': float(prices['subtotal']) if prices.get('subtotal') else None,
        'shipping': float(prices['shipping']) if prices.get('shipping') else None,
        'tax': float(prices['tax']) if prices.get('tax') else None,
        'total': float(prices['total']) if prices.get('total') else None,
    }


# ============================================================
# CLI
# ============================================================

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage:')
        print('  python3 detect_platform.py <URL>')
        print('  python3 detect_platform.py <URL> --cart --variant <ID>')
        print('  python3 detect_platform.py <URL> --cart --variant <ID> --discount CODE1 CODE2')
        print('  python3 detect_platform.py <URL> --browser')
        print('  python3 detect_platform.py <URL> --price-check --variant <ID>')
        sys.exit(1)
    
    url = sys.argv[1]
    use_browser = '--browser' in sys.argv
    use_cart = '--cart' in sys.argv
    price_check = '--price-check' in sys.argv
    
    print(f'Detecting platform for: {url}')
    print('---')
    
    result = detect_platform(url, use_browser=use_browser)
    print(json.dumps(result, indent=2))
    
    # Get variant ID
    variant_id = None
    if '--variant' in sys.argv:
        variant_idx = sys.argv.index('--variant') + 1
        variant_id = int(sys.argv[variant_idx])
    elif result.get('product', {}) and result['product'].get('variants'):
        variant_id = result['product']['variants'][0]['id']
    
    # Storefront API cart creation (fast, no browser)
    if use_cart and result.get('storefront_token') and variant_id:
        discount_codes = []
        if '--discount' in sys.argv:
            idx = sys.argv.index('--discount') + 1
            while idx < len(sys.argv) and not sys.argv[idx].startswith('--'):
                discount_codes.append(sys.argv[idx])
                idx += 1
        
        print(f'\n--- Storefront API Cart (variant {variant_id}) ---')
        cart = shopify_cart_create(
            result['store_domain'],
            result['storefront_token'],
            variant_id,
            discount_codes=discount_codes
        )
        print(json.dumps(cart, indent=2))
    
    # Legacy browser-based price check
    elif price_check and variant_id:
        print(f'\n--- Price Check (variant {variant_id}) ---')
        prices = get_checkout_total(
            result['store_domain'], variant_id=variant_id,
            storefront_token=result.get('storefront_token')
        )
        print(json.dumps(prices, indent=2))
