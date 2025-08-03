#!/usr/bin/env python3
"""
Website Finder - Mode Batch Optimisé
UN SEUL driver Chrome pour toutes les recherches du batch
"""

import json
import time
import sys
import logging
import re
import signal
from typing import Optional, Dict, Tuple
import random
from datetime import datetime
from urllib.parse import quote_plus

try:
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

class TimeoutError(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutError("Operation timed out")

class BatchWebsiteFinder:
    def __init__(self, session_id: str = None, debug: bool = False, headless: bool = True):
        if not SELENIUM_AVAILABLE:
            raise ImportError("Please install: pip install undetected-chromedriver selenium")
            
        self.session_id = session_id or f"batch_{int(time.time())}"
        self.debug = debug
        self.headless = headless
        self.setup_logging()
        
        # Configuration proxy Webshare
        self.proxy_host = "p.webshare.io"
        self.proxy_port = "80"
        self.proxy_user = "xftpfnvt-rotate"
        self.proxy_pass = "yulnmnbiq66j"
        
        # ✅ UN SEUL DRIVER POUR TOUT LE BATCH
        self.driver = None
        self.driver_initialized = False
        
        # Timeouts optimisés
        self.max_search_time = 15  # 15 sec max par entreprise
        self.batch_timeout = 600   # 10 minutes max pour tout le batch
        
    def setup_logging(self):
        level = logging.DEBUG if self.debug else logging.INFO
        logging.basicConfig(
            level=level,
            format=f'[{self.session_id}] %(levelname)s: %(message)s',
            stream=sys.stderr
        )
        self.logger = logging.getLogger(__name__)
    
    def setup_driver_once(self):
        """Configure le driver Chrome UNE SEULE FOIS pour tout le batch"""
        if self.driver_initialized:
            return True
            
        try:
            self.logger.info("🚀 Initializing Chrome driver for entire batch...")
            
            options = uc.ChromeOptions()
            
            # ✅ CONFIGURATION PROXY WEBSHARE
            proxy_string = f"{self.proxy_user}:{self.proxy_pass}@{self.proxy_host}:{self.proxy_port}"
            options.add_argument(f'--proxy-server=http://{proxy_string}')
            self.logger.info(f"🌐 Using proxy: {self.proxy_host}:{self.proxy_port}")
            
            # Options optimisées pour vitesse et stabilité
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-web-security')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--disable-extensions')
            options.add_argument('--disable-plugins')
            options.add_argument('--disable-images')  # Plus rapide
            options.add_argument('--window-size=1280,720')
            options.add_argument('--lang=fr-FR')
            
            # Mode headless
            if self.headless:
                options.add_argument('--headless=new')
            
            # User agent français
            options.add_argument('--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            # ✅ CRÉER LE DRIVER
            self.driver = uc.Chrome(options=options, version_main=None)
            
            # Configuration timeouts
            self.driver.set_page_load_timeout(15)
            self.driver.implicitly_wait(8)
            
            # Anti-détection
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            # ✅ TEST DE CONNECTIVITÉ
            self.logger.info("🧪 Testing Google connectivity...")
            self.driver.get("https://www.google.fr")
            time.sleep(2)
            
            title = self.driver.title
            if "Google" in title:
                self.logger.info(f"✅ Google accessible via proxy: {title}")
                self.driver_initialized = True
                
                # ✅ ACCEPTER LES COOKIES UNE FOIS POUR TOUTES
                self.accept_google_cookies_once()
                return True
            else:
                self.logger.error(f"❌ Unexpected Google response: {title}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Driver setup failed: {e}")
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
                self.driver = None
            return False
    
    def accept_google_cookies_once(self):
        """Accepte les cookies Google une seule fois"""
        try:
            cookie_selectors = [
                "//button[contains(text(), 'Tout accepter')]",
                "//button[contains(text(), 'Accept all')]",
                "#L2AGLb",
                ".QS5gu"
            ]
            
            for selector in cookie_selectors:
                try:
                    if selector.startswith('//'):
                        accept_button = WebDriverWait(self.driver, 3).until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                    else:
                        accept_button = WebDriverWait(self.driver, 3).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                        )
                    accept_button.click()
                    self.logger.info("✅ Google cookies accepted globally")
                    time.sleep(2)
                    return
                except:
                    continue
                    
        except Exception as e:
            self.logger.debug(f"ℹ️ No cookie popup: {e}")

    def search_single_company(self, search_query: str, company_index: int, total_companies: int) -> Dict:
        """Recherche UNE entreprise avec le driver existant"""
        start_time = time.time()
        result = {
            'search_query': search_query,
            'website_url': None,
            'phone': None,
            'source': None,
            'found_at': None,
            'session_id': self.session_id,
            'processing_time': 0,
            'batch_position': company_index + 1,
            'batch_total': total_companies
        }
        
        try:
            # ✅ TIMEOUT PAR RECHERCHE
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(self.max_search_time)
            
            self.logger.info(f"🔍 ({company_index + 1}/{total_companies}) Searching: {search_query}")
            
            # ✅ RECHERCHE MAPS AVEC DRIVER EXISTANT
            website_url, phone = self.search_maps_with_existing_driver(search_query)
            
            if website_url or phone:
                result.update({
                    'website_url': website_url,
                    'phone': phone,
                    'source': 'google_maps',
                    'found_at': datetime.now().isoformat()
                })
                self.logger.info(f"✅ ({company_index + 1}/{total_companies}) Found: {website_url or 'No site'} / {phone or 'No phone'}")
            else:
                result['source'] = 'not_found'
                self.logger.info(f"❌ ({company_index + 1}/{total_companies}) Nothing found")
                
        except TimeoutError:
            result['error'] = f'Search timeout ({self.max_search_time}s)'
            self.logger.warning(f"⏰ ({company_index + 1}/{total_companies}) Timeout")
        except Exception as e:
            result['error'] = str(e)
            self.logger.error(f"❌ ({company_index + 1}/{total_companies}) Error: {e}")
        finally:
            signal.alarm(0)
            result['processing_time'] = round(time.time() - start_time, 2)
            
            # ✅ DÉLAI ENTRE RECHERCHES (important pour éviter rate limiting)
            if company_index < total_companies - 1:
                delay = random.uniform(2, 4)
                self.logger.debug(f"⏱️ Waiting {delay:.1f}s before next search...")
                time.sleep(delay)
                
        return result

    def search_maps_with_existing_driver(self, search_query: str) -> Tuple[Optional[str], Optional[str]]:
        """Recherche Maps avec le driver déjà initialisé"""
        website_url = None
        phone = None
        
        try:
            search_url = f"https://www.google.com/maps/search/{quote_plus(search_query)}"
            self.logger.debug(f"🗺️ Maps URL: {search_url}")
            
            # ✅ NAVIGATION
            self.driver.get(search_url)
            time.sleep(random.uniform(2, 4))
            
            # ✅ ATTENDRE LES RÉSULTATS
            try:
                # Attendre que le feed de résultats soit présent
                WebDriverWait(self.driver, 8).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '[role="feed"], .section-result'))
                )
                self.logger.debug("✅ Results container found")
            except TimeoutException:
                self.logger.debug("⚠️ No results container found")
                return None, None
            
            # ✅ CLIQUER SUR PREMIER RÉSULTAT
            first_result_selectors = [
                '[role="feed"] a[href*="/maps/place/"]:first-child',
                'a[href*="/maps/place/"]:first-of-type',
                '.section-result:first-child a'
            ]
            
            clicked = False
            for selector in first_result_selectors:
                try:
                    first_result = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    
                    # Scroll vers l'élément si nécessaire
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", first_result)
                    time.sleep(1)
                    
                    first_result.click()
                    self.logger.debug(f"✅ Clicked result with: {selector}")
                    time.sleep(3)
                    clicked = True
                    break
                except Exception as e:
                    self.logger.debug(f"⚠️ Selector {selector} failed: {e}")
                    continue
            
            if not clicked:
                self.logger.debug("❌ Could not click any result")
                return None, None
            
            # ✅ EXTRAIRE SITE WEB
            website_selectors = [
                'a[data-item-id="authority"]',
                'a.lcr4fd',
                'a[href*="http"]:not([href*="google.com"]):not([href*="maps"])',
                '[data-item-id="authority"] span'
            ]
            
            for selector in website_selectors:
                try:
                    website_elem = WebDriverWait(self.driver, 3).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    href = website_elem.get_attribute('href')
                    if href and 'http' in href and 'google' not in href:
                        website_url = href
                        self.logger.debug(f"🌐 Website: {href}")
                        break
                except:
                    continue
            
            # ✅ EXTRAIRE TÉLÉPHONE
            phone_selectors = [
                'button[data-item-id^="phone:tel:"]',
                '[data-item-id^="phone"] span',
                'span[role="img"][aria-label*="téléphone"]'
            ]
            
            for selector in phone_selectors:
                try:
                    phone_elem = WebDriverWait(self.driver, 3).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    
                    phone_text = phone_elem.text.strip()
                    if not phone_text and 'data-item-id' in phone_elem.get_attribute('outerHTML'):
                        phone_id = phone_elem.get_attribute('data-item-id')
                        if 'tel:' in phone_id:
                            phone_text = phone_id.split('tel:')[1]
                    
                    if phone_text and self.is_valid_french_phone(phone_text):
                        phone = phone_text
                        self.logger.debug(f"📞 Phone: {phone}")
                        break
                except:
                    continue
                    
        except Exception as e:
            self.logger.debug(f"⚠️ Maps search error: {e}")
            
        return website_url, phone

    def is_valid_french_phone(self, phone: str) -> bool:
        """Valide numéro français"""
        if not phone or len(phone) < 10:
            return False
        
        clean_phone = re.sub(r'[^\d+]', '', phone)
        return bool(re.match(r'^(0[1-9]|\+33[1-9]|33[1-9])\d{8}$', clean_phone))
    
    def process_batch(self, companies_data: list) -> list:
        """Traite tout le batch avec UN SEUL driver"""
        
        # ✅ TIMEOUT GLOBAL DU BATCH
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(self.batch_timeout)
        
        try:
            total_companies = len(companies_data)
            self.logger.info(f"🚀 Starting batch: {total_companies} companies")
            
            # ✅ INITIALISER LE DRIVER UNE SEULE FOIS
            if not self.setup_driver_once():
                raise Exception("Failed to initialize Chrome driver")
            
            results = []
            start_time = time.time()
            
            # ✅ TRAITER CHAQUE ENTREPRISE SÉQUENTIELLEMENT
            for i, company in enumerate(companies_data):
                query = company.get('searchQuery', '')
                if not query:
                    continue
                
                # Recherche avec le driver existant
                result = self.search_single_company(query, i, total_companies)
                
                # Enrichir avec données originales
                enhanced_result = {
                    **result,
                    **{k: v for k, v in company.items() if k != 'searchQuery'},
                    'hasWebsite': bool(result.get('website_url')),
                    'websiteSource': result.get('source', 'not_found')
                }
                
                results.append({k: v for k, v in enhanced_result.items() if v is not None})
            
            # ✅ STATS FINALES
            batch_time = time.time() - start_time
            with_website = sum(1 for r in results if r.get('hasWebsite'))
            with_phone = sum(1 for r in results if r.get('phone'))
            errors = sum(1 for r in results if r.get('error'))
            
            self.logger.info(f"📊 BATCH COMPLETE in {batch_time:.1f}s:")
            self.logger.info(f"   • {len(results)}/{total_companies} processed")
            self.logger.info(f"   • {with_website} websites found")
            self.logger.info(f"   • {with_phone} phones found")
            self.logger.info(f"   • {errors} errors")
            self.logger.info(f"   • Avg {batch_time/len(results):.1f}s per company")
            
            return results
            
        except TimeoutError:
            self.logger.error(f"⏰ BATCH TIMEOUT ({self.batch_timeout}s)")
            return results if 'results' in locals() else []
        except Exception as e:
            self.logger.error(f"❌ Batch processing failed: {e}")
            return results if 'results' in locals() else []
        finally:
            signal.alarm(0)
            # ✅ FERMER LE DRIVER À LA FIN DU BATCH
            if self.driver:
                try:
                    self.driver.quit()
                    self.logger.info("🔚 Chrome driver closed")
                except:
                    pass

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Website Finder - Batch Mode Optimized')
    parser.add_argument('--batch-mode', action='store_true')
    parser.add_argument('--find-websites-only', action='store_true')
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--no-headless', action='store_true')
    
    args = parser.parse_args()
    
    try:
        if args.batch_mode:
            # ✅ LIRE INPUT
            input_text = sys.stdin.read().strip()
            input_data = json.loads(input_text)
            
            if not isinstance(input_data, list):
                input_data = [input_data]
            
            # ✅ CRÉER LE BATCH FINDER
            finder = BatchWebsiteFinder(
                debug=args.debug,
                headless=not args.no_headless
            )
            
            # ✅ TRAITER TOUT LE BATCH
            results = finder.process_batch(input_data)
            
            # ✅ OUTPUT POUR N8N
            for result in results:
                print(json.dumps(result, ensure_ascii=False))
                
        else:
            print("Batch mode only supported")
            sys.exit(1)
            
    except Exception as e:
        print(json.dumps({'error': f'Batch processing failed: {e}'}, ensure_ascii=False))
        logging.error(f"💀 Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
