#!/usr/bin/env python3
"""
Website Finder pour Naosite - Version batch mode pour n8n
Traite plusieurs entreprises en lot depuis stdin JSON
"""

import json
import time
import argparse
import sys
import logging
import re
from typing import Optional, Dict, List
import random
from datetime import datetime
from urllib.parse import quote_plus, urlparse

try:
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    from selenium.webdriver.chrome.service import Service
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

class WebsiteFinderBatch:
    def __init__(self, session_id: str = None, debug: bool = False, use_proxy: bool = True, test_mode: bool = False):
        if not SELENIUM_AVAILABLE:
            raise ImportError("Please install: pip install undetected-chromedriver selenium")
            
        self.session_id = session_id or f"batch_{int(time.time())}"
        self.debug = debug
        self.use_proxy = use_proxy
        self.test_mode = test_mode
        self.setup_logging()
        
        # Configuration proxy Webshare
        self.proxy_host = ".webshare.io"
        self.proxy_port = "1080" 
        self.proxy_user = "xftpfnvt-rotate"
        self.proxy_pass = "yulnmnbiq66j"
        
        self.driver = None
        
        # Statistiques
        self.stats = {
            'total_companies': 0,
            'processed': 0,
            'with_website': 0,
            'with_phone': 0,
            'errors': 0
        }
        
    def setup_logging(self):
        level = logging.DEBUG if self.debug else logging.INFO
        logging.basicConfig(
            level=level,
            format=f'[{self.session_id}] %(levelname)s: %(message)s',
            stream=sys.stderr
        )
        self.logger = logging.getLogger(__name__)
    
    def setup_driver(self):
        
        try:
            if self.test_mode:
                self.logger.info("🧪 TEST MODE: No proxy, direct connection only")
            
            self.logger.info("🚀 Initializing robust Chrome for batch processing...")
            
            options = uc.ChromeOptions()
            
            # --- Options anti-détection et de stabilité ---
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--window-size=1280,800')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-extensions') # L'extension de proxy sera chargée plus bas
            options.add_argument('--disable-images')
            options.add_argument('--lang=fr-FR,fr')
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')
            
            # --- Configuration du proxy via une extension (méthode fiable) ---
            if self.use_proxy and not self.test_mode:
                self.logger.info("🔗 Configuring Webshare proxy via extension...")
                import os
                plugin_path = '/tmp/proxy_auth_plugin'
                
                manifest_json = """
                { "version": "1.0.0", "manifest_version": 2, "name": "Chrome Proxy", "permissions": ["proxy", "<all_urls>", "webRequest", "webRequestBlocking"], "background": { "scripts": ["background.js"] } }
                """
                background_js = f'''
                var config = {{ mode: "fixed_servers", rules: {{ singleProxy: {{ scheme: "http", host: "{self.proxy_host}", port: parseInt("{self.proxy_port}") }} }} }};
                chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{}});
                function callbackFn(details) {{ return {{ authCredentials: {{ username: "{self.proxy_user}", password: "{self.proxy_pass}" }} }}; }}
                chrome.webRequest.onAuthRequired.addListener(callbackFn, {{urls: ["<all_urls>"]}}, ['blocking']);
                '''
                
                if not os.path.exists(plugin_path):
                    os.makedirs(plugin_path)
                with open(os.path.join(plugin_path, "manifest.json"), "w") as f:
                    f.write(manifest_json)
                with open(os.path.join(plugin_path, "background.js"), "w") as f:
                    f.write(background_js)
                
                options.add_argument(f'--load-extension={plugin_path}')
                self.logger.info(f"Proxy Webshare configured for user: {self.proxy_user}")
            else:
                self.logger.info("⚠️ PROXY DISABLED - Direct connection")
            
            self.logger.info("⚙️ Creating Chrome instance...")
            
            self.driver = uc.Chrome(options=options, use_subprocess=True)
            self.driver.set_page_load_timeout(30)
            self.driver.implicitly_wait(5)
            
            # Test de connectivité
            if not self.test_mode:
                self.logger.info("🧪 Testing connectivity...")
                try:
                    self.driver.get("https://httpbin.org/ip")
                    time.sleep(2)
                    ip_info_text = self.driver.find_element(By.TAG_NAME, "pre").text
                    ip_info = json.loads(ip_info_text)
                    self.logger.info(f"✅ Connection working! IP: {ip_info.get('origin')}")
                except Exception as e:
                    self.logger.warning(f"⚠️ Connection test failed (but driver is likely OK): {e}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Driver setup failed: {e}", exc_info=True)
            return False
    
    def search_company_website(self, company: Dict) -> Dict:
        """Recherche le site web d'une entreprise"""
        result = {
            **company,  # Conserver toutes les données originales
            'website_url': None,
            'phone': None,
            'hasWebsite': False,
            'websiteSource': 'not_found',
            'processed_at': datetime.now().isoformat(),
            'session_id': self.session_id
        }
        
        try:
            search_query = company.get('searchQuery', '')
            if not search_query:
                search_query = f"{company.get('searchName', '')} {company.get('activity', '')} {company.get('ville', '')}"
            
            self.logger.info(f"🔍 Searching: {company.get('searchName', 'Unknown')}")
            
            # Google Maps search
            maps_url = f"https://www.google.com/maps/search/{quote_plus(search_query)}"
            
            try:
                self.driver.get(maps_url)
                time.sleep(random.uniform(2, 4))
                
                # Accepter cookies si nécessaire
                try:
                    cookie_selectors = [
                        "//button[contains(., 'Tout accepter')]",
                        "//button[contains(., 'Accept all')]",
                        "#L2AGLb"
                    ]
                    for selector in cookie_selectors:
                        try:
                            if selector.startswith('#'):
                                button = self.driver.find_element(By.CSS_SELECTOR, selector)
                            else:
                                button = self.driver.find_element(By.XPATH, selector)
                            button.click()
                            time.sleep(1)
                            break
                        except:
                            continue
                except:
                    pass
                
                # Attendre et cliquer sur le premier résultat
                try:
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, '[role="feed"], [role="main"]'))
                    )
                    
                    # Cliquer sur le premier résultat
                    first_result = self.driver.find_element(By.CSS_SELECTOR, 'a[href*="/maps/place/"]')
                    self.driver.execute_script("arguments[0].click();", first_result)
                    time.sleep(random.uniform(2, 3))
                    
                    # Chercher le site web
                    website_selectors = [
                        'a[data-item-id="authority"]',
                        'a.lcr4fd',
                        'button[data-item-id="authority"]',
                        '[data-item-id="authority"] a'
                    ]
                    
                    for selector in website_selectors:
                        try:
                            website_elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                            href = website_elem.get_attribute('href')
                            if href and 'http' in href and 'google' not in href:
                                result.update({
                                    'website_url': href,
                                    'hasWebsite': True,
                                    'websiteSource': 'google_maps'
                                })
                                self.logger.info(f"🌐 Website found: {href}")
                                break
                        except:
                            continue
                    
                    # Chercher le téléphone
                    phone_selectors = [
                        'button[data-item-id^="phone:tel:"]',
                        '[data-item-id^="phone"] span'
                    ]
                    
                    for selector in phone_selectors:
                        try:
                            phone_elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                            phone_text = phone_elem.text.strip()
                            
                            if not phone_text and 'data-item-id' in phone_elem.get_attribute('outerHTML'):
                                phone_id = phone_elem.get_attribute('data-item-id')
                                if 'tel:' in phone_id:
                                    phone_text = phone_id.split('tel:')[1]
                            
                            if phone_text and re.search(r'0[1-9][\s\-\.]*(?:\d[\s\-\.]*){8}', phone_text):
                                result['phone'] = phone_text
                                self.logger.info(f"📞 Phone found: {phone_text}")
                                break
                        except:
                            continue
                    
                except TimeoutException:
                    self.logger.warning(f"⚠️ Timeout for {company.get('searchName')}")
                except Exception as e:
                    self.logger.warning(f"⚠️ Maps search failed for {company.get('searchName')}: {e}")
                
            except Exception as e:
                self.logger.error(f"❌ Error searching {company.get('searchName')}: {e}")
                self.stats['errors'] += 1
                result['error'] = str(e)
            
            # Mise à jour statistiques
            self.stats['processed'] += 1
            if result['hasWebsite']:
                self.stats['with_website'] += 1
            if result.get('phone'):
                self.stats['with_phone'] += 1
                
        except Exception as e:
            self.logger.error(f"❌ Critical error for {company.get('searchName')}: {e}")
            result['error'] = str(e)
            self.stats['errors'] += 1
        
        return result
    
    def process_batch(self, companies: List[Dict]) -> List[Dict]:
        """Traite un batch d'entreprises"""
        results = []
        
        self.stats['total_companies'] = len(companies)
        self.logger.info(f"🚀 Starting batch: {len(companies)} companies")
        
        if not self.setup_driver():
            self.logger.error("❌ Failed to initialize Chrome")
            return []
        
        try:
            for i, company in enumerate(companies, 1):
                try:
                    self.logger.info(f"📋 Processing {i}/{len(companies)}: {company.get('searchName', 'Unknown')}")
                    
                    result = self.search_company_website(company)
                    results.append(result)
                    
                    # Petit délai entre les recherches
                    if i < len(companies):
                        time.sleep(random.uniform(1, 3))
                    
                except Exception as e:
                    self.logger.error(f"❌ Error processing company {i}: {e}")
                    # Ajouter un résultat d'erreur
                    error_result = {
                        **company,
                        'website_url': None,
                        'phone': None,
                        'hasWebsite': False,
                        'websiteSource': 'error',
                        'error': str(e),
                        'processed_at': datetime.now().isoformat()
                    }
                    results.append(error_result)
                    continue
            
        finally:
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
        
        # Log des statistiques finales
        self.logger.info(f"📊 Batch completed: {self.stats['processed']}/{self.stats['total_companies']} processed")
        self.logger.info(f"🌐 Websites found: {self.stats['with_website']}")
        self.logger.info(f"📞 Phones found: {self.stats['with_phone']}")
        self.logger.info(f"❌ Errors: {self.stats['errors']}")
        
        return results

