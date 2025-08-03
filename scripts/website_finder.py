#!/usr/bin/env python3
"""
Website Finder pour Naosite - Compatible n8n Input
Traite les données directement depuis n8n sendInputToCommand
"""

import json
import time
import argparse
import sys
import logging
import re
from typing import Optional, Dict, Tuple
import random
from datetime import datetime
from urllib.parse import quote_plus, urlparse

try:
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

class WebsiteFinder:
    def __init__(self, session_id: str = None, debug: bool = False, headless: bool = True):
        if not SELENIUM_AVAILABLE:
            raise ImportError("Please install: pip install undetected-chromedriver selenium beautifulsoup4")
            
        self.session_id = session_id or f"finder_{int(time.time())}"
        self.debug = debug
        self.headless = headless
        self.setup_logging()
        
        # Configuration proxy Webshare
        self.proxy_host = "p.webshare.io"
        self.proxy_port = "80"
        self.proxy_user = "xftpfnvt"
        self.proxy_pass = "yulnmnbiq66j"
        
        self.driver = None
        
    def setup_logging(self):
        level = logging.DEBUG if self.debug else logging.WARNING
        logging.basicConfig(
            level=level,
            format=f'[{self.session_id}] %(levelname)s: %(message)s',
            stream=sys.stderr
        )
        self.logger = logging.getLogger(__name__)
    
    def setup_driver(self):
        """Configure Chrome avec proxy Webshare"""
        try:
            options = uc.ChromeOptions()
            
            # Configuration proxy
            proxy_string = f"{self.proxy_user}:{self.proxy_pass}@{self.proxy_host}:{self.proxy_port}"
            options.add_argument(f'--proxy-server=http://{proxy_string}')
            
            # Options standard
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-web-security')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--lang=fr-FR')
            
            if self.headless:
                options.add_argument('--headless=new')
            
            # User agent français
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            self.driver = uc.Chrome(options=options, version_main=None)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.driver.implicitly_wait(10)
            
            self.logger.info("Chrome driver initialized with Webshare proxy")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to setup driver: {e}")
            return False

    def extract_website_and_phone_from_maps(self, search_query: str) -> Tuple[Optional[str], Optional[str]]:
        """Cherche le site web ET le téléphone sur Google Maps"""
        website_url = None
        phone = None
        
        try:
            search_url = f"https://www.google.com/maps/search/{quote_plus(search_query)}"
            self.driver.get(search_url)
            
            time.sleep(random.uniform(3, 5))
            
            # Accepter cookies
            try:
                accept_button = self.driver.find_element(By.XPATH, "//button[contains(., 'Tout accepter')]")
                accept_button.click()
                time.sleep(1)
            except:
                pass
            
            # Chercher le premier résultat
            try:
                first_result = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, '[role="feed"] a[href*="/maps/place/"]'))
                )
                first_result.click()
                time.sleep(random.uniform(2, 4))
                
                # Site web
                website_selectors = [
                    'a[data-item-id="authority"]',
                    'a.lcr4fd',
                    'a[href*="http"]:not([href*="google.com"]):not([href*="maps"])'
                ]
                
                for selector in website_selectors:
                    try:
                        website_elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                        if website_elem:
                            href = website_elem.get_attribute('href')
                            if href and 'http' in href and 'google' not in href:
                                website_url = href
                                break
                    except:
                        continue
                
                # Téléphone
                phone_selectors = [
                    'button[data-item-id^="phone:tel:"]',
                    '[data-item-id^="phone"] span'
                ]
                
                for selector in phone_selectors:
                    try:
                        phone_elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                        if phone_elem:
                            phone_text = phone_elem.text.strip()
                            if not phone_text and 'data-item-id' in phone_elem.get_attribute('outerHTML'):
                                phone_id = phone_elem.get_attribute('data-item-id')
                                if 'tel:' in phone_id:
                                    phone_text = phone_id.split('tel:')[1]
                            
                            if phone_text and self.is_valid_french_phone(phone_text):
                                phone = phone_text
                                break
                    except:
                        continue
                        
            except TimeoutException:
                self.logger.debug("No Maps results found")
                
        except Exception as e:
            self.logger.error(f"Error in Maps search: {e}")
            
        return website_url, phone

    def is_valid_french_phone(self, phone: str) -> bool:
        """Valide un numéro de téléphone français"""
        if not phone:
            return False
        
        clean_phone = re.sub(r'[^\d+]', '', phone)
        patterns = [
            r'^0[1-9]\d{8}$',
            r'^\+33[1-9]\d{8}$',
            r'^33[1-9]\d{8}$',
        ]
        
        return any(re.match(pattern, clean_phone) for pattern in patterns)
    
    def find_website(self, search_query: str) -> Dict:
        """Fonction principale - trouve le site web ET le téléphone"""
        result = {
            'search_query': search_query,
            'website_url': None,
            'phone': None,
            'source': None,
            'found_at': None,
            'session_id': self.session_id
        }
        
        if not self.setup_driver():
            result['error'] = 'Driver setup failed'
            return result
        
        try:
            self.logger.info(f"Searching for: {search_query}")
            
            # Chercher sur Google Maps
            website_url, phone = self.extract_website_and_phone_from_maps(search_query)
            
            if website_url or phone:
                result.update({
                    'website_url': website_url,
                    'phone': phone,
                    'source': 'google_maps',
                    'found_at': datetime.now().isoformat()
                })
            else:
                result['source'] = 'not_found'
                
        except Exception as e:
            result['error'] = str(e)
            self.logger.error(f"Search failed: {e}")
            
        finally:
            if self.driver:
                self.driver.quit()
                
        return result

