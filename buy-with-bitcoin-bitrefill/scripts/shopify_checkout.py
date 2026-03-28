#!/usr/bin/env python3
"""
Shopify Checkout Module — Reusable for any Shopify store

Handles the full checkout flow: add to cart → fill shipping → fill payment → submit.
Works with both old-style Shopify checkout (id-based selectors) and new checkout
(label-based selectors with hidden autofill fields).

Shopify uses two checkout systems:
  1. Classic: `#checkout_shipping_address_first_name` etc.
  2. New (2024+): Dynamic IDs, label-based, `get_by_label()` with `.first` needed
  Both use iframes for card fields: `iframe.card-fields-iframe` (classic) or
  `iframe[title="Field container for: ..."]` (new)

Usage:
    from shopify_checkout import ShopifyCheckout
    
    checkout = ShopifyCheckout(
        store_domain='https://www.livemomentous.com',
        shipping_address={...},
        card={'number': '...', 'exp': '...', 'cvv': '...', 'name': '...'},
        email='wrencole.nyc@gmail.com'
    )
    result = checkout.run(variant_id=41325780664503, quantity=1)

Based on patterns from:
  - SneakerBot (github.com/samc621/SneakerBot) — 800+ stars, tested on 100s of Shopify stores
  - Our own Momentous purchase (2026-03-21)
  - Shopify Storefront API docs
"""

import json
import os
import re
import time
from datetime import datetime
from pathlib import Path


# ============================================================
# Configuration
# ============================================================

BRAVE_PATH = '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser'
BRAVE_ARGS = [
    '--no-first-run', '--no-default-browser-check', '--disable-extensions',
    '--disable-component-extensions-with-background-pages', '--disable-brave-update',
    '--disable-brave-extension', '--disable-component-update',
    '--disable-blink-features=AutomationControlled'
]
SCREENSHOT_DIR = os.path.expanduser('~/.openclaw/openclaw-workspace/purchases')