def main():
    parser = argparse.ArgumentParser(description='Website Finder for Naosite - Batch Mode')
    
    # Mode batch
    parser.add_argument('--batch-mode', action='store_true', help='Process multiple companies from stdin JSON')
    parser.add_argument('--find-websites-only', action='store_true', help='Only find websites, do not analyze quality')
    
    # Options
    parser.add_argument('--session-id', help='Session ID for tracking')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--no-proxy', action='store_true', help='Disable proxy (for testing)')
    parser.add_argument('--test-mode', action='store_true', help='Enable test mode (limit processing)')
    
    # Argument query pour compatibilité (optionnel en mode batch)
    parser.add_argument('query', nargs='?', help='Business search query (not used in batch mode)')
    
    args = parser.parse_args()
    
    if not args.batch_mode and not args.query:
        parser.error("query argument is required when not in batch mode")
    
    try:
        if args.batch_mode:
            # Mode batch : lire depuis stdin
            logging.info("📥 Reading input data...")
            
            input_data = sys.stdin.read().strip()
            if not input_data:
                logging.error("❌ No input data received")
                sys.exit(1)
            
            try:
                companies = json.loads(input_data)
                logging.info(f"📊 Data loaded from stdin")
            except json.JSONDecodeError as e:
                logging.error(f"❌ Invalid JSON input: {e}")
                sys.exit(1)
            
            if not isinstance(companies, list):
                logging.error("❌ Input must be a JSON array of companies")
                sys.exit(1)
            
            logging.info(f"📋 Loaded {len(companies)} companies")
            
            # Mode test : limiter à 3 entreprises
            if args.test_mode and len(companies) > 3:
                companies = companies[:3]
                logging.info(f"🧪 TEST MODE: Limited to {len(companies)} companies")
            
            # Traitement batch
            finder = WebsiteFinderBatch(
                session_id=args.session_id,
                debug=args.debug,
                use_proxy=not args.no_proxy,
                test_mode=args.test_mode
            )
            
            results = finder.process_batch(companies)
            
            # Output : une ligne JSON par entreprise
            logging.info("📤 Outputting results...")
            for result in results:
                print(json.dumps(result, ensure_ascii=False))
                
            if args.debug:
                logging.info(f"✅ Batch processing completed: {len(results)} results")
        
        else:
            # Mode simple query (pour compatibilité)
            logging.error("❌ Single query mode not implemented in batch version")
            sys.exit(1)
            
    except Exception as e:
        logging.error(f"❌ Batch failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
