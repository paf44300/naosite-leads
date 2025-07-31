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
PROXY_HOST = "proxy.webshare.io"
PROXY_PORT = "8000"
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
                locale='fr-FR'
            )
            
            # Anti-détection
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                window.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
            """)
            
            page = context.new_page()
            
            try:
                # Construction de l'URL
                search_query = f"{query} {city}".strip()
                maps_url = f"https://www.google.com/maps/search/{search_query.replace(' ', '+')}"
                
                self.logger.info(f"Loading: {maps_url}")
                
                # Charger la page
                page.goto(maps_url, wait_until='domcontentloaded', timeout=30000)
                
                # Attendre que les résultats se chargent
                time.sleep(random.uniform(3, 5))
                
                # Attendre le panneau latéral des résultats
                try:
                    page.wait_for_selector('div[role="feed"]', timeout=10000)
                except:
                    self.logger.warning("Feed not found, trying alternative selectors")
                
                # Scroll pour charger plus de résultats
                for _ in range(3):
                    page.evaluate('document.querySelector("div[role=\\"feed\\"]")?.scrollBy(0, 1000)')
                    time.sleep(random.uniform(1, 2))
                
                # Sélecteurs pour les business cards
                business_selectors = [
                    'div[jsaction*="mouseover"][role="article"]',
                    'a[href*="/maps/place/"]',
                    'div[data-index]',
                    '.Nv2PK',
                    '.THOPZb'
                ]
                
                businesses = []
                for selector in business_selectors:
                    try:
                        elements = page.query_selector_all(selector)
                        if elements:
                            businesses = elements
                            self.logger.info(f"Found {len(elements)} with selector: {selector}")
                            break
                    except:
                        continue
                
                # Extraire les données
                for i, business in enumerate(businesses[offset:offset+limit]):
                    try:
                        # Cliquer pour avoir plus de détails (optionnel)
                        try:
                            business.click()
                            time.sleep(random.uniform(0.5, 1))
                        except:
                            pass
                        
                        # Extraction du nom
                        name = None
                        name_selectors = ['.DUwDvf', '.fontHeadlineSmall', 'h1', '.qBF1Pd']
                        for sel in name_selectors:
                            elem = business.query_selector(sel)
                            if elem:
                                name = elem.inner_text().strip()
                                if name:
                                    break
                        
                        if not name:
                            continue
                        
                        # Vérifier l'absence de site web
                        website_elem = business.query_selector('a[data-value*="Website"], a[aria-label*="Site"]')
                        if website_elem:
                            self.logger.debug(f"Skipping {name} - has website")
                            continue
                        
                        # Extraction du téléphone
                        phone = None
                        phone_selectors = [
                            'button[data-tooltip*="phone"]',
                            'a[href^="tel:"]',
                            'span[aria-label*="Téléphone"]'
                        ]
                        for sel in phone_selectors:
                            elem = business.query_selector(sel)
                            if elem:
                                phone_text = elem.get_attribute('aria-label') or elem.inner_text()
                                if phone_text:
                                    phone = self.normalize_phone(phone_text)
                                    if phone:
                                        break
                        
                        # Extraction de l'adresse
                        address = None
                        addr_selectors = [
                            'button[data-item-id*="address"]',
                            'div[aria-label*="Adresse"]',
                            '.W4Efsd:nth-of-type(2) span:nth-of-type(2)'
                        ]
                        for sel in addr_selectors:
                            elem = business.query_selector(sel)
                            if elem:
                                address = elem.inner_text().strip()
                                if address and len(address) > 5:
                                    break
                        
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
                            'source': 'google_maps',
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
