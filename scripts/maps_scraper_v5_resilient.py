#!/usr/bin/env python3
"""
Google Maps Scraper v5.0 - Resilient Humanoid Strategy
Utilise playwright-stealth et des techniques de navigation avancées pour une fiabilité maximale.
"""

import os
import sys
import json
import time
import random
import argparse
import re
from datetime import datetime
from urllib.parse import quote_plus

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
    from playwright_stealth import stealth_sync
except ImportError:
    print("Erreur: Assurez-vous d'avoir installé playwright et playwright-stealth.", file=sys.stderr)
    sys.exit(1)

# --- Configuration ---
PROXY_HOST = "p.webshare.io"
PROXY_PORT = "80"
PROXY_USER = "xftpfnvt"
PROXY_PASS = "yulnmnbiq66j"

class ResilientMapsScraper:
    def __init__(self, session_id=None, debug=False):
        self.session_id = session_id or f"maps_resilient_{int(time.time())}"
        self.debug = debug
        self.setup_logging()
        self.VALID_DEPARTMENTS = ['44', '35', '29', '56', '85', '49', '53']

    def setup_logging(self):
        level = logging.DEBUG if self.debug else logging.INFO
        logging.basicConfig(level=level, format=f'[{self.session_id}] %(levelname)s: %(message)s', stream=sys.stderr)
        self.logger = logging.getLogger(__name__)

    def _get_browser_context(self, playwright_instance):
        browser_args = [
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-blink-features=AutomationControlled'
        ]
        launch_options = {'headless': True, 'args': browser_args}
        if PROXY_USER and PROXY_PASS:
            launch_options['proxy'] = {'server': f'http://{PROXY_HOST}:{PROXY_PORT}', 'username': PROXY_USER, 'password': PROXY_PASS}

        browser = playwright_instance.chromium.launch(**launch_options)
        context = browser.new_context(
            locale='fr-FR',
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            geolocation={'latitude': 47.2184, 'longitude': -1.5536} # Nantes
        )
        stealth_sync(context) # Appliquer les patches anti-détection
        return browser, context

    def normalize_phone(self, text_block):
        if not text_block: return None
        match = re.search(r'(?:\+33|0)\s*[1-9](?:[\s.-]*\d{2}){4}', text_block)
        if match:
            digits = ''.join(filter(str.isdigit, match.group(0)))
            return '+33' + digits[1:] if digits.startswith('0') else '+' + digits
        return None

    def validate_department(self, address):
        if not address: return None
        match = re.search(r'\b(\d{5})\b', address)
        return match.group(1)[:2] if match and match.group(1)[:2] in self.VALID_DEPARTMENTS else None

    def scrape(self, query, city, limit=30, offset=0):
        results = []
        search_query = f"{query} à {city}".strip()
        search_url = f"https://www.google.com/maps/search/{quote_plus(search_query)}"

        with sync_playwright() as p:
            browser, context = self._get_browser_context(p)
            page = context.new_page()
            try:
                # Étape 1: "Chauffer" la session en visitant la page de base
                self.logger.info("Warming up session by visiting Google base...")
                page.goto("https://www.google.com/maps/search/plombier+29200", wait_until='networkidle', timeout=60000)

                # Étape 2: Accepter les cookies de manière "humaine"
                consent_button = page.locator('button:has-text("Tout accepter")').first
                if consent_button.is_visible(timeout=10000):
                    bounding_box = consent_button.bounding_box()
                    if bounding_box:
                        page.mouse.move(bounding_box['x'] + bounding_box['width'] / 2, bounding_box['y'] + bounding_box['height'] / 2)
                        time.sleep(random.uniform(0.1, 0.3))
                        consent_button.click()
                        self.logger.info("Consent form accepted.")
                        page.wait_for_load_state('networkidle', timeout=15000)
                
                # Étape 3: Effectuer la recherche réelle
                self.logger.info(f"Navigating to search URL: {search_url}")
                page.goto(search_url, wait_until='networkidle', timeout=60000)

                # Étape 4: Attendre et scroller le panneau de résultats
                feed_selector = 'div[role="feed"]'
                page.wait_for_selector(feed_selector, state='visible', timeout=20000)
                self.logger.info("Results feed visible. Scrolling to load all results.")
                
                for _ in range(7): # Plus de scrolls pour plus de résultats
                    page.locator(feed_selector).evaluate("node => node.scrollTop = node.scrollHeight")
                    time.sleep(random.uniform(2, 3.5))

                # Étape 5: Extraire les données
                cards = page.locator(f'{feed_selector} > div[role="article"]').all()
                self.logger.info(f"Found {len(cards)} business cards.")

                for card in cards[offset:offset+limit]:
                    card_text = card.inner_text()
                    if "site web" in card_text.lower():
                        continue

                    address_match = re.search(r'([\d\w\s,.-]+? \d{5} [\w\s.-]+)', card_text)
                    address = address_match.group(1).strip() if address_match else None
                    
                    department = self.validate_department(address)
                    if not department:
                        continue
                    
                    name_element = card.locator('a[aria-label]').first
                    name = name_element.get_attribute('aria-label').strip() if name_element else "N/A"
                    phone = self.normalize_phone(card_text)
                    
                    results.append({
                        'name': name,
                        'phone': phone,
                        'address': address,
                        'city': city,
                        'department': department,
                        'activity': query.title(),
                        'source': 'Maps_resilient',
                        'website': None,
                        'extracted_from': 'humanoid_v5',
                        'scraped_at': datetime.now().isoformat()
                    })
                    self.logger.info(f"✅ Extracted: {name}")

            except PlaywrightTimeoutError as e:
                self.logger.error(f"FATAL TIMEOUT: The page took too long to load or find a selector. This often means IP block or CAPTCHA. Error: {e}")
                page.screenshot(path='fatal_timeout_error.png')
            except Exception as e:
                self.logger.error(f"A critical error occurred: {e}")
                page.screenshot(path='critical_error.png')
            finally:
                self.logger.info(f"Scraping finished. Extracted {len(results)} results.")
                browser.close()
        
        return results

def main():
    parser = argparse.ArgumentParser(description="Google Maps Scraper v5 - Resilient Humanoid Strategy")
    # ... (les arguments restent les mêmes)
    parser.add_argument("query", help="Profession/activité à rechercher")
    parser.add_argument("--city", required=True, help="Code postal ou ville")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--session-id", help="Session ID")
    parser.add_argument("--debug", action="store_true")
    
    args = parser.parse_args()
    
    scraper = ResilientMapsScraper(session_id=args.session_id, debug=args.debug)
    results = scraper.scrape(query=args.query, city=args.city, limit=args.limit, offset=args.offset)
    
    for result in results:
        print(json.dumps(result, ensure_ascii=False))

    if len(results) == 0:
        sys.exit(1) # Quitter avec un code d'erreur si aucun résultat pour n8n

if __name__ == "__main__":
    main()
