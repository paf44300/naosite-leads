#!/usr/bin/env python3
"""
Website Finder pour Naosite - Version ultra robuste avec Webshare rotatif
Pas de fallback - uniquement de vraies données extraites
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
from urllib.parse import quote_plus
import subprocess
import os

try:
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

class RobustWebsiteFinder:
    def __init__(self, session_id: str = None, debug: bool = False, use_proxy: bool = True, test_mode: bool = False):
        if not SELENIUM_AVAILABLE:
            raise ImportError("Please install: pip install undetected-chromedriver selenium")
            
        self.session_id = session_id or f"robust_{int(time.time())}"
        self.debug = debug
        self.use_proxy = use_proxy
        self.test_mode = test_mode
        self.setup_logging()
        
        # Configuration proxy Webshare ROTATIF
        self.proxy_endpoints = [
            {"host": "p.webshare.io", "port": "80"},
            {"host": "proxy.webshare.io", "port": "8000"},
            {"host": "rotating-residential.webshare.io", "port": "80"}
        ]
        self.proxy_user = "xftpfnvt-rotate"
        self.proxy_pass = "yulnmnbiq66j"
        
        self.driver = None
        self.driver_failures = 0
        self.max_driver_failures = 3
        
        # Statistiques
        self.stats = {
            'total_companies': 0,
            'processed': 0,
            'with_website': 0,
            'with_phone': 0,
            'driver_restarts': 0,
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
    
    def check_chrome_binary(self):
        """Vérifier que Chrome est accessible"""
        chrome_binaries = [
            '/usr/bin/google-chrome-stable',
            '/usr/bin/google-chrome',
            '/usr/bin/chromium-browser',
            '/usr/bin/chromium'
        ]
        
        for binary in chrome_binaries:
            if os.path.exists(binary):
                try:
                    result = subprocess.run([binary, '--version'], 
                                          capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        self.logger.info(f"✅ Chrome found: {binary} - {result.stdout.strip()}")
                        return binary
                except Exception as e:
                    self.logger.debug(f"Chrome test failed for {binary}: {e}")
                    continue
        
        self.logger.error("❌ No working Chrome binary found!")
        return None
    
    def get_rotating_proxy(self):
        """Obtenir un proxy rotatif depuis la liste"""
        if not self.use_proxy or self.test_mode:
            return None
        
        endpoint = random.choice(self.proxy_endpoints)
        proxy_url = f"http://{self.proxy_user}:{self.proxy_pass}@{endpoint['host']}:{endpoint['port']}"
        self.logger.debug(f"Using proxy: {endpoint['host']}:{endpoint['port']}")
        return proxy_url
    
    def setup_driver(self):
        """Configure Chrome avec toutes les optimisations possibles"""
        try:
            self.logger.info("🚀 Setting up Chrome driver (ultra robust mode)...")
            
            # Vérifier Chrome
            chrome_binary = self.check_chrome_binary()
            if not chrome_binary:
                raise Exception("Chrome binary not found")
            
            # Nettoyer les anciens processus Chrome
            try:
                subprocess.run(['pkill', '-f', 'chrome'], capture_output=True, timeout=5)
                time.sleep(1)
            except:
                pass
            
            # Configuration Chrome options
            options = uc.ChromeOptions()
            
            # === OPTIONS CRITIQUES POUR CONTAINERS ===
            options.add_argument('--headless=new')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-software-rasterizer')
            options.add_argument('--disable-background-timer-throttling')
            options.add_argument('--disable-backgrounding-occluded-windows')
            options.add_argument('--disable-renderer-backgrounding')
            options.add_argument('--disable-features=TranslateUI,BlinkGenPropertyTrees,VizDisplayCompositor')
            options.add_argument('--disable-ipc-flooding-protection')
            options.add_argument('--disable-web-security')
            options.add_argument('--disable-extensions')
            options.add_argument('--disable-plugins')
            options.add_argument('--disable-default-apps')
            options.add_argument('--disable-sync')
            options.add_argument('--disable-background-networking')
            options.add_argument('--disable-blink-features=AutomationControlled')
            
            # === PERFORMANCE ET MÉMOIRE ===
            options.add_argument('--memory-pressure-off')
            options.add_argument('--max_old_space_size=1024')
            options.add_argument('--window-size=1280,720')
            options.add_argument('--start-maximized')
            
            # === DISPLAY ET XVFB ===
            if os.environ.get('DISPLAY'):
                options.add_argument(f'--display={os.environ["DISPLAY"]}')
            
            # === STABILITÉ ===
            options.add_argument('--disable-crash-reporter')
            options.add_argument('--disable-in-process-stack-traces')
            options.add_argument('--disable-logging')
            options.add_argument('--disable-breakpad')
            options.add_argument('--no-first-run')
            options.add_argument('--no-default-browser-check')
            options.add_argument('--disable-client-side-phishing-detection')
            
            # === LOCALE ===
            options.add_argument('--lang=fr-FR')
            options.add_argument('--accept-lang=fr-FR,fr,en-US,en')
            
            # === USER AGENT ===
            options.add_argument('--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            # === PROXY ROTATIF ===
            proxy_url = self.get_rotating_proxy()
            if proxy_url:
                options.add_argument(f'--proxy-server={proxy_url}')
                self.logger.info("🔗 Webshare rotating proxy configured")
            else:
                self.logger.info("⚠️ No proxy - Direct connection")
            
            # === TIMEOUTS ET PERFORMANCE ===
            options.add_argument('--timeout=30000')
            options.add_argument('--page-load-strategy=eager')
            
            # === PREFS POUR PERFORMANCE ===
            prefs = {
                "profile.managed_default_content_settings.images": 2,
                "profile.default_content_setting_values.notifications": 2,
                "profile.default_content_settings.popups": 0,
                "profile.default_content_settings.geolocation": 2,
                "profile.default_content_settings.media_stream": 2
            }
            options.add_experimental_option("prefs", prefs)
            
            # === BINARY PATH ===
            options.binary_location = chrome_binary
            
            # === SERVICE CONFIGURATION ===
            service_args = [
                '--verbose',
                '--log-path=/tmp/chromedriver.log',
                '--whitelisted-ips='
            ]
            
            self.logger.info("⚙️ Creating Chrome driver instance...")
            
            # Créer le driver avec gestion d'erreur
            try:
                self.driver = uc.Chrome(
                    options=options,
                    version_main=None,
                    service_args=service_args
                )
            except Exception as e:
                self.logger.warning(f"undetected-chromedriver failed: {e}, trying regular selenium...")
                # Fallback sur Selenium standard
                from selenium import webdriver
                service = Service()
                self.driver = webdriver.Chrome(service=service, options=options)
            
            # Configuration post-création
            self.driver.set_page_load_timeout(30)
            self.driver.implicitly_wait(5)
            
            # === TEST CONNECTIVITÉ ===
            self.logger.info("🧪 Testing Chrome stability...")
            try:
                self.driver.get("data:text/html,<html><body><h1>Test</h1></body></html>")
                time.sleep(1)
                title = self.driver.title
                self.logger.info("✅ Chrome driver is stable and responsive")
            except Exception as e:
                self.logger.warning(f"Chrome stability test failed: {e}")
                raise
            
            # === TEST RÉSEAU (si pas en test mode) ===
            if not self.test_mode:
                try:
                    self.driver.get("https://httpbin.org/ip")
                    time.sleep(2)
                    ip_info = json.loads(self.driver.find_element(By.TAG_NAME, "pre").text)
                    ip = ip_info.get('origin', 'unknown')
                    self.logger.info(f"✅ Network test passed! IP: {ip}")
                except Exception as e:
                    self.logger.warning(f"⚠️ Network test failed: {e}")
            
            self.driver_failures = 0  # Reset counter on success
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Driver setup failed: {e}")
            self.driver_failures += 1
            
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
                self.driver = None
            
            return False
    
    def ensure_driver_healthy(self):
        """S'assurer que le driver est en bon état"""
        if not self.driver:
            return self.setup_driver()
        
        try:
            # Test simple pour vérifier que le driver répond
            self.driver.current_url
            return True
        except (WebDriverException, Exception) as e:
            self.logger.warning(f"Driver health check failed: {e}")
            self.cleanup_driver()
            
            if self.driver_failures < self.max_driver_failures:
                self.logger.info("🔄 Attempting driver restart...")
                self.stats['driver_restarts'] += 1
                return self.setup_driver()
            else:
                self.logger.error(f"❌ Max driver failures reached ({self.max_driver_failures})")
                return False
    
    def cleanup_driver(self):
        """Nettoyer proprement le driver"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None
    
    def search_google_maps_real(self, search_query: str, company_name: str) -> Dict:
        """Recherche réelle sur Google Maps - pas de fallback"""
        result = {
            'website_url': None,
            'phone': None,
            'hasWebsite': False,
            'websiteSource': 'not_found'
        }
        
        try:
            if not self.ensure_driver_healthy():
                raise Exception("Driver not available")
            
            self.logger.info(f"🔍 Searching Google Maps: {search_query}")
            
            # URL Google Maps
            maps_url = f"https://www.google.com/maps/search/{quote_plus(search_query)}"
            
            try:
                self.driver.get(maps_url)
                time.sleep(random.uniform(2, 4))
                
                # Gestion cookies Google
                try:
                    cookie_selectors = [
                        "//button[contains(text(), 'Tout accepter')]",
                        "//button[contains(text(), 'Accept all')]",
                        "//button[@id='L2AGLb']",
                        "#L2AGLb"
                    ]
                    
                    for selector in cookie_selectors:
                        try:
                            if selector.startswith('#'):
                                button = self.driver.find_element(By.CSS_SELECTOR, selector)
                            else:
                                button = self.driver.find_element(By.XPATH, selector)
                            
                            if button.is_displayed():
                                button.click()
                                time.sleep(1)
                                self.logger.debug("✅ Cookies accepted")
                                break
                        except:
                            continue
                except Exception as e:
                    self.logger.debug(f"Cookie handling: {e}")
                
                # Attendre les résultats Maps
                try:
                    WebDriverWait(self.driver, 15).until(
                        EC.any_of(
                            EC.presence_of_element_located((By.CSS_SELECTOR, '[role="feed"]')),
                            EC.presence_of_element_located((By.CSS_SELECTOR, '[role="main"]')),
                            EC.presence_of_element_located((By.CSS_SELECTOR, '.Nv2PK'))
                        )
                    )
                    
                    # Chercher et cliquer sur le premier résultat
                    business_selectors = [
                        'a[href*="/maps/place/"]',
                        '[data-result-index="0"] a',
                        '.Nv2PK .hfpxzc',
                        'div[role="article"] a'
                    ]
                    
                    clicked = False
                    for selector in business_selectors:
                        try:
                            elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                            if elements:
                                first_element = elements[0]
                                self.driver.execute_script("arguments[0].click();", first_element)
                                time.sleep(random.uniform(2, 4))
                                clicked = True
                                self.logger.debug("✅ Clicked on business result")
                                break
                        except Exception as e:
                            self.logger.debug(f"Click attempt failed with {selector}: {e}")
                            continue
                    
                    if not clicked:
                        self.logger.warning("⚠️ Could not click on any business result")
                        return result
                    
                    # Extraire les données du business
                    time.sleep(random.uniform(1, 2))
                    
                    # === CHERCHER SITE WEB ===
                    website_selectors = [
                        'a[data-item-id="authority"]',
                        'a.lcr4fd',
                        'button[data-item-id="authority"]',
                        '[data-item-id="authority"] a',
                        'a[href*="http"]:not([href*="google.com"]):not([href*="maps"]):not([href*="youtube"])'
                    ]
                    
                    for selector in website_selectors:
                        try:
                            website_elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                            href = website_elem.get_attribute('href')
                            
                            if href and 'http' in href and self.is_valid_website(href):
                                result.update({
                                    'website_url': href,
                                    'hasWebsite': True,
                                    'websiteSource': 'google_maps'
                                })
                                self.logger.info(f"🌐 Website found: {href}")
                                break
                        except:
                            continue
                    
                    # === CHERCHER TÉLÉPHONE ===
                    phone_selectors = [
                        'button[data-item-id^="phone:tel:"]',
                        '[data-item-id^="phone"] span',
                        'button[aria-label*="téléphone"]',
                        'span[dir="ltr"]'
                    ]
                    
                    for selector in phone_selectors:
                        try:
                            phone_elems = self.driver.find_elements(By.CSS_SELECTOR, selector)
                            for phone_elem in phone_elems:
                                phone_text = phone_elem.text.strip()
                                
                                # Si pas de texte, essayer data-item-id
                                if not phone_text and 'data-item-id' in phone_elem.get_attribute('outerHTML'):
                                    phone_id = phone_elem.get_attribute('data-item-id')
                                    if 'tel:' in phone_id:
                                        phone_text = phone_id.split('tel:')[1]
                                
                                # Validation numéro français
                                if phone_text and self.is_valid_french_phone(phone_text):
                                    result['phone'] = phone_text
                                    self.logger.info(f"📞 Phone found: {phone_text}")
                                    break
                            
                            if result.get('phone'):
                                break
                        except:
                            continue
                    
                except TimeoutException:
                    self.logger.warning(f"⚠️ Timeout waiting for Maps results: {search_query}")
                    return result
                    
            except Exception as e:
                self.logger.error(f"❌ Maps search error: {e}")
                return result
                
        except Exception as e:
            self.logger.error(f"❌ Critical Maps search error: {e}")
            return result
        
        return result
    
    def is_valid_website(self, url: str) -> bool:
        """Valider qu'une URL est un vrai site d'entreprise"""
        if not url or not url.startswith('http'):
            return False
        
        exclude_domains = [
            'facebook.com', 'linkedin.com', 'instagram.com', 'twitter.com',
            'pagesjaunes.fr', 'societe.com', 'verif.com', 'infogreffe.fr',
            'pappers.fr', 'score3.fr', 'mappy.com', 'yelp.fr',
            'tripadvisor.fr', 'leboncoin.fr', 'youtube.com', 'wikipedia.org',
            'google.com', 'maps.google.com'
        ]
        
        url_lower = url.lower()
        for domain in exclude_domains:
            if domain in url_lower:
                return False
        
        return True
    
    def is_valid_french_phone(self, phone: str) -> bool:
        """Valider un numéro de téléphone français"""
        if not phone:
            return False
        
        # Nettoyer le numéro
        clean_phone = re.sub(r'[^\d+]', '', phone)
        
        # Patterns français
        patterns = [
            r'^0[1-9]\d{8}$',      # 01 23 45 67 89
            r'^\+33[1-9]\d{8}$',   # +33 1 23 45 67 89
            r'^33[1-9]\d{8}$',     # 33 1 23 45 67 89
        ]
        
        for pattern in patterns:
            if re.match(pattern, clean_phone):
                return True
        
        return False
    
    def search_company_website(self, company: Dict) -> Dict:
        """Rechercher le site web d'une entreprise - VRAIES DONNÉES SEULEMENT"""
        result = {
            **company,
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
            
            company_name = company.get('searchName', 'Unknown')
            
            # RECHERCHE GOOGLE MAPS RÉELLE
            maps_result = self.search_google_maps_real(search_query, company_name)
            
            # Fusionner les résultats
            result.update(maps_result)
            
            # Statistiques
            self.stats['processed'] += 1
            if result['hasWebsite']:
                self.stats['with_website'] += 1
            if result.get('phone'):
                self.stats['with_phone'] += 1
                
        except Exception as e:
            self.logger.error(f"❌ Error searching {company.get('searchName')}: {e}")
            result['error'] = str(e)
            self.stats['errors'] += 1
        
        return result
    
    def process_batch(self, companies: List[Dict]) -> List[Dict]:
        """Traiter un batch d'entreprises - VRAIES DONNÉES SEULEMENT"""
        results = []
        
        self.stats['total_companies'] = len(companies)
        self.logger.info(f"🚀 Starting REAL scraping batch: {len(companies)} companies")
        
        try:
            for i, company in enumerate(companies, 1):
                try:
                    company_name = company.get('searchName', f'Company_{i}')
                    self.logger.info(f"📋 Processing {i}/{len(companies)}: {company_name}")
                    
                    result = self.search_company_website(company)
                    results.append(result)
                    
                    # Délai entre recherches pour éviter détection
                    if i < len(companies):
                        delay = random.uniform(2, 5)
                        time.sleep(delay)
                    
                except Exception as e:
                    self.logger.error(f"❌ Error processing company {i}: {e}")
                    
                    # Ajouter résultat d'erreur (pas de fallback)
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
            self.cleanup_driver()
        
        # Statistiques finales
        self.logger.info(f"📊 REAL SCRAPING COMPLETED:")
        self.logger.info(f"  📋 Processed: {self.stats['processed']}/{self.stats['total_companies']}")
        self.logger.info(f"  🌐 Websites found: {self.stats['with_website']}")
        self.logger.info(f"  📞 Phones found: {self.stats['with_phone']}")
        self.logger.info(f"  🔄 Driver restarts: {self.stats['driver_restarts']}")
        self.logger.info(f"  ❌ Errors: {self.stats['errors']}")
        
        return results

def main():
    parser = argparse.ArgumentParser(description='Robust Website Finder for Naosite - Real Data Only')
    
    # Mode batch
    parser.add_argument('--batch-mode', action='store_true', help='Process multiple companies from stdin JSON')
    parser.add_argument('--find-websites-only', action='store_true', help='Only find websites, do not analyze quality')
    
    # Options
    parser.add_argument('--session-id', help='Session ID for tracking')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--no-proxy', action='store_true', help='Disable proxy (for testing)')
    parser.add_argument('--test-mode', action='store_true', help='Enable test mode (limit processing)')
    
    # Argument query pour compatibilité
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
            
            # Traitement batch RÉEL
            finder = RobustWebsiteFinder(
                session_id=args.session_id,
                debug=args.debug,
                use_proxy=not args.no_proxy,
                test_mode=args.test_mode
            )
            
            results = finder.process_batch(companies)
            
            # Output : une ligne JSON par entreprise
            logging.info("📤 Outputting real scraped results...")
            for result in results:
                print(json.dumps(result, ensure_ascii=False))
                
            if args.debug:
                logging.info(f"✅ Real scraping completed: {len(results)} results")
        
        else:
            # Mode simple query (pour compatibilité)
            logging.error("❌ Single query mode not implemented in batch version")
            sys.exit(1)
            
    except Exception as e:
        logging.error(f"❌ Real scraping batch failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