class ShopifyCheckout:
    """
    Reusable Shopify checkout handler.
    
    Supports:
    - Cart via AJAX API (/cart/add.js, /cart/clear.js)
    - Both classic and new Shopify checkout form layouts
    - Card iframes (PCI-compliant fields)
    - Address autocomplete dismissal
    - Captcha detection (flags, doesn't auto-solve)
    - Shipping method selection
    - Screenshot at each stage
    """
    
    def __init__(self, store_domain, shipping_address, card, email,
                 billing_address=None, shipping_speed=0):
        """
        Args:
            store_domain: e.g., 'https://www.livemomentous.com'
            shipping_address: dict with keys: first_name, last_name, address1, 
                             address2 (optional), city, state, zip, phone (optional),
                             company (optional)
            card: dict with keys: number, exp (MM/YY), cvv, name
            email: buyer email
            billing_address: dict (same format) or None to use shipping
            shipping_speed: 0 = cheapest, 1 = next cheapest, etc.
        """
        self.domain = store_domain.rstrip('/')
        self.shipping = shipping_address
        self.billing = billing_address
        self.card = card
        self.email = email
        self.shipping_speed = shipping_speed
        
        self.page = None
        self.browser = None
        self.ctx = None
        self.screenshots = []
        self.start_time = None
    
    def _screenshot(self, label):
        """Save screenshot and track it."""
        Path(SCREENSHOT_DIR).mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d-%H%M%S')
        path = os.path.join(SCREENSHOT_DIR, f'{ts}-shopify-{label}.png')
        try:
            self.page.screenshot(path=path, full_page=False)
            self.screenshots.append(path)
        except:
            pass
        return path
    
    def _elapsed(self):
        return f'{time.time() - self.start_time:.1f}s'
    
    def _log(self, msg):
        print(f'[SHOPIFY] [{self._elapsed()}] {msg}')
    
    # --------------------------------------------------------
    # Cart Management
    # --------------------------------------------------------
    
    def clear_cart(self):
        """Clear all items from cart via AJAX API."""
        self.page.evaluate("fetch('/cart/clear.js', {method: 'POST'})")
        self.page.wait_for_timeout(500)
    
    def add_to_cart(self, variant_id, quantity=1):
        """Add item to cart via AJAX API. Returns cart JSON."""
        result = self.page.evaluate(f"""
            fetch('/cart/add.js', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{items: [{{id: {variant_id}, quantity: {quantity}}}]}})
            }}).then(r => r.json())
        """)
        self.page.wait_for_timeout(500)
        return result
    
    def get_cart(self):
        """Get current cart contents."""
        return self.page.evaluate("fetch('/cart.js').then(r => r.json())")
    
    # --------------------------------------------------------
    # Form Filling — handles both classic and new Shopify checkout
    # --------------------------------------------------------
    
    def _fill_field(self, label_text, value, is_select=False):
        """
        Fill a form field by label text using .first to handle
        Shopify's hidden autofill duplicate fields.
        """
        if not value:
            return
        
        try:
            if is_select:
                el = self.page.get_by_label(label_text).first
                el.select_option(label=value)
            else:
                el = self.page.get_by_label(label_text).first
                el.fill(value)
        except Exception as e:
            self._log(f'  Warning: Could not fill "{label_text}": {e}')
    
    def _fill_field_by_id(self, selector, value, is_select=False):
        """Fill field by CSS selector (fallback for classic checkout)."""
        if not value:
            return
        try:
            el = self.page.locator(selector)
            if el.count() > 0 and el.first.is_visible():
                if is_select:
                    el.first.select_option(value)
                else:
                    el.first.fill(value)
        except Exception as e:
            self._log(f'  Warning: Could not fill {selector}: {e}')
    
    def fill_email(self):
        """Fill email field."""
        # Try new-style first
        try:
            self._fill_field('Email', self.email)
            return
        except:
            pass
        # Classic fallback
        self._fill_field_by_id('input#checkout_email', self.email)
    
    def fill_shipping_address(self):
        """Fill shipping address fields."""
        addr = self.shipping
        
        # Detect which checkout style we're on
        classic = self.page.locator('#checkout_shipping_address_first_name')
        
        if classic.count() > 0 and classic.is_visible():
            # Classic Shopify checkout
            self._log('Detected classic Shopify checkout')
            prefix = '#checkout_shipping_address_'
            self._fill_field_by_id(f'{prefix}first_name', addr['first_name'])
            self._fill_field_by_id(f'{prefix}last_name', addr['last_name'])
            self._fill_field_by_id(f'{prefix}company', addr.get('company', ''))
            self._fill_field_by_id(f'{prefix}address1', addr['address1'])
            self._fill_field_by_id(f'{prefix}address2', addr.get('address2', ''))
            self._fill_field_by_id(f'{prefix}city', addr['city'])
            self._fill_field_by_id(f'{prefix}province', addr['state'], is_select=True)
            self._fill_field_by_id(f'{prefix}zip', addr['zip'])
            self._fill_field_by_id(f'{prefix}phone', addr.get('phone', ''))
        else:
            # New Shopify checkout (dynamic IDs, label-based)
            self._log('Detected new Shopify checkout')
            self._fill_field('First name', addr['first_name'])
            self._fill_field('Last name', addr['last_name'])
            self._fill_field('Company', addr.get('company', ''))
            
            # Address field — use specific ID to avoid autocomplete issues
            addr_input = self.page.locator('#shipping-address1')
            if addr_input.count() > 0:
                addr_input.fill(addr['address1'])
            else:
                self._fill_field('Address', addr['address1'])
            
            # Dismiss address autocomplete dropdown
            self.page.wait_for_timeout(1500)
            self.page.keyboard.press('Escape')
            self.page.wait_for_timeout(500)
            
            self._fill_field('Apartment', addr.get('address2', ''))
            self._fill_field('City', addr['city'])
            self._fill_field('State', addr['state'], is_select=True)
            self._fill_field('ZIP code', addr['zip'])
            self._fill_field('Phone', addr.get('phone', ''))
    
    def fill_card_details(self):
        """
        Fill card details in Shopify's PCI-compliant iframes.
        
        Handles both:
        - Classic: `iframe.card-fields-iframe` (indexed 0-3)
        - New: `iframe[title="Field container for: ..."]` (title-based)
        """
        card = self.card
        
        # Ensure Credit Card is selected as payment method
        cc_radio = self.page.locator('#basic-creditCards, input[value="credit_card"]')
        if cc_radio.count() > 0:
            cc_radio.first.click()
            self.page.wait_for_timeout(1000)
        
        # Try new-style iframes first (title-based)
        new_card_frame = self.page.locator('iframe[title*="Card number"]')
        classic_card_frames = self.page.locator('iframe.card-fields-iframe')
        
        if new_card_frame.count() > 0:
            self._log('Filling card via new-style title iframes')
            self._fill_iframe_field('iframe[title*="Card number"]', 'Card number', card['number'])
            self._fill_iframe_field('iframe[title*="Name on card"]', 'Name on card', card['name'])
            self._fill_iframe_field('iframe[title*="Expiration"]', 'Expiration date', card['exp'])
            self._fill_iframe_field('iframe[title*="Security code"]', 'Security code', card['cvv'])
            
        elif classic_card_frames.count() >= 3:
            self._log('Filling card via classic indexed iframes')
            # Classic: iframes are ordered: number, name, expiry, cvv
            frames = self.page.query_selector_all('iframe.card-fields-iframe')
            
            if len(frames) >= 4:
                self._fill_classic_iframe(frames[0], '#number', card['number'])
                self._fill_classic_iframe(frames[1], '#name', card['name'])
                self._fill_classic_iframe(frames[2], '#expiry', card['exp'])
                self._fill_classic_iframe(frames[3], '#verification_value', card['cvv'])
            elif len(frames) == 3:
                # Some stores don't have name field
                self._fill_classic_iframe(frames[0], '#number', card['number'])
                self._fill_classic_iframe(frames[1], '#expiry', card['exp'])
                self._fill_classic_iframe(frames[2], '#verification_value', card['cvv'])
        else:
            self._log('WARNING: No card iframes found!')
    
    def _fill_iframe_field(self, iframe_selector, role_name, value):
        """Fill a field inside an iframe using role-based selector."""
        try:
            frame = self.page.frame_locator(iframe_selector)
            frame.get_by_role('textbox', name=role_name).fill(value)
            self.page.wait_for_timeout(300)
        except Exception as e:
            self._log(f'  Warning: iframe fill failed for {role_name}: {e}')
    
    def _fill_classic_iframe(self, frame_handle, selector, value):
        """Fill a field inside a classic iframe using element handle."""
        try:
            frame = frame_handle.content_frame()
            frame.wait_for_selector(selector, timeout=5000)
            frame.type(selector, value, delay=10)
            self.page.wait_for_timeout(300)
        except Exception as e:
            self._log(f'  Warning: classic iframe fill failed for {selector}: {e}')
    
    # --------------------------------------------------------
    # Navigation
    # --------------------------------------------------------
    
    def click_continue(self):
        """Click the continue/submit button (works for both checkout styles)."""
        # Try multiple button patterns
        clicked = self.page.evaluate("""() => {
            // Classic: #continue_button
            let btn = document.querySelector('#continue_button');
            if (btn && btn.getBoundingClientRect().width > 0) { btn.click(); return 'classic'; }
            
            // New: button with "Pay now" text
            for (const b of document.querySelectorAll('button')) {
                const t = b.textContent.trim().toLowerCase();
                if (t.includes('pay now') && b.getBoundingClientRect().width > 0) { 
                    b.click(); return 'pay_now'; 
                }
            }
            
            // New: button with "Continue to shipping"
            for (const b of document.querySelectorAll('button[type="submit"]')) {
                if (b.getBoundingClientRect().width > 0) { b.click(); return 'submit'; }
            }
            
            return 'none';
        }""")
        self._log(f'Clicked continue: {clicked}')
        self.page.wait_for_timeout(5000)
    
    def select_shipping_method(self, index=0):
        """Select shipping method by index (0 = first/cheapest)."""
        self.page.evaluate(f"""() => {{
            const methods = document.querySelectorAll('input[name*="shipping_rate"], input[name*="shipping"]');
            if (methods.length > {index}) methods[{index}].click();
        }}""")
        self.page.wait_for_timeout(1000)
    
    def check_captcha(self):
        """Check if a captcha is present. Returns True if detected."""
        has_captcha = self.page.evaluate("""() => {
            return !!(document.querySelector('#g-recaptcha') || 
                     document.querySelector('.g-recaptcha') ||
                     document.querySelector('iframe[src*="recaptcha"]'));
        }""")
        if has_captcha:
            self._log('⚠️ CAPTCHA DETECTED — manual intervention needed')
        return has_captcha
    
    def get_order_total(self):
        """Extract the order total from the checkout page."""
        total = self.page.evaluate(r"""() => {
            const text = document.body.innerText;
            const match = text.match(/(?:Total|USD)\s*\$?([\d,]+\.\d{2})/i);
            return match ? match[1].replace(',', '') : null;
        }""")
        return float(total) if total else None
    
    def check_confirmation(self):
        """Check if we're on the confirmation page."""
        url = self.page.url
        text = self.page.inner_text('body')
        
        is_confirmed = ('thank' in url.lower() or
                       'confirmation' in text.lower()[:500] or
                       'order is confirmed' in text.lower()[:500])
        
        conf_number = None
        match = re.search(r'Confirmation\s*#?\s*([A-Z0-9]+)', text)
        if match:
            conf_number = match.group(1)
        
        return is_confirmed, conf_number
    
    # --------------------------------------------------------
    # Main Flow
    # --------------------------------------------------------
    
    def run(self, variant_id, quantity=1, dry_run=False):
        """
        Execute full checkout flow.
        
        Args:
            variant_id: Shopify variant ID to purchase
            quantity: number of items
            dry_run: if True, stop before clicking "Pay now"
            
        Returns:
            dict with confirmation details, screenshots, timing
        """
        import subprocess
        from playwright.sync_api import sync_playwright
        
        # Kill existing Brave
        subprocess.run(['pkill', '-9', '-f', 'Brave'], capture_output=True)
        time.sleep(1)
        
        self.start_time = time.time()
        
        with sync_playwright() as p:
            self.browser = p.chromium.launch(
                executable_path=BRAVE_PATH, headless=False,
                args=BRAVE_ARGS, ignore_default_args=['--enable-automation']
            )
            self.ctx = self.browser.new_context()
            self.page = self.ctx.new_page()
            self.page.set_default_timeout(15000)
            
            try:
                return self._run_flow(variant_id, quantity, dry_run)
            except Exception as e:
                self._screenshot('error')
                self._log(f'ERROR: {e}')
                return {
                    'success': False, 'error': str(e),
                    'screenshots': self.screenshots,
                    'elapsed': self._elapsed()
                }
            finally:
                self.browser.close()
    
    def _run_flow(self, variant_id, quantity, dry_run):
        """Inner checkout flow."""
        
        # Step 1: Navigate and add to cart
        self._log(f'Adding variant {variant_id} x{quantity} to cart')
        self.page.goto(f'{self.domain}/products', wait_until='domcontentloaded', timeout=15000)
        self.page.wait_for_timeout(2000)
        
        self.clear_cart()
        result = self.add_to_cart(variant_id, quantity)
        self._log(f'Cart: {json.dumps(result).get("title", "item added") if isinstance(result, dict) else "added"}')
        
        cart = self.get_cart()
        total = cart.get('total_price', 0) / 100
        self._log(f'Cart total: ${total:.2f} | Items: {cart.get("item_count", 0)}')
        
        # Step 2: Go to checkout
        self._log('Navigating to checkout')
        self.page.goto(f'{self.domain}/checkout', wait_until='domcontentloaded', timeout=15000)
        self.page.wait_for_timeout(5000)
        
        # Step 3: Check for captcha
        if self.check_captcha():
            self._screenshot('captcha')
            return {
                'success': False, 'error': 'captcha_detected',
                'screenshots': self.screenshots, 'elapsed': self._elapsed()
            }
        
        # Step 4: Fill contact + shipping
        self._log('Filling email')
        self.fill_email()
        
        self._log('Filling shipping address')
        self.fill_shipping_address()
        
        self._screenshot('shipping-filled')
        self.page.wait_for_timeout(2000)
        
        # Step 5: Fill card details (new checkout shows all on one page)
        self._log('Filling card details')
        self.fill_card_details()
        
        self._screenshot('card-filled')
        self.page.wait_for_timeout(1000)
        
        # Step 6: Check total
        order_total = self.get_order_total()
        if order_total:
            self._log(f'Order total: ${order_total:.2f}')
        
        if dry_run:
            self._screenshot('dry-run-ready')
            self._log('DRY RUN — stopping before payment')
            return {
                'success': True, 'dry_run': True,
                'total': order_total, 'screenshots': self.screenshots,
                'elapsed': self._elapsed()
            }
        
        # Step 7: Submit order
        self._log('Submitting order...')
        self.click_continue()
        self.page.wait_for_timeout(10000)
        
        # Step 8: Check for multi-step checkout (shipping method selection)
        # Some stores have separate shipping page
        shipping_methods = self.page.locator('input[name*="shipping_rate"]')
        if shipping_methods.count() > 0:
            self._log(f'Shipping method page — selecting option {self.shipping_speed}')
            self.select_shipping_method(self.shipping_speed)
            self.click_continue()
            self.page.wait_for_timeout(5000)
        
        # Step 9: Check confirmation
        self._screenshot('result')
        confirmed, conf_number = self.check_confirmation()
        
        if confirmed:
            self._log(f'✅ ORDER CONFIRMED! #{conf_number}')
        else:
            self._log('⚠️ Could not confirm order — check screenshots')
        
        return {
            'success': confirmed,
            'confirmation_number': conf_number,
            'total': order_total,
            'url': self.page.url,
            'screenshots': self.screenshots,
            'elapsed': self._elapsed()
        }


