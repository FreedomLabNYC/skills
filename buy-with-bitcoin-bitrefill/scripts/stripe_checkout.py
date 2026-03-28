#!/usr/bin/env python3
"""
Stripe Hosted Checkout Module — for sites using checkout.stripe.com

When a merchant uses Stripe-hosted checkout, the buyer is redirected to
checkout.stripe.com where ALL fields are standard DOM elements (no iframes!).
This makes it the easiest checkout to automate.

Stripe-hosted checkout is used by:
- SaaS products (Cursor, Vercel, Notion subscriptions)
- Digital goods sellers
- Some DTC physical goods brands
- Any merchant using Stripe Payment Links

Usage:
    from stripe_checkout import StripeHostedCheckout
    
    checkout = StripeHostedCheckout(
        billing_info={...},
        card={'number': '...', 'exp': '...', 'cvv': '...', 'name': '...'},
        email='wrencole.nyc@gmail.com'
    )
    result = checkout.complete(checkout_url)

Can also handle the pre-checkout step (navigating merchant site, adding to cart)
if given a merchant URL + add-to-cart instructions.
"""

import json
import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path


BRAVE_PATH = '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser'
BRAVE_ARGS = [
    '--no-first-run', '--no-default-browser-check', '--disable-extensions',
    '--disable-component-extensions-with-background-pages', '--disable-brave-update',
    '--disable-brave-extension', '--disable-component-update',
    '--disable-blink-features=AutomationControlled'
]
SCREENSHOT_DIR = os.path.expanduser('~/.openclaw/openclaw-workspace/purchases')


