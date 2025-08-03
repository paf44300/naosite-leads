#!/usr/bin/env python3
"""
Website Finder pour Naosite - Avec timeouts et debug
Version ultra-robuste pour éviter les blocages
"""

import json
import time
import argparse
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

class WebsiteFinder:
    def __init__(self, session_id: str = None, debug: bool = False, headless: bool = True):
        if not SELENIUM_AVAILABLE:
            raise ImportError("Please install: pip install undetected-chromedriver selenium")
            
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
        
        # ✅ TIMEOUTS STRICTS
        self.max_search_time = 30  # 30 secondes max par entreprise
        self.driver_timeout = 15   # 15 secondes pour les éléments
        
    def setup_logging(self):
        level = logging.DEBUG if self.debug else logging.INFO
        logging.basicConfig(
            level=level,
            format=f'[{self.session_id}] %(levelname)s: %(message)s',
            stream=sys.stderr
        )
        self.logger = logging.getLogger(__name__)
    
    def setup_driver(self):
        """Configure Chrome avec proxy et timeouts stricts"""
        try:
            options = uc.ChromeOptions()
            
            # ✅ CONFIGURATION PROXY
            proxy_string = f"{self.proxy_user}:{self.proxy_pass}@{self.proxy_host}:{self.proxy_port}"
            options.add_argument(f'--proxy-server=http://{proxy_string}')
            
            # ✅ OPTIONS OPTIMISÉES POUR VITESSE
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-web-security')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--disable-extensions')
            options.add_argument('--disable-plugins')
            options.add_argument('--disable-images')  # ✅ Plus rapide sans images
            options.add_argument('--disable-javascript')  # ✅ Plus rapide sans JS complexe
            options.add_argument('--window-size=1280,720')  # ✅ Plus petit
            options.add_argument('--lang=fr-FR')
            
            # ✅ TIMEOUTS RÉSEAU STRICTS
            options.add_argument('--page-load-strategy=eager')
            options.add_argument('--timeout=10')
            
            if self.headless:
                options.add_argument('--headless=new')
            
            # User agent français léger
            options.add_argument('--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36')
            
            # ✅ CRÉER DRIVER AVEC TIMEOUT
            self.driver = uc.Chrome(options=options, version_main=None)
            
            # ✅ TIMEOUTS STRICTS
            self.driver.set_page_load_timeout(10)  # 10 sec max pour charger
            self.driver.implicitly_wait(5)         # 5 sec max pour trouver éléments
            
            # Anti-détection minimal
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            self.logger.info("✅ Chrome driver ready with strict timeouts")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Driver setup failed: {e}")
            return False

    def extract_website_and_phone_from_maps(self, search_query: str) -> Tuple[Optional[str], Optional[str]]:
        """Cherche site web ET téléphone avec timeout strict"""
        website_url = None
        phone = None
        
        try:
            # ✅ TIMEOUT GLOBAL pour cette fonction
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(20)  # 20 secondes MAX
            
            search_url = f"https://www.google.com/maps/search/{quote_plus(search_query)}"
            self.logger.info(f"🗺️ Searching Maps: {search_url}")
            
            self.driver.get(search_url)
            time.sleep(2)  # ✅ Délai réduit
            
            # ✅ ACCEPTER COOKIES RAPIDEMENT
            try:
                accept_button = WebDriverWait(self.driver, 3).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Tout accepter')]"))
                )
                accept_button.click()
                time.sleep(1)
                self.logger.debug("✅ Cookies accepted")
            except:
                self.logger.debug("⚠️ No cookies popup")
            
            # ✅ CHERCHER PREMIER RÉSULTAT
            try:
                first_result = WebDriverWait(self.driver, 8).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, '[role="feed"] a[href*="/maps/place/"]'))
                )
                first_result.click()
                time.sleep(2)
                self.logger.debug("✅ First result clicked")
                
                # ✅ SITE WEB - RECHERCHE RAPIDE
                website_selectors = [
                    'a[data-item-id="authority"]',
                    'a.lcr4fd',
                    'a[href*="http"]:not([href*="google.com"]):not([href*="maps"])'
                ]
                
                for selector in website_selectors:
                    try:
                        website_elem = WebDriverWait(self.driver, 2).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                        )
                        href = website_elem.get_attribute('href')
                        if href and 'http' in href and 'google' not in href:
                            website_url = href
                            self.logger.info(f"🌐 Website found: {href}")
                            break
                    except:
                        continue
                
                # ✅ TÉLÉPHONE - RECHERCHE RAPIDE
                phone_selectors = [
                    'button[data-item-id^="phone:tel:"]',
                    '[data-item-id^="phone"] span'
                ]
                
                for selector in phone_selectors:
                    try:
                        phone_elem = WebDriverWait(self.driver, 2).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                        )
                        phone_text = phone_elem.text.strip()
                        
                        if not phone_text and 'data-item-id' in phone_elem.get_attribute('outerHTML'):
                            phone_id = phone_elem.get_attribute('data-item-id')
                            if 'tel:' in phone_id:
                                phone_text = phone_id.split('tel:')[1]
                        
                        if phone_text and self.is_valid_french_phone(phone_text):
                            phone = phone_text
                            self.logger.info(f"📞 Phone found: {phone}")
                            break
                    except:
                        continue
                        
            except TimeoutException:
                self.logger.warning("⚠️ No Maps results found quickly")
                
        except TimeoutError:
            self.logger.error("⏰ Maps search TIMEOUT (20s)")
        except Exception as e:
            self.logger.error(f"❌ Maps search error: {e}")
        finally:
            signal.alarm(0)  # ✅ Annuler timeout
            
        return website_url, phone

    def is_valid_french_phone(self, phone: str) -> bool:
        """Valide un numéro français rapidement"""
        if not phone or len(phone) < 10:
            return False
        
        clean_phone = re.sub(r'[^\d+]', '', phone)
        return bool(re.match(r'^(0[1-9]|\\+33[1-9]|33[1-9])\\d{8}$', clean_phone))
    
    def find_website(self, search_query: str) -> Dict:
        """Fonction principale avec timeout global"""
        start_time = time.time()
        result = {
            'search_query': search_query,
            'website_url': None,
            'phone': None,
            'source': None,
            'found_at': None,
            'session_id': self.session_id,
            'processing_time': 0
        }
        
        try:
            # ✅ TIMEOUT GLOBAL PER COMPANY
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(self.max_search_time)
            
            if not self.setup_driver():
                result['error'] = 'Driver setup failed'
                return result
            
            self.logger.info(f"🔍 Searching: {search_query}")
            
            # ✅ MAPS SEULEMENT (pour l'instant)
            website_url, phone = self.extract_website_and_phone_from_maps(search_query)
            
            if website_url or phone:
                result.update({
                    'website_url': website_url,
                    'phone': phone,
                    'source': 'google_maps',
                    'found_at': datetime.now().isoformat()
                })
                self.logger.info(f"✅ Found: {website_url or 'No website'} / {phone or 'No phone'}")
            else:
                result['source'] = 'not_found'
                self.logger.info("❌ Nothing found")
                
        except TimeoutError:
            result['error'] = f'Search timeout ({self.max_search_time}s)'
            self.logger.error(f"⏰ TIMEOUT after {self.max_search_time}s")
        except Exception as e:
            result['error'] = str(e)
            self.logger.error(f"❌ Search failed: {e}")
        finally:
            signal.alarm(0)  # ✅ Annuler timeout
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
            
            # ✅ TEMPS DE TRAITEMENT
            result['processing_time'] = round(time.time() - start_time, 2)
                
        return result

