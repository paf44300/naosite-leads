#!/usr/bin/env python3
"""
Google Maps Scraper v4.0 REAL - FINAL FIXED VERSION
Utilise Playwright pour l'extraction dynamique sur le site public de Google Maps.
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
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import logging

# Configuration du Proxy
PROXY_HOST = "p.webshare.io"
PROXY_PORT = "80"
PROXY_USER = "xftpfnvt"
PROXY_PASS = "yulnmnbiq66j"

class RealMapsScraper:
    def __init__(self, session_id=None, debug=False):
        self.session_id = session_id or f"maps_{int(time.time())}"
        self.debug = debug
        self.setup_logging()
        self.VALID_DEPARTMENTS = ['44', '35', '29', '56', '85', '49', '53']

    def setup_logging(self):
        level = logging.DEBUG if self.debug else logging.INFO
        logging.basicConfig(
            level=level,
            format=f'[{self.session_id}] %(levelname)s: %(message)s',
            stream=sys.stderr
        )
        self.logger = logging.getLogger(__name__)

    def normalize_phone(self, text_block):
        """Extrait et normalise un numéro de téléphone depuis un bloc de texte."""
        if not text_block:
            return None
        # Pattern pour trouver des numéros de téléphone français plus efficacement
        phone_pattern = r'(?:\+33|0)\s*[1-9](?:[\s.-]*\d{2}){4}'
        match = re.search(phone_pattern, text_block)
        if match:
            phone_digits = ''.join(filter(str.isdigit, match.group(0)))
            if phone_digits.startswith('0'):
                return '+33' + phone_digits[1:]
            if phone_digits.startswith('33'):
                return '+' + phone_digits
        return None

    def validate_department(self, address):
        """Valide le département à partir de l'adresse."""
        if not address:
            return None
        postal_match = re.search(r'\b(\d{5})\b', address)
        if postal_match:
            dept = postal_match.group(1)[:2]
            if dept in self.VALID_DEPARTMENTS:
                return dept
        return None

    def scrape_with_playwright(self, query, city, limit=30, offset=0):
        """Scrape Google Maps en utilisant l'URL publique et des sélecteurs robustes."""
        results = []
        search_query = f"{query} {city}".strip()
        # **CHANGEMENT MAJEUR**: Utilisation de l'URL publique de Google Maps
        maps_url = f"https://www.google.com/maps/search/{quote_plus(search_query)}"

        with sync_playwright() as p:
            browser_args = [
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled'
            ]
            launch_options = {'headless': True, 'args': browser_args}
            if PROXY_USER and PROXY_PASS:
                launch_options['proxy'] = {
                    'server': f'http://{PROXY_HOST}:{PROXY_PORT}',
                    'username': PROXY_USER,
                    'password': PROXY_PASS
                }

            browser = p.chromium.launch(**launch_options)
            context = browser.new_context(
                locale='fr-FR',
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = context.new_page()

            try:
                self.logger.info(f"Navigating to public URL: {maps_url}")
                page.goto(maps_url, wait_until='networkidle', timeout=60000)

                # Gérer le formulaire de consentement de Google
                try:
                    consent_button = page.locator('button:has-text("Tout accepter")').first
                    if consent_button.is_visible():
                        self.logger.info("Consent form found. Clicking 'Accept all'.")
                        consent_button.click()
                        page.wait_for_load_state('networkidle', timeout=10000)
                except PlaywrightTimeoutError:
                    self.logger.info("Consent form did not require interaction or timed out.")
                except Exception:
                    self.logger.info("No consent form found, continuing.")

                # Attendre que le conteneur des résultats soit visible
                results_feed_selector = 'div[role="feed"]'
                page.wait_for_selector(results_feed_selector, state='visible', timeout=20000)
                self.logger.info("Results feed is visible. Starting scroll.")

                # Scroll pour charger tous les résultats
                for i in range(5):
                    page.locator(results_feed_selector).evaluate("node => node.scrollTop = node.scrollHeight")
                    time.sleep(random.uniform(1.5, 2.5))
                    self.logger.debug(f"Scroll {i+1}/5 complete.")

                # Sélecteur robuste pour les fiches d'entreprise
                business_cards = page.locator(f'{results_feed_selector} > div[role="article"]').all()
                self.logger.info(f"Found {len(business_cards)} business cards.")

                for card in business_cards[offset:offset+limit]:
                    try:
                        card_text = card.inner_text()
                        
                        # Filtre crucial : ignorer les entreprises avec un site web
                        if "site web" in card_text.lower():
                            self.logger.debug(f"Skipping card, contains 'Site Web': {card_text[:100]}")
                            continue

                        address = None
                        # Pattern pour trouver une adresse complète avec code postal
                        address_match = re.search(r'([\d\w\s,.-]+? \d{5} [\w\s.-]+)', card_text)
                        if address_match:
                            address = address_match.group(1).strip()
                        
                        # Validation par département
                        department = self.validate_department(address)
                        if not department:
                            self.logger.debug(f"Skipping card, department not in valid list or address not found in: {card_text[:100]}")
                            continue
                        
                        name = card.locator('a[aria-label]').first.get_attribute('aria-label')
                        phone = self.normalize_phone(card_text)

                        if not name:
                            continue

                        result = {
                            'name': name.strip(),
                            'phone': phone,
                            'address': address,
                            'city': city,
                            'department': department,
                            'activity': query.title(),
                            'source': 'Maps_public',
                            'website': None,
                            'email': None,
                            'extracted_from': 'real_html_v3_public',
                            'geo_validated': True,
                            'scraped_at': datetime.now().isoformat(),
                            'session_id': self.session_id
                        }
                        results.append(result)
                        self.logger.info(f"✅ Extracted: {name}")

                    except Exception as e:
                        self.logger.warning(f"Could not process a business card. Error: {e}")

            except PlaywrightTimeoutError as e:
                self.logger.error(f"Timeout Error during page navigation or waiting for selector: {e}")
            except Exception as e:
                self.logger.error(f"A critical error occurred in Playwright: {e}")
            finally:
                page.screenshot(path='final_state.png')
                self.logger.info("Screenshot of final state saved to 'final_state.png'.")
                browser.close()

        return results

def main():
    parser = argparse.ArgumentParser(description="Google Maps Scraper v4.0 - FINAL")
    parser.add_argument("query", help="Profession/activité à rechercher")
    parser.add_argument("--city", required=True, help="Code postal ou ville")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--session-id", help="Session ID")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    scraper = RealMapsScraper(
        session_id=args.session_id,
        debug=args.debug
    )
    
    results = scraper.scrape_with_playwright(
        query=args.query,
        city=args.city,
        limit=args.limit,
        offset=args.offset
    )
    
    for result in results:
        print(json.dumps(result, ensure_ascii=False))
    
    if len(results) > 0:
        logging.info(f"SUCCESS: {len(results)} results extracted.")
    else:
        logging.warning("PROCESS FINISHED: 0 results were extracted.")

if __name__ == "__main__":
    main()
