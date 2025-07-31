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
import re
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
        # This regex is more robust for finding phone numbers within a block of text
        phone_match = re.search(r'(\+33[\s\d.-]{9,12}|0[1-9](?:[\s\d.-]{8}))', phone)
        if not phone_match:
            return None
        
        phone_digits = ''.join(filter(str.isdigit, phone_match.group(1)))
        
        if phone_digits.startswith('33'):
            return '+' + phone_digits
        if phone_digits.startswith('0'):
            return '+33' + phone_digits[1:]
        return None

    def extract_city_from_address(self, address):
        """Extrait la ville de l'adresse"""
        if not address:
            return ""
        
        # This pattern looks for a postal code followed by a city name
        match = re.search(r'\b(\d{5})\s+([A-Z][a-zÀ-ÿ\s\-\']+)', address)
        if match:
            return match.group(2).strip()
        return ""
    
    def validate_department(self, address):
        """Valide le département depuis l'adresse"""
        if not address:
            return None
        
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
            browser_args = [
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled',
                '--disable-features=site-per-process'
            ]
            
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
                geolocation={'latitude': 48.3904, 'longitude': -4.4861}, # Coords for Brest (29)
                permissions=['geolocation']
            )
            
            context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
            
            page = context.new_page()
            
            try:
                search_query = f"{query} {city}".strip()
                # Using the public Google Maps URL
                maps_url = f"https://www.google.com/maps/search/{search_query.replace(' ', '+')}"
                
                self.logger.info(f"Loading: {maps_url}")
                
                page.goto(maps_url, wait_until='domcontentloaded', timeout=60000)
                
                # Handle Google's consent form
                try:
                    consent_button = page.query_selector('//button[.//div[contains(text(), "Tout accepter")]]')
                    if consent_button:
                        self.logger.info("Consent button found, clicking it.")
                        consent_button.click()
                        page.wait_for_load_state('networkidle', timeout=10000)
                except Exception as e:
                    self.logger.warning(f"Could not handle consent form: {e}")

                # Wait for the main results feed to appear
                try:
                    page.wait_for_selector('div[role="feed"]', timeout=20000)
                except Exception:
                    self.logger.error("Results feed not found. Page might not have loaded correctly or no results were found.")
                    browser.close()
                    return []
                
                # Scroll to load more results
                for _ in range(5):
                    page.evaluate('document.querySelector("div[role=\\"feed\\"]")?.scrollBy(0, 5000)')
                    time.sleep(random.uniform(1.5, 2.5))
                
                businesses = page.query_selector_all('div[role="article"]')
                self.logger.info(f"Found {len(businesses)} potential businesses.")

                for business in businesses[offset:offset+limit]:
                    try:
                        full_text = business.inner_text()
                        
                        name_element = business.query_selector('.fontHeadlineSmall, .qBF1Pd')
                        if not name_element:
                            continue
                        name = name_element.inner_text().strip()

                        if "Site Web" in full_text:
                            self.logger.debug(f"Skipping '{name}' - has website link.")
                            continue
                        
                        address = None
                        addr_elements = business.query_selector_all('div.W4Efsd:not(:first-child) > span:nth-child(2)')
                        for elem in addr_elements:
                            text = elem.inner_text()
                            if re.search(r'\d{5}', text):
                                address = text
                                break
                        
                        dept = self.validate_department(address) if address else None
                        if not dept:
                            self.logger.debug(f"Skipping '{name}' - department not in {self.VALID_DEPARTMENTS} or address not found.")
                            continue

                        phone = self.normalize_phone(full_text)
                        
                        result = {
                            'name': name,
                            'phone': phone,
                            'address': address,
                            'city': self.extract_city_from_address(address),
                            'department': dept,
                            'activity': query.title(),
                            'source': 'Maps',
                            'website': None,
                            'email': None,
                            'extracted_from': 'real_html_v2',
                            'geo_validated': True,
                            'scraped_at': datetime.now().isoformat(),
                            'session_id': self.session_id
                        }
                        results.append(result)
                        self.logger.info(f"✅ Extracted: {name}")
                        
                    except Exception as e:
                        self.logger.debug(f"Error extracting a single business: {e}")
                
            except Exception as e:
                self.logger.error(f"A general Playwright error occurred: {e}")
                page.screenshot(path='error_screenshot.png')
                self.logger.info("An error screenshot has been saved to 'error_screenshot.png'")
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
    
    for result in results:
        print(json.dumps(result, ensure_ascii=False))
    
    if args.debug:
        logging.info(f"SUCCESS: {len(results)} results extracted")

if __name__ == "__main__":
    main()