class StripeHostedCheckout:
    """
    Handles Stripe-hosted checkout at checkout.stripe.com.
    
    All fields are standard DOM elements — no iframes, no PCI complications.
    This is the simplest checkout to automate.
    
    Field map (verified from Stripe docs + source):
        input#email                     — Email
        input#cardNumber                — Card number
        input#cardExpiry                — Expiration (MM / YY)
        input#cardCvc                   — CVC/CVV
        input#billingName               — Name on card
        select#billingCountry           — Country (value="US")
        input#billingPostalCode         — ZIP/Postal code
        input#billingAddressLine1       — Street address (if shipping required)
        input#billingAddressLine2       — Apt/suite
        input#billingLocality           — City
        input#billingAdministrativeArea — State/Province (or select)
        button.SubmitButton             — Pay button
    
    Some fields only appear if the merchant requires shipping address.
    Card fields appear after email is entered (Stripe checks for Link/express first).
    """
    
    def __init__(self, card, email, billing_name=None, 
                 shipping_address=None, phone=None):
        """
        Args:
            card: dict with keys: number, exp (MM/YY), cvv, name
            email: buyer email
            billing_name: name for billing (defaults to card['name'])
            shipping_address: dict with address1, address2, city, state, zip, country
                             Only needed if merchant requires shipping
            phone: phone number (some merchants require it)
        """
        self.card = card
        self.email = email
        self.billing_name = billing_name or card.get('name', '')
        self.shipping = shipping_address or {}
        self.phone = phone or ''
        
        self.page = None
        self.browser = None
        self.screenshots = []
        self.start_time = None
    
    def _screenshot(self, label):
        Path(SCREENSHOT_DIR).mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d-%H%M%S')
        path = os.path.join(SCREENSHOT_DIR, f'{ts}-stripe-{label}.png')
        try:
            self.page.screenshot(path=path, full_page=False)
            self.screenshots.append(path)
        except:
            pass
        return path
    
    def _elapsed(self):
        return f'{time.time() - self.start_time:.1f}s'
    
    def _log(self, msg):
        print(f'[STRIPE] [{self._elapsed()}] {msg}')
    
    def _fill(self, selector, value):
        """Fill a field, handling cases where it may not exist."""
        if not value:
            return False
        try:
            el = self.page.locator(selector)
            if el.count() > 0 and el.first.is_visible():
                el.first.fill(value)
                self.page.wait_for_timeout(200)
                return True
        except Exception as e:
            self._log(f'  Could not fill {selector}: {e}')
        return False
    
    def _select(self, selector, value):
        """Select a dropdown value."""
        if not value:
            return False
        try:
            el = self.page.locator(selector)
            if el.count() > 0 and el.first.is_visible():
                el.first.select_option(value=value)
                self.page.wait_for_timeout(200)
                return True
        except Exception as e:
            self._log(f'  Could not select {selector}: {e}')
        return False
    
    def _click(self, selector):
        """Click an element."""
        try:
            el = self.page.locator(selector)
            if el.count() > 0 and el.first.is_visible():
                el.first.click()
                return True
        except:
            pass
        return False
    
    # --------------------------------------------------------
    # Stripe Checkout Flow
    # --------------------------------------------------------
    
    def detect_stripe_checkout(self):
        """Check if current page is a Stripe hosted checkout."""
        url = self.page.url
        return 'checkout.stripe.com' in url or 'pay.stripe.com' in url
    
    def wait_for_checkout_ready(self, timeout=15):
        """Wait for checkout form to be interactive."""
        start = time.time()
        while time.time() - start < timeout:
            # Check if email field exists
            has_email = self.page.locator('#email').count() > 0
            if has_email:
                return True
            self.page.wait_for_timeout(500)
        return False
    
    def fill_email(self):
        """Fill email and wait for form to expand."""
        self._fill('#email', self.email)
        self.page.wait_for_timeout(2000)
        
        # Stripe may show a "Link" (express checkout) prompt after email
        # Dismiss it if present
        self.page.evaluate("""() => {
            // Click away from Link popup
            const overlay = document.querySelector('[data-testid="link-authentication-dismiss"]');
            if (overlay) overlay.click();
        }""")
        self.page.wait_for_timeout(500)
    
    def fill_card(self):
        """Fill card details. Stripe hosted checkout has these as plain inputs."""
        self._fill('#cardNumber', self.card['number'])
        self._fill('#cardExpiry', self.card['exp'])
        self._fill('#cardCvc', self.card['cvv'])
        self._fill('#billingName', self.billing_name)
    
    def fill_billing_address(self):
        """Fill billing address fields (appear if merchant requires them)."""
        self._select('#billingCountry', self.shipping.get('country', 'US'))
        self._fill('#billingPostalCode', self.shipping.get('zip', ''))
        self._fill('#billingAddressLine1', self.shipping.get('address1', ''))
        self._fill('#billingAddressLine2', self.shipping.get('address2', ''))
        self._fill('#billingLocality', self.shipping.get('city', ''))
        
        # State can be input or select depending on country
        state = self.shipping.get('state', '')
        if state:
            if not self._select('#billingAdministrativeArea', state):
                self._fill('#billingAdministrativeArea', state)
    
    def fill_shipping_address(self):
        """Fill shipping address if separate from billing."""
        # Stripe uses shipping* prefixed fields when shipping is separate
        self._fill('#shippingName', f"{self.shipping.get('first_name', '')} {self.shipping.get('last_name', '')}".strip())
        self._select('#shippingCountry', self.shipping.get('country', 'US'))
        self._fill('#shippingAddressLine1', self.shipping.get('address1', ''))
        self._fill('#shippingAddressLine2', self.shipping.get('address2', ''))
        self._fill('#shippingLocality', self.shipping.get('city', ''))
        self._fill('#shippingPostalCode', self.shipping.get('zip', ''))
        
        state = self.shipping.get('state', '')
        if state:
            if not self._select('#shippingAdministrativeArea', state):
                self._fill('#shippingAdministrativeArea', state)
        
        if self.phone:
            self._fill('#phoneNumber', self.phone)
    
    def select_shipping_method(self, index=0):
        """Select shipping method if options are shown."""
        methods = self.page.locator('input[name="shippingRate"]')
        if methods.count() > index:
            methods.nth(index).click()
            self.page.wait_for_timeout(1000)
    
    def get_total(self):
        """Extract the total amount from the checkout page."""
        total = self.page.evaluate(r"""() => {
            // Stripe shows total in the submit button and/or summary
            const btn = document.querySelector('.SubmitButton');
            if (btn) {
                const match = btn.textContent.match(/[\$€£]([\d,.]+)/);
                if (match) return match[1].replace(',', '');
            }
            // Also check summary section
            const summary = document.querySelector('[data-testid="total-amount"]');
            if (summary) {
                const match = summary.textContent.match(/[\$€£]([\d,.]+)/);
                if (match) return match[1].replace(',', '');
            }
            return null;
        }""")
        return float(total) if total else None
    
    def submit(self):
        """Click the Pay/Submit button."""
        # Try multiple selectors
        clicked = (
            self._click('button.SubmitButton') or
            self._click('button[data-testid="hosted-payment-submit-button"]') or
            self._click('button[type="submit"]')
        )
        if clicked:
            self.page.wait_for_timeout(10000)
        return clicked
    
    def check_success(self):
        """Check if payment was successful."""
        url = self.page.url
        text = self.page.inner_text('body')[:1000].lower()
        
        success = (
            'success' in url or
            'return_url' in url or
            'thank' in text or
            'payment successful' in text or
            'order confirmed' in text or
            'receipt' in text
        )
        
        return success
    
    def check_error(self):
        """Check for payment errors on the page."""
        error = self.page.evaluate("""() => {
            const err = document.querySelector('[data-testid="payment-error"]') ||
                       document.querySelector('.ErrorMessage') ||
                       document.querySelector('[role="alert"]');
            return err ? err.textContent.trim() : null;
        }""")
        return error
    
    # --------------------------------------------------------
    # Main Flow
    # --------------------------------------------------------
    
    def complete(self, checkout_url, dry_run=False):
        """
        Complete a Stripe hosted checkout.
        
        Args:
            checkout_url: URL starting with checkout.stripe.com or pay.stripe.com,
                         or a merchant URL that redirects to Stripe checkout
            dry_run: if True, fill everything but don't click Pay
            
        Returns:
            dict with success status, total, screenshots, timing
        """
        from playwright.sync_api import sync_playwright
        
        subprocess.run(['pkill', '-9', '-f', 'Brave'], capture_output=True)
        time.sleep(1)
        
        self.start_time = time.time()
        
        with sync_playwright() as p:
            self.browser = p.chromium.launch(
                executable_path=BRAVE_PATH, headless=False,
                args=BRAVE_ARGS, ignore_default_args=['--enable-automation']
            )
            ctx = self.browser.new_context()
            self.page = ctx.new_page()
            self.page.set_default_timeout(15000)
            
            try:
                return self._run_flow(checkout_url, dry_run)
            except Exception as e:
                self._screenshot('error')
                self._log(f'ERROR: {e}')
                return {
                    'success': False, 'error': str(e),
                    'screenshots': self.screenshots, 'elapsed': self._elapsed()
                }
            finally:
                self.browser.close()
    
    def _run_flow(self, checkout_url, dry_run):
        """Execute the Stripe checkout flow."""
        
        # Step 1: Navigate to checkout
        self._log(f'Navigating to {checkout_url[:80]}...')
        self.page.goto(checkout_url, wait_until='domcontentloaded', timeout=20000)
        self.page.wait_for_timeout(5000)
        
        # Step 2: Verify we're on Stripe checkout
        if not self.detect_stripe_checkout():
            # Might be a merchant page that redirects — wait
            self._log(f'Not on Stripe checkout yet. URL: {self.page.url[:80]}')
            self.page.wait_for_timeout(5000)
            if not self.detect_stripe_checkout():
                return {
                    'success': False,
                    'error': f'Not a Stripe checkout page: {self.page.url}',
                    'screenshots': self.screenshots, 'elapsed': self._elapsed()
                }
        
        self._log('On Stripe checkout')
        
        # Step 3: Wait for form
        if not self.wait_for_checkout_ready():
            self._screenshot('not-ready')
            return {
                'success': False, 'error': 'Checkout form did not load',
                'screenshots': self.screenshots, 'elapsed': self._elapsed()
            }
        
        # Step 4: Fill email
        self._log('Filling email')
        self.fill_email()
        
        # Step 5: Fill shipping if present
        shipping_present = self.page.locator('#shippingName, #shippingAddressLine1').count() > 0
        if shipping_present:
            self._log('Filling shipping address')
            self.fill_shipping_address()
            
            # Select shipping method if shown
            self.select_shipping_method(0)
        
        # Step 6: Fill card details
        self._log('Filling card details')
        self.fill_card()
        
        # Step 7: Fill billing address if present
        billing_present = self.page.locator('#billingAddressLine1').count() > 0
        if billing_present:
            self._log('Filling billing address')
            self.fill_billing_address()
        else:
            # At minimum, fill ZIP and country
            self._fill('#billingPostalCode', self.shipping.get('zip', '10014'))
            self._select('#billingCountry', 'US')
        
        self.page.wait_for_timeout(1000)
        self._screenshot('filled')
        
        # Step 8: Get total
        total = self.get_total()
        if total:
            self._log(f'Total: ${total:.2f}')
        
        # Step 9: Check for errors before submitting
        error = self.check_error()
        if error:
            self._log(f'Error before submit: {error}')
            return {
                'success': False, 'error': error, 'total': total,
                'screenshots': self.screenshots, 'elapsed': self._elapsed()
            }
        
        if dry_run:
            self._screenshot('dry-run')
            self._log('DRY RUN — not submitting')
            return {
                'success': True, 'dry_run': True, 'total': total,
                'screenshots': self.screenshots, 'elapsed': self._elapsed()
            }
        
        # Step 10: Submit
        self._log('Submitting payment...')
        self.submit()
        
        # Step 11: Check result
        self._screenshot('result')
        
        error = self.check_error()
        if error:
            self._log(f'Payment error: {error}')
            return {
                'success': False, 'error': error, 'total': total,
                'screenshots': self.screenshots, 'elapsed': self._elapsed()
            }
        
        success = self.check_success()
        self._log(f'{"✅ Payment successful!" if success else "⚠️ Unclear result — check screenshots"}')
        
        return {
            'success': success,
            'total': total,
            'url': self.page.url,
            'screenshots': self.screenshots,
            'elapsed': self._elapsed()
        }


