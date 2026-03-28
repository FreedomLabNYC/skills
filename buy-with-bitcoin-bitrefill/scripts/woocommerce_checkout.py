#!/usr/bin/env python3
"""
WooCommerce Checkout Module — for WordPress/WooCommerce stores

WooCommerce powers ~20% of e-commerce. Field IDs are hardcoded in WooCommerce core,
making them consistent across stores regardless of WordPress theme.

Payment gateway support:
  - Braintree/PayPal: Card iframes ARE fillable ✅
  - Stripe Elements: Card iframes are BLOCKED by Stripe ⚠️
    (For Stripe-gateway WooCommerce, we fill shipping/billing but payment
     may need manual intervention or a different approach)
  - Direct bank/COD: No card fields needed

Usage:
    from woocommerce_checkout import WooCommerceCheckout
    
    checkout = WooCommerceCheckout(
        store_url='https://example-store.com',
        billing={...},
        card={'number': '...', 'exp_month': '01', 'exp_year': '30', 'cvv': '...', 'name': '...'},
        email='wrencole.nyc@gmail.com'
    )
    result = checkout.run(product_url='/product/example/', quantity=1)
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


class WooCommerceCheckout:
    """
    WooCommerce checkout handler.
    
    WooCommerce field IDs (from core templates/checkout/form-billing.php):
        #billing_first_name, #billing_last_name, #billing_company
        #billing_country (select, value="US")
        #billing_address_1, #billing_address_2
        #billing_city, #billing_state (select, value="NY")
        #billing_postcode, #billing_phone, #billing_email
        
        #shipping_first_name through #shipping_postcode (if different)
        #ship-to-different-address-checkbox
        
        #place_order — submit button
        input[name="payment_method"] — payment gateway radio buttons
    
    Payment gateways:
        Stripe: #wc-stripe-card-element or .__PrivateStripeElement iframe
        Braintree: iframe#braintree-hosted-field-number etc.
        PayPal: redirects to PayPal
    """
    
    def __init__(self, store_url, billing, card, email,
                 shipping=None, payment_method='stripe'):
        """
        Args:
            store_url: base URL (e.g., 'https://store.example.com')
            billing: dict with first_name, last_name, company, country, 
                    address1, address2, city, state, zip, phone
            card: dict with number, exp_month, exp_year, cvv, name
            email: buyer email
            shipping: dict (same as billing) or None to use billing address
            payment_method: 'stripe', 'braintree', 'paypal', 'cod'
        """
        self.store_url = store_url.rstrip('/')
        self.billing = billing
        self.shipping = shipping
        self.card = card
        self.email = email
        self.payment_method = payment_method
        
        self.page = None
        self.browser = None
        self.screenshots = []
        self.start_time = None
    
    def _screenshot(self, label):
        Path(SCREENSHOT_DIR).mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d-%H%M%S')
        path = os.path.join(SCREENSHOT_DIR, f'{ts}-woo-{label}.png')
        try:
            self.page.screenshot(path=path, full_page=False)
            self.screenshots.append(path)
        except:
            pass
        return path
    
    def _elapsed(self):
        return f'{time.time() - self.start_time:.1f}s'
    
    def _log(self, msg):
        print(f'[WOO] [{self._elapsed()}] {msg}')
    
    def _fill(self, selector, value):
        if not value:
            return False
        try:
            el = self.page.locator(selector)
            if el.count() > 0 and el.first.is_visible():
                el.first.fill(str(value))
                self.page.wait_for_timeout(200)
                return True
        except Exception as e:
            self._log(f'  Could not fill {selector}: {e}')
        return False
    
    def _select(self, selector, value):
        if not value:
            return False
        try:
            el = self.page.locator(selector)
            if el.count() > 0 and el.first.is_visible():
                el.first.select_option(value=value)
                self.page.wait_for_timeout(300)
                return True
        except:
            pass
        # WooCommerce sometimes uses Select2 dropdowns
        try:
            # Click the Select2 container to open it
            container = self.page.locator(f'{selector}_field .select2-selection')
            if container.count() > 0:
                container.click()
                self.page.wait_for_timeout(500)
                # Type in the search box
                search = self.page.locator('.select2-search__field')
                if search.count() > 0:
                    search.fill(value)
                    self.page.wait_for_timeout(500)
                    search.press('Enter')
                    self.page.wait_for_timeout(300)
                    return True
        except Exception as e:
            self._log(f'  Could not select {selector} (Select2): {e}')
        return False
    
    # --------------------------------------------------------
    # Add to Cart
    # --------------------------------------------------------
    
    def add_to_cart_ajax(self, product_id, quantity=1):
        """Add to cart via WooCommerce AJAX API."""
        result = self.page.evaluate(f"""
            fetch('{self.store_url}/?wc-ajax=add_to_cart', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
                body: 'product_id={product_id}&quantity={quantity}'
            }}).then(r => r.json()).catch(e => ({{error: e.message}}))
        """)
        return result
    
    def add_to_cart_form(self, product_url, quantity=1):
        """Add to cart by navigating to product page and clicking Add to Cart."""
        url = product_url if product_url.startswith('http') else f'{self.store_url}{product_url}'
        self.page.goto(url, wait_until='domcontentloaded', timeout=15000)
        self.page.wait_for_timeout(3000)
        
        # Set quantity
        qty_input = self.page.locator('input.qty, input[name="quantity"]')
        if qty_input.count() > 0:
            qty_input.first.fill(str(quantity))
        
        # Click Add to Cart
        self.page.locator('button.single_add_to_cart_button, button[name="add-to-cart"]').first.click()
        self.page.wait_for_timeout(3000)
    
    # --------------------------------------------------------
    # Billing & Shipping
    # --------------------------------------------------------
    
    def fill_billing(self):
        """Fill all billing fields using WooCommerce's standard IDs."""
        b = self.billing
        self._fill('#billing_first_name', b.get('first_name', ''))
        self._fill('#billing_last_name', b.get('last_name', ''))
        self._fill('#billing_company', b.get('company', ''))
        self._select('#billing_country', b.get('country', 'US'))
        self.page.wait_for_timeout(500)  # Country change may trigger state reload
        self._fill('#billing_address_1', b.get('address1', ''))
        self._fill('#billing_address_2', b.get('address2', ''))
        self._fill('#billing_city', b.get('city', ''))
        self._select('#billing_state', b.get('state', ''))
        self._fill('#billing_postcode', b.get('zip', ''))
        self._fill('#billing_phone', b.get('phone', ''))
        self._fill('#billing_email', self.email)
    
    def fill_shipping(self):
        """Fill shipping fields if different from billing."""
        if not self.shipping:
            return
        
        # Check the "ship to different address" checkbox
        checkbox = self.page.locator('#ship-to-different-address-checkbox')
        if checkbox.count() > 0 and not checkbox.is_checked():
            checkbox.click()
            self.page.wait_for_timeout(1000)
        
        s = self.shipping
        self._fill('#shipping_first_name', s.get('first_name', ''))
        self._fill('#shipping_last_name', s.get('last_name', ''))
        self._fill('#shipping_company', s.get('company', ''))
        self._select('#shipping_country', s.get('country', 'US'))
        self.page.wait_for_timeout(500)
        self._fill('#shipping_address_1', s.get('address1', ''))
        self._fill('#shipping_address_2', s.get('address2', ''))
        self._fill('#shipping_city', s.get('city', ''))
        self._select('#shipping_state', s.get('state', ''))
        self._fill('#shipping_postcode', s.get('zip', ''))
    
    # --------------------------------------------------------
    # Payment
    # --------------------------------------------------------
    
    def select_payment_method(self):
        """Select the payment method radio button."""
        selector = f'input[name="payment_method"][value="{self.payment_method}"]'
        el = self.page.locator(selector)
        if el.count() > 0:
            el.click()
            self.page.wait_for_timeout(1000)
            self._log(f'Selected payment: {self.payment_method}')
            return True
        
        # Try common aliases
        aliases = {
            'stripe': ['stripe', 'woocommerce_payments', 'stripe_cc'],
            'braintree': ['braintree_credit_card', 'paypal_credit_card'],
            'paypal': ['ppcp-gateway', 'paypal', 'braintree_paypal'],
        }
        for alias in aliases.get(self.payment_method, []):
            selector = f'input[name="payment_method"][value="{alias}"]'
            el = self.page.locator(selector)
            if el.count() > 0:
                el.click()
                self.page.wait_for_timeout(1000)
                self._log(f'Selected payment: {alias}')
                return True
        
        self._log(f'WARNING: Could not find payment method {self.payment_method}')
        # List available methods
        methods = self.page.evaluate("""() => {
            return Array.from(document.querySelectorAll('input[name="payment_method"]'))
                .map(el => el.value);
        }""")
        self._log(f'Available methods: {methods}')
        return False
    
    def fill_card_braintree(self):
        """Fill card details in Braintree hosted fields (fillable iframes)."""
        iframe_map = {
            'iframe#braintree-hosted-field-number': self.card['number'],
            'iframe#braintree-hosted-field-expirationDate': f"{self.card['exp_month']}/{self.card['exp_year']}",
            'iframe#braintree-hosted-field-cvv': self.card['cvv'],
        }
        
        for iframe_sel, value in iframe_map.items():
            try:
                frame = self.page.frame_locator(iframe_sel)
                inp = frame.locator('input')
                inp.fill(value)
                self.page.wait_for_timeout(300)
            except Exception as e:
                self._log(f'  Braintree iframe fill error ({iframe_sel}): {e}')
        
        # Cardholder name (sometimes outside iframe)
        self._fill('#braintree-hosted-field-cardholderName input', self.card.get('name', ''))
    
    def fill_card_stripe(self):
        """
        Attempt to fill Stripe card fields in WooCommerce.
        
        ⚠️ Stripe Elements blocks programmatic filling of its iframes.
        This method tries anyway, and reports if it fails.
        """
        # Try the older Card Element
        stripe_iframe = self.page.locator('.__PrivateStripeElement iframe')
        if stripe_iframe.count() > 0:
            try:
                frame = self.page.frame_locator('.__PrivateStripeElement iframe').first
                inp = frame.locator('input[name="cardnumber"]')
                inp.fill(self.card['number'])
                self._log('Stripe Card Element: filled (old style)')
                return True
            except Exception as e:
                self._log(f'⚠️ Stripe Card Element blocked: {e}')
                self._log('Stripe Elements prevents programmatic card entry.')
                self._log('Options: use Stripe-hosted checkout, or manual intervention.')
                return False
        
        # Try the newer Payment Element
        payment_el = self.page.locator('#wc-stripe-payment-element iframe, [data-elements-stable-field-name] iframe')
        if payment_el.count() > 0:
            self._log('⚠️ Stripe Payment Element detected — cannot fill programmatically')
            return False
        
        self._log('No Stripe card fields found')
        return False
    
    # --------------------------------------------------------
    # Order
    # --------------------------------------------------------
    
    def get_order_total(self):
        """Get order total from the checkout page."""
        total = self.page.evaluate(r"""() => {
            const el = document.querySelector('.order-total .amount, .order-total bdi');
            if (el) {
                const match = el.textContent.match(/[\d,.]+/);
                return match ? match[0].replace(',', '') : null;
            }
            return null;
        }""")
        return float(total) if total else None
    
    def place_order(self):
        """Click Place Order button."""
        self.page.locator('#place_order').click()
        self.page.wait_for_timeout(10000)
    
    def check_confirmation(self):
        """Check if order was placed successfully."""
        text = self.page.inner_text('body')[:2000].lower()
        url = self.page.url.lower()
        
        confirmed = (
            'order-received' in url or
            'thank you' in text or
            'order received' in text or
            'order has been received' in text
        )
        
        order_number = None
        match = re.search(r'order\s*(?:number|#)[:\s]*(\d+)', text)
        if match:
            order_number = match.group(1)
        
        return confirmed, order_number
    
    def detect_gateway(self):
        """Auto-detect which payment gateway the store uses."""
        gateways = self.page.evaluate("""() => {
            const methods = document.querySelectorAll('input[name="payment_method"]');
            return Array.from(methods).map(m => ({
                value: m.value,
                label: m.closest('.wc_payment_method')?.querySelector('label')?.textContent?.trim() || m.value,
                checked: m.checked
            }));
        }""")
        self._log(f'Available payment gateways: {json.dumps(gateways)}')
        return gateways
    
    # --------------------------------------------------------
    # Main Flow
    # --------------------------------------------------------
    
    def run(self, product_url=None, product_id=None, quantity=1, dry_run=False):
        """
        Execute full WooCommerce checkout.
        
        Provide either product_url (navigates to page) or product_id (AJAX add).
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
                return self._run_flow(product_url, product_id, quantity, dry_run)
            except Exception as e:
                self._screenshot('error')
                self._log(f'ERROR: {e}')
                return {
                    'success': False, 'error': str(e),
                    'screenshots': self.screenshots, 'elapsed': self._elapsed()
                }
            finally:
                self.browser.close()
    
    def _run_flow(self, product_url, product_id, quantity, dry_run):
        
        # Step 1: Add to cart
        if product_url:
            self._log(f'Adding to cart via product page: {product_url}')
            self.add_to_cart_form(product_url, quantity)
        elif product_id:
            self._log(f'Adding to cart via AJAX: product {product_id}')
            self.page.goto(self.store_url, wait_until='domcontentloaded', timeout=15000)
            self.page.wait_for_timeout(2000)
            self.add_to_cart_ajax(product_id, quantity)
        
        # Step 2: Go to checkout
        self._log('Navigating to checkout')
        self.page.goto(f'{self.store_url}/checkout/', wait_until='domcontentloaded', timeout=15000)
        self.page.wait_for_timeout(5000)
        
        # Step 3: Detect payment gateway
        gateways = self.detect_gateway()
        
        # Auto-select best gateway
        gateway_values = [g['value'] for g in gateways]
        if self.payment_method not in gateway_values:
            # Pick first available
            if gateways:
                self.payment_method = gateways[0]['value']
                self._log(f'Using first available gateway: {self.payment_method}')
        
        # Step 4: Fill billing
        self._log('Filling billing info')
        self.fill_billing()
        
        # Step 5: Fill shipping if different
        if self.shipping:
            self._log('Filling separate shipping address')
            self.fill_shipping()
        
        # Step 6: Select payment method
        self.select_payment_method()
        self.page.wait_for_timeout(2000)
        
        # Step 7: Fill card details (gateway-specific)
        card_filled = False
        if 'braintree' in self.payment_method:
            self._log('Filling Braintree card fields')
            self.fill_card_braintree()
            card_filled = True
        elif 'stripe' in self.payment_method or 'woocommerce_payments' in self.payment_method:
            self._log('Attempting Stripe card fields')
            card_filled = self.fill_card_stripe()
            if not card_filled:
                self._screenshot('stripe-blocked')
                self._log('⚠️ Stripe card fields blocked — cannot complete payment programmatically')
                return {
                    'success': False,
                    'error': 'stripe_elements_blocked',
                    'message': 'Stripe Elements blocks programmatic card entry. '
                              'Consider using a store with Braintree or Shopify checkout instead.',
                    'screenshots': self.screenshots, 'elapsed': self._elapsed()
                }
        elif self.payment_method in ('cod', 'bacs', 'cheque'):
            self._log(f'No card needed for {self.payment_method}')
            card_filled = True
        
        self._screenshot('filled')
        
        # Step 8: Get total
        total = self.get_order_total()
        if total:
            self._log(f'Order total: ${total:.2f}')
        
        if dry_run:
            self._screenshot('dry-run')
            self._log('DRY RUN — not placing order')
            return {
                'success': True, 'dry_run': True, 'total': total,
                'gateways': gateways,
                'screenshots': self.screenshots, 'elapsed': self._elapsed()
            }
        
        # Step 9: Place order
        self._log('Placing order...')
        self.place_order()
        
        # Step 10: Check result
        self._screenshot('result')
        confirmed, order_number = self.check_confirmation()
        
        if confirmed:
            self._log(f'✅ Order confirmed! #{order_number}')
        else:
            self._log('⚠️ Could not confirm order — check screenshots')
        
        return {
            'success': confirmed,
            'order_number': order_number,
            'total': total,
            'url': self.page.url,
            'screenshots': self.screenshots,
            'elapsed': self._elapsed()
        }


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='WooCommerce checkout')
    parser.add_argument('--store', required=True, help='Store URL')
    parser.add_argument('--product-url', help='Product page URL path')
    parser.add_argument('--product-id', type=int, help='Product ID for AJAX add')
    parser.add_argument('--quantity', default=1, type=int)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    
    billing = {
        'first_name': 'Harrison', 'last_name': 'Friedes',
        'company': 'Fat Cat Fab Lab',
        'country': 'US', 'address1': '224 West 4th Street',
        'city': 'New York', 'state': 'NY', 'zip': '10014', 'phone': ''
    }
    
    card = {
        'number': '4111111111111111',
        'exp_month': '12', 'exp_year': '30',
        'cvv': '123', 'name': 'Wren Cole'
    }
    
    checkout = WooCommerceCheckout(
        store_url=args.store, billing=billing, card=card,
        email='wrencole.nyc@gmail.com'
    )
    
    result = checkout.run(
        product_url=args.product_url, product_id=args.product_id,
        quantity=args.quantity, dry_run=args.dry_run
    )
    print(json.dumps(result, indent=2))