def main():
    parser = argparse.ArgumentParser(description='Website Finder - Fast & Robust')
    parser.add_argument('--batch-mode', action='store_true')
    parser.add_argument('--find-websites-only', action='store_true')
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--no-headless', action='store_true')
    parser.add_argument('--max-companies', type=int, default=25, help='Max companies to process')
    
    args = parser.parse_args()
    
    try:
        if args.batch_mode:
            input_text = sys.stdin.read().strip()
            
            try:
                input_data = json.loads(input_text)
                if not isinstance(input_data, list):
                    input_data = [input_data]
            except json.JSONDecodeError as e:
                print(json.dumps({'error': f'Invalid JSON: {e}'}, ensure_ascii=False))
                sys.exit(1)
            
            # ✅ LIMITER LE NOMBRE (pour éviter les timeouts)
            input_data = input_data[:args.max_companies]
            total = len(input_data)
            
            logging.info(f"🚀 Starting batch processing: {total} companies (max {args.max_companies})")
            
            results = []
            for i, item in enumerate(input_data):
                query = item.get('searchQuery', '')
                if not query:
                    continue
                
                try:
                    logging.info(f"📋 Processing ({i+1}/{total}): {item.get('searchName', query)}")
                    
                    # ✅ CRÉER NOUVELLE INSTANCE POUR CHAQUE RECHERCHE
                    finder = WebsiteFinder(
                        session_id=f"batch_{i}",
                        debug=args.debug,
                        headless=not args.no_headless
                    )
                    
                    result = finder.find_website(query)
                    
                    # Enrichir avec données originales
                    enhanced_result = {
                        **result,
                        **{k: v for k, v in item.items() if k != 'searchQuery'},
                        'hasWebsite': bool(result.get('website_url')),
                        'websiteSource': result.get('source', 'not_found'),
                        'batch_position': i + 1,
                        'batch_total': total
                    }
                    
                    results.append({k: v for k, v in enhanced_result.items() if v is not None})
                    
                    # ✅ DÉLAI ENTRE RECHERCHES
                    if i < total - 1:
                        time.sleep(random.uniform(1, 3))
                    
                except Exception as e:
                    error_result = {
                        **item,
                        'website_url': None,
                        'phone': None,
                        'source': 'error',
                        'error': str(e),
                        'hasWebsite': False,
                        'processing_time': 0
                    }
                    results.append(error_result)
                    logging.error(f"❌ Error ({i+1}/{total}): {e}")
            
            # ✅ OUTPUT RÉSULTATS
            for result in results:
                print(json.dumps(result, ensure_ascii=False))
                
            # ✅ STATS FINALES
            total_time = sum(r.get('processing_time', 0) for r in results)
            with_website = sum(1 for r in results if r.get('hasWebsite'))
            with_phone = sum(1 for r in results if r.get('phone'))
            
            logging.info(f"📊 BATCH COMPLETE:")
            logging.info(f"   • {len(results)} processed in {total_time:.1f}s")
            logging.info(f"   • {with_website} websites found")
            logging.info(f"   • {with_phone} phones found")
            logging.info(f"   • Avg {total_time/len(results):.1f}s per company")
                
        else:
            print("Batch mode only")
            sys.exit(1)
            
    except Exception as e:
        print(json.dumps({'error': f'Fatal error: {e}'}, ensure_ascii=False))
        logging.error(f"💀 Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