# ============================================================
# Convenience: Navigate merchant site → Stripe checkout
# ============================================================

def merchant_to_stripe_checkout(page, merchant_url, add_to_cart_fn=None):
    """
    Helper to navigate a merchant's site and reach Stripe checkout.
    
    Many merchants have a "Buy" button that creates a Stripe Checkout Session
    and redirects. This helper waits for the redirect.
    
    Args:
        page: Playwright page object
        merchant_url: URL to start at
        add_to_cart_fn: optional callback(page) to add items to cart
    
    Returns:
        Stripe checkout URL or None
    """
    page.goto(merchant_url, wait_until='domcontentloaded', timeout=15000)
    page.wait_for_timeout(3000)
    
    if add_to_cart_fn:
        add_to_cart_fn(page)
    
    # Wait for redirect to Stripe
    for _ in range(20):
        if 'checkout.stripe.com' in page.url:
            return page.url
        page.wait_for_timeout(1000)
    
    return None


# ============================================================
# CLI
# ============================================================

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Stripe hosted checkout')
    parser.add_argument('--url', required=True, help='Stripe checkout URL')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    
    card = {
        'number': '4242424242424242',
        'exp': '12/30',
        'cvv': '123',
        'name': 'Wren Cole'
    }
    
    shipping = {
        'first_name': 'Harrison',
        'last_name': 'Friedes',
        'address1': '224 West 4th Street',
        'city': 'New York',
        'state': 'NY',
        'zip': '10014',
        'country': 'US'
    }
    
    checkout = StripeHostedCheckout(
        card=card,
        email='wrencole.nyc@gmail.com',
        shipping_address=shipping
    )
    
    result = checkout.complete(args.url, dry_run=args.dry_run)
    print(json.dumps(result, indent=2))
