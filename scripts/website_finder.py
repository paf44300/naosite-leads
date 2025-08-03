#!/usr/bin/env python3
"""
Website Finder - Compatible avec arguments n8n directs
Lit les données directement depuis les arguments de ligne de commande
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

# ✅ FONCTION POUR LOGS VISIBLES DANS N8N
def log_to_n8n(message, level="INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    formatted_message = f"[{timestamp}] {level}: {message}"
    print(formatted_message, file=sys.stderr, flush=True)

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
        
        # ✅ CONFIGURATION WEBSHARE ROTATING PROXY
        self.proxy_domain = "p.webshare.io"
        self.proxy_port = "80"
        self.proxy_username = "xftpfnvt-rotate"
        self.proxy_password = "yulnmnbiq66j"
        
        # ✅ FORMAT ROTATING PROXY ENDPOINT
        self.proxy_url = f"http://{self.proxy_username}:{self.proxy_password}@{self.proxy_domain}:{self.proxy_port}"
        
        self.driver = None
        self.driver_initialized = False
        
        # Timeouts
        self.max_search_time = 15
        self.batch_timeout = 600
        
    def setup_driver_once(self):
        """Configure le driver Chrome avec Webshare Rotating Proxy"""
        if self.driver_initialized:
            return True
            
        try:
            log_to_n8n("🚀 Initializing Chrome with Webshare rotating proxy...")
            
            options = uc.ChromeOptions()
            
            # ✅ CONFIGURATION WEBSHARE ROTATING PROXY
            options.add_argument(f'--proxy-server={self.proxy_url}')
            log_to_n8n(f"🌐 Using Webshare rotating proxy: {self.proxy_domain}:{self.proxy_port}")
            log_to_n8n(f"👤 Username: {self.proxy_username}")
            
            # Options optimisées
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-web-security')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--disable-extensions')
            options.add_argument('--disable-plugins')
            options.add_argument('--disable-images')
            options.add_argument('--window-size=1280,720')
            options.add_argument('--lang=fr-FR')
            
            if self.headless:
                options.add_argument('--headless=new')
            
            options.add_argument('--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            # ✅ CRÉER LE DRIVER
            log_to_n8n("⚙️ Creating Chrome instance...")
            self.driver = uc.Chrome(options=options, version_main=None)
            
            # Configuration timeouts
            self.driver.set_page_load_timeout(15)
            self.driver.implicitly_wait(8)
            
            # Anti-détection
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            # ✅ TEST DE CONNECTIVITÉ AVEC PROXY
            log_to_n8n("🧪 Testing proxy connectivity...")
            
            # Test httpbin pour voir l'IP
            self.driver.get("https://httpbin.org/ip")
            time.sleep(3)
            
            try:
                body_text = self.driver.find_element(By.TAG_NAME, "body").text
                if "origin" in body_text:
                    log_to_n8n(f"✅ Proxy working! IP: {body_text}")
                else:
                    log_to_n8n(f"⚠️ Unexpected response: {body_text}")
            except:
                log_to_n8n("⚠️ Could not get IP info")
            
            # Test Google France
            log_to_n8n("🧪 Testing Google France access...")
            self.driver.get("https://www.google.fr")
            time.sleep(2)
            
            title = self.driver.title
            if "Google" in title:
                log_to_n8n(f"✅ Google accessible via proxy: {title}")
                self.driver_initialized = True
                
                self.accept_google_cookies_once()
                return True
            else:
                log_to_n8n(f"❌ Unexpected Google response: {title}", "ERROR")
                return False
                
        except Exception as e:
            log_to_n8n(f"❌ Driver setup failed: {e}", "ERROR")
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
                "#L2AGLb"
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
                    log_to_n8n("✅ Google cookies accepted")
                    time.sleep(2)
                    return
                except:
                    continue
        except Exception as e:
            log_to_n8n(f"ℹ️ No cookie popup found")

    def search_single_company(self, search_query: str, company_name: str, company_index: int, total_companies: int) -> Dict:
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
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(self.max_search_time)
            
            log_to_n8n(f"🔍 ({company_index + 1}/{total_companies}) {company_name}")
            
            website_url, phone = self.search_maps_with_existing_driver(search_query)
            
            if website_url or phone:
                result.update({
                    'website_url': website_url,
                    'phone': phone,
                    'source': 'google_maps',
                    'found_at': datetime.now().isoformat()
                })
                status = f"✅ Found: {website_url or 'No site'}"
                if phone:
                    status += f" / {phone}"
                log_to_n8n(f"   {status}")
            else:
                result['source'] = 'not_found'
                log_to_n8n(f"   ❌ Nothing found")
                
        except TimeoutError:
            result['error'] = f'Search timeout ({self.max_search_time}s)'
            log_to_n8n(f"   ⏰ Timeout ({self.max_search_time}s)", "WARNING")
        except Exception as e:
            result['error'] = str(e)
            log_to_n8n(f"   ❌ Error: {e}", "ERROR")
        finally:
            signal.alarm(0)
            result['processing_time'] = round(time.time() - start_time, 2)
            
            if company_index < total_companies - 1:
                delay = random.uniform(3, 6)
                log_to_n8n(f"   ⏱️ Waiting {delay:.1f}s for IP rotation...")
                time.sleep(delay)
                
        return result

    def search_maps_with_existing_driver(self, search_query: str) -> Tuple[Optional[str], Optional[str]]:
        """Recherche Maps avec rotation automatique"""
        website_url = None
        phone = None
        
        try:
            search_url = f"https://www.google.com/maps/search/{quote_plus(search_query)}"
            
            self.driver.get(search_url)
            time.sleep(random.uniform(3, 5))
            
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '[role="feed"], .section-result'))
                )
            except TimeoutException:
                return None, None
            
            # Cliquer premier résultat
            first_result_selectors = [
                '[role="feed"] a[href*="/maps/place/"]:first-child',
                'a[href*="/maps/place/"]:first-of-type'
            ]
            
            clicked = False
            for selector in first_result_selectors:
                try:
                    first_result = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", first_result)
                    time.sleep(1)
                    first_result.click()
                    time.sleep(3)
                    clicked = True
                    break
                except:
                    continue
            
            if not clicked:
                return None, None
            
            # Chercher site web
            website_selectors = [
                'a[data-item-id="authority"]',
                'a.lcr4fd',
                'a[href*="http"]:not([href*="google.com"]):not([href*="maps"])'
            ]
            
            for selector in website_selectors:
                try:
                    website_elem = WebDriverWait(self.driver, 4).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    href = website_elem.get_attribute('href')
                    if href and 'http' in href and 'google' not in href:
                        website_url = href
                        break
                except:
                    continue
            
            # Chercher téléphone
            phone_selectors = [
                'button[data-item-id^="phone:tel:"]',
                '[data-item-id^="phone"] span'
            ]
            
            for selector in phone_selectors:
                try:
                    phone_elem = WebDriverWait(self.driver, 4).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    
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
                    
        except Exception as e:
            pass
            
        return website_url, phone

    def is_valid_french_phone(self, phone: str) -> bool:
        """Valide numéro français"""
        if not phone or len(phone) < 10:
            return False
        
        clean_phone = re.sub(r'[^\d+]', '', phone)
        return bool(re.match(r'^(0[1-9]|\+33[1-9]|33[1-9])\d{8}$', clean_phone))
    
    def process_batch(self, companies_data: list) -> list:
        """Traite tout le batch avec rotation IP automatique"""
        
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(self.batch_timeout)
        
        try:
            total_companies = len(companies_data)
            log_to_n8n(f"🚀 Starting batch: {total_companies} companies")
            log_to_n8n(f"🔄 Using Webshare rotating proxy (new IP per request)")
            
            if not self.setup_driver_once():
                raise Exception("Failed to initialize Chrome with Webshare proxy")
            
            results = []
            start_time = time.time()
            
            for i, company in enumerate(companies_data):
                query = company.get('searchQuery', '')
                company_name = company.get('searchName', 'Unknown')
                
                if not query:
                    continue
                
                result = self.search_single_company(query, company_name, i, total_companies)
                
                enhanced_result = {
                    **result,
                    **{k: v for k, v in company.items() if k != 'searchQuery'},
                    'hasWebsite': bool(result.get('website_url')),
                    'websiteSource': result.get('source', 'not_found')
                }
                
                results.append({k: v for k, v in enhanced_result.items() if v is not None})
            
            # Stats finales
            batch_time = time.time() - start_time
            with_website = sum(1 for r in results if r.get('hasWebsite'))
            with_phone = sum(1 for r in results if r.get('phone'))
            errors = sum(1 for r in results if r.get('error'))
            
            log_to_n8n(f"📊 BATCH COMPLETE in {batch_time:.1f}s:")
            log_to_n8n(f"   • {len(results)}/{total_companies} processed")
            log_to_n8n(f"   • {with_website} websites found")
            log_to_n8n(f"   • {with_phone} phones found")
            log_to_n8n(f"   • {errors} errors")
            
            return results
            
        except TimeoutError:
            log_to_n8n(f"⏰ BATCH TIMEOUT ({self.batch_timeout}s)", "ERROR")
            return results if 'results' in locals() else []
        except Exception as e:
            log_to_n8n(f"❌ Batch failed: {e}", "ERROR")
            return results if 'results' in locals() else []
        finally:
            signal.alarm(0)
            if self.driver:
                try:
                    self.driver.quit()
                    log_to_n8n("🔚 Chrome driver closed")
                except:
                    pass

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Website Finder for n8n')
    
    # ✅ MODE n8n : Lire depuis argument ou stdin
    parser.add_argument('--data', help='JSON data as argument (for n8n)')
    parser.add_argument('--batch-mode', action='store_true', help='Process batch mode')
    parser.add_argument('--find-websites-only', action='store_true')
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--no-headless', action='store_true')
    
    args = parser.parse_args()
    
    try:
        log_to_n8n("📥 Reading input data...")
        
        # ✅ LIRE DONNÉES - De l'argument OU de stdin
        if args.data:
            # Mode argument (pour éviter les problèmes d'échappement)
            input_data = json.loads(args.data)
            log_to_n8n("📊 Data loaded from argument")
        else:
            # Mode stdin (ancien)
            input_text = sys.stdin.read().strip()
            if not input_text:
                log_to_n8n("❌ No input data provided", "ERROR")
                sys.exit(1)
            input_data = json.loads(input_text)
            log_to_n8n("📊 Data loaded from stdin")
        
        if not isinstance(input_data, list):
            input_data = [input_data]
        
        log_to_n8n(f"📋 Loaded {len(input_data)} companies")
        
        # Créer le finder
        finder = BatchWebsiteFinder(
            debug=args.debug,
            headless=not args.no_headless
        )
        
        log_to_n8n("✅ Using configured Webshare rotating proxy")
        
        # Traiter le batch
        results = finder.process_batch(input_data)
        
        log_to_n8n(f"📤 Outputting {len(results)} results...")
        
        # Output pour n8n
        for result in results:
            print(json.dumps(result, ensure_ascii=False))
            
    except Exception as e:
        log_to_n8n(f"💀 Fatal error: {e}", "ERROR")
        print(json.dumps({'error': f'Fatal error: {e}'}, ensure_ascii=False))
        sys.exit(1)

if __name__ == "__main__":
    main()
