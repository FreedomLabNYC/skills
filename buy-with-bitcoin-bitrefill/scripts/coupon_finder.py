#!/usr/bin/env python3
"""
Coupon Code Finder

Searches multiple sources for discount codes, then validates them
against the store's API (Shopify Storefront API) or checkout page.

Sources (ranked by code quality):
  1. Influencer/podcast codes ("[brand] podcast code") — highest value, 15-20% off
  2. Store homepage banners/popups — reliable first-time customer codes
  3. Common pattern brute-force (WELCOME10, SAVE15, FIRST20, etc.)
  4. Google search ("[store] coupon code [year]")
  5. Reddit search (r/deals, r/coupons, etc.)
  6. X/Twitter search via bird CLI
  7. Coupon aggregator sites (RetailMeNot, CouponFollow, etc.)

For Shopify stores, codes are validated via the Storefront API
(~0.5s per code, pure HTTP, no browser needed).

Usage:
    from coupon_finder import find_coupons
    results = find_coupons(
        store_url='https://www.livemomentous.com',
        store_name='Momentous',
        variant_id=41325780664503,
        storefront_token='8a6e727e18e71aa26257d8d2410f3cd3'
    )
    # Returns: [{code, applicable, savings, source}, ...]

CLI:
    python3 coupon_finder.py "https://www.livemomentous.com" "Momentous" \
        --variant 41325780664503 --token 8a6e727e18e71aa26257d8d2410f3cd3
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

# Common non-coupon strings that look like codes
STOP_WORDS = {
    'HTML', 'HEAD', 'BODY', 'HTTP', 'META', 'LINK', 'TYPE', 'SPAN', 'TRUE',
    'FALSE', 'NULL', 'NONE', 'JSON', 'ARIA', 'ROLE', 'DATA', 'GRID', 'ICON',
    'CODE', 'CODES', 'COUPON', 'COUPONS', 'PROMO', 'PROMOS', 'DISCOUNT',
    'THE', 'FOR', 'AND', 'OFF', 'USE', 'GET', 'SAVE', 'FREE', 'BEST',
    'YOUR', 'THAT', 'THIS', 'WITH', 'FROM', 'DEAL', 'DEALS', 'SITE',
    'PAGE', 'MORE', 'HAVE', 'WILL', 'BEEN', 'JUST', 'ONLY', 'ALSO',
    'SALE', 'SHOP', 'COPY', 'SHOW', 'VIEW', 'CLICK', 'APPLY', 'ENTER',
    'VERIFIED', 'ACTIVE', 'EXPIRED', 'USED', 'TIMES', 'TODAY', 'WORKS',
    'OFFER', 'OFFERS', 'TOTAL', 'ORDER', 'ORDERS', 'CHECKOUT', 'CART',
    'ITEM', 'ITEMS', 'PRODUCT', 'PRODUCTS', 'STORE', 'STORES', 'BRAND',
    'FIRST', 'LAST', 'NEXT', 'BACK', 'HOME', 'MENU', 'SEARCH', 'CLOSE',
    'OPEN', 'SIGN', 'LOGIN', 'EMAIL', 'NAME', 'TEXT', 'FONT', 'SIZE',
    'COLOR', 'STYLE', 'CLASS', 'WIDTH', 'HEIGHT', 'IMAGE', 'TITLE',
    'SCRIPT', 'HTTPS', 'BUTTON', 'INPUT', 'FORM', 'LABEL', 'VALUE',
    'SUBMIT', 'SELECT', 'OPTION', 'TABLE', 'TBODY', 'THEAD',
    'DOCTYPE', 'CHARSET', 'CONTENT', 'DESCRIPTION', 'VIEWPORT',
}


def find_coupons(store_url, store_name, variant_id=None,
                 storefront_token=None, max_codes=30, use_browser=True):
    """
    Search for coupon codes and validate them.
    
    Args:
        store_url: base URL (e.g., 'https://www.livemomentous.com')
        store_name: brand/store name for search queries
        variant_id: Shopify variant ID (for API validation)
        storefront_token: Shopify Storefront API token
        max_codes: max codes to test (default 30)
        use_browser: whether to use Playwright for JS-rendered coupon sites
        
    Returns:
        list of {code, applicable, savings, total, source} sorted by savings
    """
    print(f'[COUPON] Searching for {store_name} discount codes...')
    start = time.time()
    
    # Step 1: Gather codes from all sources
    all_codes = {}  # code -> set of sources
    
    # Source 1: Common pattern brute-force (fast, no network)
    print('[COUPON] Generating common patterns...')
    pattern_codes = _generate_common_patterns(store_name)
    for code in pattern_codes:
        all_codes.setdefault(code, set()).add('pattern')
    print(f'[COUPON]   Generated {len(pattern_codes)} pattern-based codes')
    
    # Source 2: Store homepage (banners, popups)
    print('[COUPON] Checking store homepage...')
    homepage_codes = _check_homepage(store_url)
    for code in homepage_codes:
        all_codes.setdefault(code, set()).add('homepage')
    print(f'[COUPON]   Found {len(homepage_codes)} codes from homepage')
    
    # Source 3: Influencer/podcast codes
    print('[COUPON] Searching for influencer codes...')
    influencer_codes = _search_influencer_codes(store_name)
    for code in influencer_codes:
        all_codes.setdefault(code, set()).add('influencer')
    print(f'[COUPON]   Found {len(influencer_codes)} codes from influencer search')
    
    # Source 4: Google search
    print('[COUPON] Searching Google...')
    google_codes = _search_google(store_name, store_url)
    for code in google_codes:
        all_codes.setdefault(code, set()).add('google')
    print(f'[COUPON]   Found {len(google_codes)} codes from Google')
    
    # Source 5: Reddit search
    print('[COUPON] Searching Reddit...')
    reddit_codes = _search_reddit(store_name)
    for code in reddit_codes:
        all_codes.setdefault(code, set()).add('reddit')
    print(f'[COUPON]   Found {len(reddit_codes)} codes from Reddit')
    
    # Source 6: X/Twitter search
    twitter_codes = _search_twitter(store_name)
    if twitter_codes:
        for code in twitter_codes:
            all_codes.setdefault(code, set()).add('twitter')
        print(f'[COUPON]   Found {len(twitter_codes)} codes from X/Twitter')
    
    # Source 7: Coupon aggregator sites (browser)
    if use_browser:
        print('[COUPON] Scraping coupon sites...')
        aggregator_codes = _scrape_coupon_sites(store_name, store_url)
        for code in aggregator_codes:
            all_codes.setdefault(code, set()).add('aggregator')
        print(f'[COUPON]   Found {len(aggregator_codes)} codes from coupon sites')
    
    # Deduplicate and limit
    unique_codes = list(all_codes.keys())[:max_codes]
    print(f'[COUPON] Total unique codes to test: {len(unique_codes)}')
    
    if not unique_codes:
        print(f'[COUPON] No codes found ({time.time()-start:.1f}s)')
        return []
    
    # Step 2: Validate codes
    if storefront_token and variant_id:
        print(f'[COUPON] Validating via Shopify Storefront API...')
        results = _validate_shopify_api(
            store_url, storefront_token, variant_id, unique_codes, all_codes
        )
    else:
        print(f'[COUPON] No Storefront API available — returning unvalidated codes')
        results = [{'code': c, 'applicable': None, 'savings': 0, 'total': None,
                    'source': ', '.join(all_codes[c])} for c in unique_codes]
    
    elapsed = time.time() - start
    working = [r for r in results if r.get('applicable')]
    print(f'[COUPON] Done in {elapsed:.1f}s — {len(working)} working codes out of {len(unique_codes)} tested')
    
    return results


# ============================================================
# Code Gathering Sources
# ============================================================

def _search_google(store_name, store_url):
    """Search Google for coupon codes."""
    codes = set()
    domain = urllib.parse.urlparse(store_url).netloc
    
    queries = [
        f'{store_name} coupon code 2026',
        f'{store_name} promo code discount',
        f'{domain} coupon code',
    ]
    
    for query in queries:
        try:
            encoded = urllib.parse.quote(query)
            req = urllib.request.Request(
                f'https://www.google.com/search?q={encoded}',
                headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
            )
            resp = urllib.request.urlopen(req, timeout=10)
            html = resp.read().decode('utf-8', errors='ignore')
            text = re.sub(r'<[^>]+>', ' ', html)
            
            codes.update(_extract_codes_from_text(text))
        except:
            pass
    
    return codes


def _check_homepage(store_url):
    """Check store homepage for promotional codes in banners/popups."""
    codes = set()
    
    try:
        req = urllib.request.Request(
            store_url,
            headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
        )
        resp = urllib.request.urlopen(req, timeout=10)
        html = resp.read().decode('utf-8', errors='ignore')
        
        # Look for common promo patterns in HTML
        # Stores often embed promo codes in banners, popups, or data attributes
        patterns = [
            r'(?:discount|coupon|promo)(?:_?code)?["\'\s:=]+([A-Z][A-Z0-9]{3,20})',
            r'data-(?:discount|coupon|promo)["\'\s:=]+([A-Z][A-Z0-9]{3,20})',
            r'(?:use|enter|apply)\s+(?:code\s+)?["\']?([A-Z][A-Z0-9]{3,20})["\']?',
            r'(?:code|coupon):\s*["\']([A-Z][A-Z0-9]{3,20})["\']',
        ]
        
        for pattern in patterns:
            for m in re.finditer(pattern, html, re.IGNORECASE):
                code = m.group(1).upper()
                if _is_likely_coupon(code):
                    codes.add(code)
    except:
        pass
    
    return codes


def _search_influencer_codes(store_name):
    """Search for influencer/podcast sponsor codes."""
    codes = set()
    
    queries = [
        f'{store_name} podcast code',
        f'{store_name} sponsor code discount',
        f'{store_name} influencer discount code',
        f'{store_name} YouTube code',
    ]
    
    for query in queries:
        try:
            encoded = urllib.parse.quote(query)
            req = urllib.request.Request(
                f'https://www.google.com/search?q={encoded}',
                headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
            )
            resp = urllib.request.urlopen(req, timeout=10)
            html = resp.read().decode('utf-8', errors='ignore')
            text = re.sub(r'<[^>]+>', ' ', html)
            
            codes.update(_extract_codes_from_text(text))
        except:
            pass
    
    return codes


def _scrape_coupon_sites(store_name, store_url):
    """Scrape coupon aggregator sites using Playwright."""
    codes = set()
    domain = urllib.parse.urlparse(store_url).netloc.replace('www.', '')
    name_slug = store_name.lower().replace(' ', '-')
    
    # Sites to try
    urls = [
        f'https://www.retailmenot.com/view/{domain}',
        f'https://couponfollow.com/site/{domain}',
        f'https://www.coupons.com/coupon-codes/{name_slug}',
    ]
    
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print('[COUPON]   Playwright not available — skipping aggregator scraping')
        return codes
    
    try:
        # Don't kill browser if it's being used for something else
        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path=BRAVE_PATH, headless=False,
                args=BRAVE_ARGS, ignore_default_args=['--enable-automation']
            )
            ctx = browser.new_context()
            page = ctx.new_page()
            page.set_default_timeout(10000)
            
            for url in urls:
                try:
                    page.goto(url, wait_until='domcontentloaded', timeout=10000)
                    page.wait_for_timeout(3000)
                    
                    # Extract codes from page
                    page_codes = page.evaluate("""() => {
                        const codes = new Set();
                        
                        // Common coupon site patterns
                        // 1. data-code attributes
                        document.querySelectorAll('[data-code]').forEach(el => {
                            const code = el.getAttribute('data-code').trim();
                            if (code.length >= 3 && code.length <= 25) codes.add(code.toUpperCase());
                        });
                        
                        // 2. Coupon code containers
                        const selectors = [
                            '.coupon-code', '.code', '.promo-code', '.discount-code',
                            '[class*="coupon-code"]', '[class*="promo-code"]',
                            '[data-testid*="code"]', '[aria-label*="code"]',
                            '.offer-code', '.voucher-code'
                        ];
                        selectors.forEach(sel => {
                            document.querySelectorAll(sel).forEach(el => {
                                const text = el.textContent.trim();
                                if (text.length >= 3 && text.length <= 25 && /^[A-Z0-9]+$/i.test(text)) {
                                    codes.add(text.toUpperCase());
                                }
                            });
                        });
                        
                        // 3. Text patterns in visible content
                        const bodyText = document.body.innerText;
                        const matches = bodyText.match(/(?:code|coupon|promo)[:\\s]+"?([A-Z][A-Z0-9]{2,20})"?/gi) || [];
                        matches.forEach(m => {
                            const code = m.replace(/.*?([A-Z][A-Z0-9]{2,20}).*/i, '$1').toUpperCase();
                            if (code.length >= 3 && code.length <= 25) codes.add(code);
                        });
                        
                        return Array.from(codes);
                    }""")
                    
                    for code in page_codes:
                        if _is_likely_coupon_js(code):
                            codes.add(code)
                            
                except Exception as e:
                    pass  # Site unavailable or blocked
            
            browser.close()
    except Exception as e:
        print(f'[COUPON]   Browser scraping failed: {e}')
    
    return codes


# ============================================================
# Code Extraction Helpers
# ============================================================

def _extract_codes_from_text(text):
    """Extract likely coupon codes from text content."""
    codes = set()
    
    # Pattern 1: "code: XXXX" or "use code XXXX" or "coupon XXXX"
    for m in re.finditer(
        r'(?:code|coupon|promo|discount|use|enter|apply)[:\s"\']+([A-Z][A-Z0-9]{2,20})',
        text, re.IGNORECASE
    ):
        code = m.group(1).upper()
        if _is_likely_coupon(code):
            codes.add(code)
    
    # Pattern 2: Standalone ALL-CAPS words near coupon context
    # Look for words within 50 chars of "coupon", "code", "discount", etc.
    for m in re.finditer(
        r'(?:coupon|promo|discount|code|save|off|percent)[^.]{0,50}?([A-Z][A-Z0-9]{4,20})',
        text, re.IGNORECASE
    ):
        code = m.group(1).upper()
        if _is_likely_coupon(code):
            codes.add(code)
    
    return codes


def _is_likely_coupon(code):
    """Check if a string looks like a coupon code vs a random word."""
    if not code or len(code) < 3 or len(code) > 25:
        return False
    if code in STOP_WORDS:
        return False
    if not re.match(r'^[A-Z][A-Z0-9]+$', code):
        return False
    # Codes usually have a mix of letters/numbers or recognizable patterns
    # Pure dictionary words less than 6 chars are likely noise
    if len(code) < 6 and code.isalpha():
        return False
    return True


def _generate_common_patterns(store_name):
    """Generate common coupon code patterns to brute-force.
    
    Many stores use predictable patterns like WELCOME10, SAVE15, etc.
    This is cheap to test via API and catches a surprising number of codes.
    """
    codes = set()
    
    # Generic prefixes that many stores use
    prefixes = [
        'WELCOME', 'SAVE', 'FIRST', 'NEW', 'HELLO', 'FREE',
        'TAKE', 'GET', 'EXTRA', 'DEAL', 'SALE', 'OFFER',
        'VIP', 'SPECIAL', 'TREAT', 'THANKS', 'GIFT',
        'SUMMER', 'WINTER', 'SPRING', 'FALL',
        'HOLIDAY', 'NEWYEAR', 'BLACKFRIDAY', 'CYBER',
    ]
    
    # Common percentage suffixes
    suffixes = ['5', '10', '15', '20', '25', '30', '40', '50']
    
    # Generate PREFIX + NUMBER combos
    for prefix in prefixes:
        for suffix in suffixes:
            codes.add(f'{prefix}{suffix}')
    
    # Brand-specific patterns
    brand = store_name.upper().replace(' ', '')
    brand_short = brand[:6] if len(brand) > 6 else brand
    for suffix in suffixes:
        codes.add(f'{brand}{suffix}')
        codes.add(f'{brand_short}{suffix}')
    
    # Standalone codes
    standalone = [
        'FREESHIP', 'FREESHIPPING', 'SHIPFREE', 'NOSHIPPING',
        'NEWSLETTER', 'SIGNUP', 'EMAIL', 'SUBSCRIBE',
        'LOYALTY', 'REWARD', 'MEMBER', 'EXCLUSIVE',
        'FLASH', 'TODAY', 'LIMITED', 'LASTCHANCE',
        'REFERRAL', 'FRIEND', 'SHARE', 'SOCIAL',
        'TRYIT', 'TRYME', 'SAMPLE', 'STARTER',
        'COMEBACK', 'MISSYOU', 'RETURN', 'BACKINSTOCK',
        'BIRTHDAY', 'BDAY', 'CELEBRATE',
    ]
    codes.update(standalone)
    
    return codes


def _search_reddit(store_name):
    """Search Reddit for coupon codes."""
    codes = set()
    
    # Reddit's old search API (no auth needed)
    queries = [
        f'{store_name} coupon code',
        f'{store_name} promo discount',
    ]
    
    for query in queries:
        try:
            encoded = urllib.parse.quote(query)
            req = urllib.request.Request(
                f'https://old.reddit.com/search.json?q={encoded}&sort=new&t=year&limit=10',
                headers={
                    'User-Agent': 'Mozilla/5.0 (compatible; coupon-finder/1.0)',
                    'Accept': 'application/json'
                }
            )
            resp = urllib.request.urlopen(req, timeout=10)
            data = json.loads(resp.read())
            
            for post in data.get('data', {}).get('children', []):
                post_data = post.get('data', {})
                text = f"{post_data.get('title', '')} {post_data.get('selftext', '')}"
                codes.update(_extract_codes_from_text(text))
        except:
            pass
    
    return codes


def _search_twitter(store_name):
    """Search X/Twitter for brand discount codes using bird CLI."""
    codes = set()
    
    # Check if bird CLI is available
    bird_path = subprocess.run(['which', 'bird'], capture_output=True, text=True)
    if bird_path.returncode != 0:
        return codes
    
    try:
        result = subprocess.run(
            ['bird', 'search', f'{store_name} discount code', '--limit', '20'],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            codes.update(_extract_codes_from_text(result.stdout))
    except:
        pass
    
    return codes


def _is_likely_coupon_js(code):
    """JS-side filter (less strict since codes come from structured elements)."""
    if not code or len(code) < 3 or len(code) > 25:
        return False
    if code in STOP_WORDS:
        return False
    return True


# ============================================================
# Code Validation
# ============================================================

def _validate_shopify_api(store_url, token, variant_id, codes, code_sources):
    """Validate codes via Shopify Storefront API."""
    # Import from our detect_platform module
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, script_dir)
    
    try:
        from detect_platform import shopify_cart_create
    except ImportError:
        print('[COUPON]   Could not import detect_platform — returning unvalidated')
        return [{'code': c, 'applicable': None, 'savings': 0,
                'source': ', '.join(code_sources.get(c, set()))} for c in codes]
    
    # Get baseline total (no discount)
    baseline = shopify_cart_create(store_url, token, variant_id)
    if 'error' in baseline:
        print(f'[COUPON]   API error: {baseline["error"]}')
        return [{'code': c, 'applicable': None, 'savings': 0,
                'source': ', '.join(code_sources.get(c, set()))} for c in codes]
    
    baseline_total = baseline['total']
    results = []
    
    for i, code in enumerate(codes):
        cart = shopify_cart_create(store_url, token, variant_id, discount_codes=[code])
        
        if 'error' in cart:
            results.append({
                'code': code, 'applicable': False, 'savings': 0,
                'total': baseline_total,
                'source': ', '.join(code_sources.get(code, set()))
            })
            continue
        
        dc_list = cart.get('discount_codes', [])
        applicable = dc_list[0].get('applicable', False) if dc_list else False
        savings = round(baseline_total - cart['total'], 2) if applicable else 0
        
        results.append({
            'code': code,
            'applicable': applicable,
            'savings': savings,
            'total': cart['total'],
            'source': ', '.join(code_sources.get(code, set()))
        })
        
        if applicable:
            print(f'[COUPON]   ✅ {code} — saves ${savings:.2f} (total ${cart["total"]:.2f})')
        
        # Rate limit: ~2 requests/second
        if i < len(codes) - 1:
            time.sleep(0.5)
    
    # Sort: working codes first (by savings), then non-working
    results.sort(key=lambda r: (-r['savings'], not r.get('applicable', False)))
    
    return results


# ============================================================
# CLI
# ============================================================

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Find and validate coupon codes')
    parser.add_argument('store_url', help='Store URL (e.g., https://www.livemomentous.com)')
    parser.add_argument('store_name', help='Brand/store name for search queries')
    parser.add_argument('--variant', type=int, help='Shopify variant ID for API validation')
    parser.add_argument('--token', help='Shopify Storefront API token')
    parser.add_argument('--no-browser', action='store_true', help='Skip browser-based coupon scraping')
    parser.add_argument('--max-codes', type=int, default=30, help='Max codes to test')
    args = parser.parse_args()
    
    results = find_coupons(
        store_url=args.store_url,
        store_name=args.store_name,
        variant_id=args.variant,
        storefront_token=args.token,
        max_codes=args.max_codes,
        use_browser=not args.no_browser
    )
    
    if results:
        working = [r for r in results if r.get('applicable')]
        if working:
            print(f'\n=== {len(working)} Working Codes ===')
            for r in working:
                print(f"  {r['code']}: saves ${r['savings']:.2f} (total ${r['total']:.2f}) — source: {r['source']}")
            print(f'\nBest code: {working[0]["code"]} (saves ${working[0]["savings"]:.2f})')
        else:
            print('\nNo working codes found.')
    else:
        print('\nNo codes found to test.')