# ============================================================
# CLI for testing
# ============================================================

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Shopify checkout')
    parser.add_argument('--store', required=True, help='Store domain (e.g., https://www.livemomentous.com)')
    parser.add_argument('--variant', required=True, type=int, help='Shopify variant ID')
    parser.add_argument('--quantity', default=1, type=int)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    
    secrets = json.load(open(os.path.expanduser('~/.openclaw/secrets.json')))
    
    # Default shipping address (Fat Cat Fab Lab)
    shipping = {
        'first_name': 'Harrison',
        'last_name': 'Friedes',
        'company': 'Fat Cat Fab Lab',
        'address1': '224 West 4th Street',
        'address2': '',
        'city': 'New York',
        'state': 'New York',
        'zip': '10014',
        'phone': ''
    }
    
    # Card details would come from Bitrefill Visa redemption
    # For testing, use dummy values
    card = {
        'number': '4111111111111111',
        'exp': '12/30',
        'cvv': '123',
        'name': 'Wren Cole'
    }
    
    checkout = ShopifyCheckout(
        store_domain=args.store,
        shipping_address=shipping,
        card=card,
        email='wrencole.nyc@gmail.com'
    )
    
    result = checkout.run(variant_id=args.variant, quantity=args.quantity, dry_run=args.dry_run)
    print(json.dumps(result, indent=2))