def main():
    parser = argparse.ArgumentParser(description='Website Finder for Naosite')
    parser.add_argument('--batch-mode', action='store_true', help='Process batch from stdin')
    parser.add_argument('--find-websites-only', action='store_true', help='Only find websites')
    parser.add_argument('--session-id', help='Session ID for tracking')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--no-headless', action='store_true', help='Show browser window')
    
    args = parser.parse_args()
    
    try:
        if args.batch_mode:
            # ✅ LIRE DEPUIS STDIN (n8n sendInputToCommand)
            input_text = sys.stdin.read().strip()
            
            # ✅ GESTION DES FORMATS n8n
            try:
                # Cas 1: n8n envoie directement le JSON
                if input_text.startswith('[') or input_text.startswith('{'):
                    input_data = json.loads(input_text)
                # Cas 2: n8n envoie une string JSON
                else:
                    input_data = json.loads(input_text)
                
                # Normaliser en liste
                if not isinstance(input_data, list):
                    input_data = [input_data]
                    
            except json.JSONDecodeError as e:
                logging.error(f"JSON parse error: {e}")
                print(json.dumps({'error': f'Invalid JSON input: {e}'}, ensure_ascii=False))
                sys.exit(1)
            
            # Créer le finder
            finder = WebsiteFinder(
                session_id=args.session_id,
                debug=args.debug,
                headless=not args.no_headless
            )
            
            # Traiter chaque entreprise
            results = []
            for i, item in enumerate(input_data):
                query = item.get('searchQuery', '')
                if not query:
                    continue
                
                try:
                    # Délai entre recherches
                    if i > 0:
                        time.sleep(random.uniform(2, 4))
                    
                    result = finder.find_website(query)
                    
                    # ✅ ENRICHIR avec toutes les données originales
                    enhanced_result = {
                        'search_query': result['search_query'],
                        'website_url': result.get('website_url'),
                        'phone': result.get('phone'),
                        'source': result.get('source'),
                        'found_at': result.get('found_at'),
                        'session_id': result.get('session_id'),
                        
                        # Données originales
                        **{k: v for k, v in item.items() if k != 'searchQuery'},
                        
                        # Données dérivées
                        'hasWebsite': bool(result.get('website_url')),
                        'websiteSource': result.get('source', 'not_found')
                    }
                    
                    # Nettoyer None
                    enhanced_result = {k: v for k, v in enhanced_result.items() if v is not None}
                    results.append(enhanced_result)
                    
                    # Log progrès
                    status = "🌐 Website" if result.get('website_url') else "📞 Phone" if result.get('phone') else "❌ Nothing"
                    logging.info(f"{status} ({i+1}/{len(input_data)}): {item.get('searchName', query)}")
                    
                except Exception as e:
                    # Garder données de base en cas d'erreur
                    error_result = {
                        **item,
                        'website_url': None,
                        'phone': None,
                        'source': 'error',
                        'error': str(e),
                        'hasWebsite': False
                    }
                    results.append(error_result)
                    logging.error(f"Error processing {item.get('searchName', query)}: {e}")
            
            # ✅ OUTPUT pour n8n (une ligne par résultat)
            for result in results:
                print(json.dumps(result, ensure_ascii=False))
                
            # Stats
            total = len(results)
            with_website = sum(1 for r in results if r.get('hasWebsite'))
            with_phone = sum(1 for r in results if r.get('phone'))
            logging.info(f"📊 Batch: {total} processed, {with_website} websites, {with_phone} phones")
                
        else:
            print("Batch mode only supported")
            sys.exit(1)
            
    except Exception as e:
        print(json.dumps({'error': f'Processing failed: {e}'}, ensure_ascii=False))
        logging.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
