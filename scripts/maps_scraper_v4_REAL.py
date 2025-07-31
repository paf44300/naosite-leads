#!/usr/bin/env python3
"""
Google Maps Scraper v4.0 REAL - FIXED VERSION
Utilise Playwright pour l'extraction dynamique
"""

import os
import sys
import json
import time
import random
import argparse
from datetime import datetime
from playwright.sync_api import sync_playwright
import logging

# Configuration
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
        level = logging.DEBUG if self.debug else logging.WARNING
        logging.basicConfig(
            level=level,
            format=f'[{self.session_id}] %(levelname)s: %(message)s',
            stream=sys.stderr
        )
        self.logger = logging.getLogger(__name__)
    
    def normalize_phone(self, phone):
        """Normalise le téléphone au format français"""
        if not phone:
            return None
        phone = ''.join(filter(str.isdigit, phone))
        if phone.startswith('33'): 
            phone = '+' + phone
        elif phone.startswith('0'): 
            phone = '+33' + phone[1:]
        elif len(phone) == 9: 
            phone = '+33' + phone
        return phone if len(phone) >= 10 else None
    
    def extract_city_from_address(self, address):
        """Extrait la ville de l'adresse"""
        if not address:
            return ""
        
        import re
        # Patterns pour extraire la ville
        patterns = [
            r'(\d{5})\s+([A-Z][a-zÀ-ÿ\s\-\']+)',  # 44000 Nantes
            r'([A-Z][a-zÀ-ÿ\s\-\']+),?\s+\d{5}',  # Nantes 44000
            r',\s*([A-Z][a-zÀ-ÿ\s\-\']+)(?:\s+\d{5})?$'  # ..., Nantes
        ]
        
        for pattern in patterns:
            match = re.search(pattern, address)
            if match:
                groups = match.groups()
                for group in groups:
                    if group and not group.isdigit() and len(group) > 2:
                        return group.strip()
        return ""
    
    def validate_department(self, address):
        """Valide le département depuis l'adresse"""
        if not address:
            return None
        
        import re
        postal_match = re.search(r'\b(\d{5})\b', address)
        if postal_match:
            postal_code = postal_match.group(1)
            dept = postal_code[:2]
            if dept in self.VALID_DEPARTMENTS:
                return dept
        return None
    
def scrape_with_playwright(self, query, city, limit=30, offset=0):
    """Scrape Google Maps avec Playwright"""
    results = []

    with sync_playwright() as p:
        # Configuration du navigateur
        browser_args = [
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-blink-features=AutomationControlled',
            '--disable-features=site-per-process'
        ]

        # Configuration proxy si disponible
        launch_options = {
            'headless': True,
            'args': browser_args
        }

        if PROXY_USER and PROXY_PASS:
            launch_options['proxy'] = {
                'server': f'http://{PROXY_HOST}:{PROXY_PORT}',
                'username': PROXY_USER,
                'password': PROXY_PASS
            }

        browser = p.chromium.launch(**launch_options)

        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='fr-FR',
            geolocation={'latitude': 47.2184, 'longitude': -1.5536}, # Coordonnées de Nantes pour pertinence
            permissions=['geolocation']
        )

        # Anti-détection
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        page = context.new_page()

        try:
            # Construction de l'URL de recherche publique
            search_query = f"{query} {city}".strip()
            maps_url = f"https://www.google.com/maps/search/{search_query.replace(' ', '+')}"

            self.logger.info(f"Loading: {maps_url}")

            # Charger la page
            page.goto(maps_url, wait_until='domcontentloaded', timeout=60000) # Timeout augmenté

            # Gérer le formulaire de consentement Google
            try:
                consent_button_xpath = '//button[.//span[contains(text(), "Tout accepter")]]'
                consent_button = page.query_selector(consent_button_xpath)
                if consent_button:
                    self.logger.info("Consent button found, clicking it.")
                    consent_button.click()
                    # Attendre que la page se recharge après le clic
                    page.wait_for_load_state('domcontentloaded', timeout=15000)
                else:
                    self.logger.info("Consent button not found, proceeding.")
            except Exception as e:
                self.logger.warning(f"Could not handle consent form: {e}")


            # Attendre le panneau latéral des résultats
            try:
                page.wait_for_selector('div[role="feed"]', timeout=20000)
            except Exception as e:
                self.logger.warning(f"Feed not found, the page structure might have changed or there are no results. Error: {e}")
                browser.close()
                return []


            # Scroll pour charger plus de résultats
            for _ in range(5): # Augmenté pour plus de résultats
                page.evaluate('document.querySelector("div[role=\\"feed\\"]")?.scrollBy(0, 5000)')
                time.sleep(random.uniform(1.5, 2.5))

            # Sélecteurs pour les business cards
            business_selectors = [
                'div[role="article"]'
            ]

            businesses = []
            for selector in business_selectors:
                elements = page.query_selector_all(selector)
                if elements:
                    businesses = elements
                    self.logger.info(f"Found {len(elements)} with selector: {selector}")
                    break

            # Extraire les données
            for i, business in enumerate(businesses[offset:offset+limit]):
                try:
                    full_text = business.inner_text()

                    # Extraction du nom
                    name = None
                    name_element = business.query_selector('.fontHeadlineSmall')
                    if name_element:
                        name = name_element.inner_text().strip()

                    if not name:
                        continue

                    # Vérifier l'absence de site web
                    if "Site Web" in full_text:
                         self.logger.debug(f"Skipping {name} - has website")
                         continue

                    # Extraction du téléphone
                    phone = self.normalize_phone(full_text)

                    # Extraction de l'adresse
                    address = None
                    address_match = re.search(r'([\d\w\s,.-]+? \d{5} [\w\s.-]+)', full_text)
                    if address_match:
                        address = address_match.group(1).strip()


                    # Validation du département
                    dept = self.validate_department(address) if address else None
                    if not dept:
                        self.logger.debug(f"Skipping {name} - invalid department")
                        continue

                    # Créer l'objet résultat
                    result = {
                        'name': name,
                        'phone': phone,
                        'address': address,
                        'city': self.extract_city_from_address(address),
                        'postal_code': dept + '000',  # Approximation
                        'department': dept,
                        'activity': query.title(),
                        'source': 'Maps',
                        'website': None,
                        'email': None,
                        'extracted_from': 'real_html',
                        'geo_validated': True,
                        'scraped_at': datetime.now().isoformat(),
                        'session_id': self.session_id
                    }

                    results.append(result)
                    self.logger.info(f"✅ Extracted: {name}")

                except Exception as e:
                    self.logger.debug(f"Error extracting business: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Playwright error: {e}")
            page.screenshot(path='error_screenshot.png')
            self.logger.error("Screenshot saved to error_screenshot.png")
        finally:
            browser.close()

    return results

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("query", help="Profession/activité à rechercher")
    parser.add_argument("--city", required=True, help="Code postal ou ville")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--session-id", help="Session ID")
    parser.add_argument("--debug", action="store_true")
    
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
    
    # Output pour n8n
    for result in results:
        print(json.dumps(result, ensure_ascii=False))
    
    if args.debug:
        logging.info(f"SUCCESS: {len(results)} results extracted")

if __name__ == "__main__":
    main()
