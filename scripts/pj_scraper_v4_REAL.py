#!/usr/bin/env python3
"""
Pages Jaunes Scraper v4.0 REAL - FIXED VERSION
Utilise Playwright pour contourner les protections anti-bot
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
import re

# Configuration
PROXY_HOST = "proxy.webshare.io"
PROXY_PORT = "8000"
PROXY_USER = "xftpfnvt"
PROXY_PASS = "yulnmnbiq66j"

class RealPJScraper:
    def __init__(self, session_id=None, debug=False):
        self.session_id = session_id or f"pj_{int(time.time())}"
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
    
    def extract_email(self, text):
        """Extrait un email valide du texte"""
        if not text:
            return None
        
        email_pattern = r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b'
        matches = re.findall(email_pattern, text, re.IGNORECASE)
        
        for email in matches:
            email = email.lower().strip()
            # Filtrer les emails génériques
            if not any(spam in email for spam in ['noreply', 'no-reply', 'pagesjaunes', 'solocal']):
                return email
        return None
    
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
    
    def scrape_with_playwright(self, query, city, limit=14, max_pages=2):
        """Scrape Pages Jaunes avec Playwright"""
        results = []
        
        with sync_playwright() as p:
            # Configuration du navigateur
            browser_args = [
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled'
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
            """)
            
            page = context.new_page()
            
            try:
                for page_num in range(1, min(max_pages + 1, 3)):
                    # URL Pages Jaunes
                    pj_url = f"https://www.pagesjaunes.fr/annuaire/chercherlesprofessionnels?quoi={query}&ou={city}&page={page_num}"
                    
                    self.logger.info(f"Loading PJ page {page_num}: {pj_url}")
                    
                    # Délai entre les pages
                    if page_num > 1:
                        time.sleep(random.uniform(3, 5))
                    
                    page.goto(pj_url, wait_until='domcontentloaded', timeout=30000)
                    
                    # Attendre le chargement
                    time.sleep(random.uniform(2, 4))
                    
                    # Gérer les popups/cookies
                    try:
                        cookie_button = page.query_selector('button#didomi-notice-agree-button')
                        if cookie_button:
                            cookie_button.click()
                            time.sleep(1)
                    except:
                        pass
                    
                    # Sélecteurs pour les résultats
                    business_selectors = [
                        'article.bi',
                        'li.bi-bloc',
                        'div.bi',
                        'article[itemtype*="LocalBusiness"]'
                    ]
                    
                    businesses = []
                    for selector in business_selectors:
                        try:
                            elements = page.query_selector_all(selector)
                            if elements:
                                businesses = elements
                                self.logger.info(f"Found {len(elements)} businesses with: {selector}")
                                break
                        except:
                            continue
                    
                    if not businesses:
                        self.logger.warning(f"No businesses found on page {page_num}")
                        continue
                    
                    # Extraire les données
                    for business in businesses:
                        try:
                            # Nom
                            name = None
                            name_selectors = ['.bi-denomination', '.denomination-links', 'h3 a']
                            for sel in name_selectors:
                                elem = business.query_selector(sel)
                                if elem:
                                    name = elem.inner_text().strip()
                                    if name:
                                        break
                            
                            if not name:
                                continue
                            
                            # Adresse
                            address = None
                            addr_elem = business.query_selector('.bi-address, .address')
                            if addr_elem:
                                address = addr_elem.inner_text().strip()
                            
                            # Validation département
                            dept = self.validate_department(address) if address else None
                            if not dept:
                                self.logger.debug(f"Skipping {name} - invalid department")
                                continue
                            
                            # Téléphone
                            phone = None
                            phone_selectors = [
                                'span.coord-numero',
                                'a[href^="tel:"]',
                                '.bi-phone'
                            ]
                            for sel in phone_selectors:
                                elem = business.query_selector(sel)
                                if elem:
                                    phone_text = elem.get_attribute('href') or elem.inner_text()
                                    if phone_text:
                                        if phone_text.startswith('tel:'):
                                            phone_text = phone_text[4:]
                                        phone = self.normalize_phone(phone_text)
                                        if phone:
                                            break
                            
                            # Email
                            email = None
                            email_elem = business.query_selector('a[href^="mailto:"]')
                            if email_elem:
                                email = self.extract_email(email_elem.get_attribute('href'))
                            
                            # Si pas d'email dans mailto, chercher dans le texte
                            if not email:
                                full_text = business.inner_text()
                                email = self.extract_email(full_text)
                            
                            # Site web (pour filtrage)
                            website = None
                            website_elem = business.query_selector('a.bi-site-internet, a[href*="http"]:not([href*="pagesjaunes"])')
                            if website_elem:
                                href = website_elem.get_attribute('href')
                                if href and 'http' in href and 'pagesjaunes' not in href:
                                    website = href
                            
                            # Activité
                            activity = query.title()
                            activity_elem = business.query_selector('.bi-activity, .activites')
                            if activity_elem:
                                activity_text = activity_elem.inner_text().strip()
                                if activity_text:
                                    activity = activity_text
                            
                            # Créer le résultat
                            result = {
                                'name': name,
                                'phone': phone,
                                'email': email,
                                'address': address,
                                'city': city,
                                'department': dept,
                                'website': website,
                                'activity': activity,
                                'source': 'pages_jaunes',
                                'extracted_from': 'real_pj_html',
                                'geo_validated': True,
                                'has_email': bool(email),
                                'scraped_at': datetime.now().isoformat(),
                                'session_id': self.session_id,
                                'page': page_num
                            }
                            
                            results.append(result)
                            
                            if email:
                                self.logger.info(f"✅ EMAIL FOUND: {name} -> {email}")
                            else:
                                self.logger.info(f"✅ Extracted: {name}")
                            
                            if len(results) >= limit:
                                break
                                
                        except Exception as e:
                            self.logger.debug(f"Error extracting business: {e}")
                            continue
                    
                    if len(results) >= limit:
                        break
                        
            except Exception as e:
                self.logger.error(f"Playwright error: {e}")
            finally:
                browser.close()
        
        return results[:limit]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("query", help="Profession/activité à rechercher")
    parser.add_argument("--city", required=True, help="Code postal ou ville")
    parser.add_argument("--limit", type=int, default=14)
    parser.add_argument("--max-pages", type=int, default=2)
    parser.add_argument("--session-id", help="Session ID")
    parser.add_argument("--debug", action="store_true")
    
    args = parser.parse_args()
    
    scraper = RealPJScraper(
        session_id=args.session_id,
        debug=args.debug
    )
    
    results = scraper.scrape_with_playwright(
        query=args.query,
        city=args.city,
        limit=args.limit,
        max_pages=args.max_pages
    )
    
    # Output pour n8n
    for result in results:
        print(json.dumps(result, ensure_ascii=False))
    
    if args.debug:
        email_count = sum(1 for r in results if r.get('email'))
        logging.info(f"SUCCESS: {len(results)} results ({email_count} with email)")

if __name__ == "__main__":
    main()
