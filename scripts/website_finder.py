#!/usr/bin/env python3
"""
Google Maps Scraper pour Naosite - Version corrigée pour Fly.io
Optimisé pour fonctionner dans les containers Docker avec Chrome headless
"""

import json
import time
import argparse
import sys
import logging
import re
from typing import List, Dict, Optional
import random
from datetime import datetime
from urllib.parse import quote_plus
import os
import subprocess

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

class GoogleMapsScraper:
    def __init__(self, session_id: str = None, debug: bool = False, use_proxy: bool = True):
        if not SELENIUM_AVAILABLE:
            raise ImportError("Please install: pip install undetected-chromedriver selenium")
            
        self.session_id = session_id or f"maps_{int(time.time())}"
        self.debug = debug
        self.use_proxy = use_proxy
        self.setup_logging()
        
        # Configuration proxy Webshare
        self.proxy_host = "p.webshare.io"
        self.proxy_port = "80"
        self.proxy_user = "xftpfnvt-rotate"
        self.proxy_pass = "yulnmnbiq66j"
        
        self.driver = None
        
    def setup_logging(self):
        level = logging.DEBUG if self.debug else logging.INFO
        logging.basicConfig(
            level=level,
            format=f'[{self.session_id}] %(levelname)s: %(message)s',
            stream=sys.stderr
        )
        self.logger = logging.getLogger(__name__)
    
    def check_chrome_installation(self):
        """Vérifie que Chrome est installé et accessible"""
        try:
            result = subprocess.run(['google-chrome', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                version = result.stdout.strip()
                self.logger.info(f"✅ Chrome found: {version}")
                return True
            else:
                self.logger.error("❌ Chrome not found or not working")
                return False
        except Exception as e:
            self.logger.error(f"❌ Chrome check failed: {e}")
            return False
    
    def setup_driver(self):
        """Configure Chrome avec options optimisées pour Docker/Fly.io"""
        try:
            self.logger.info("🚀 Initializing Chrome for container environment...")
            
            # Vérifier Chrome
            if not self.check_chrome_installation():
                raise Exception("Chrome not available")
            
            options = uc.ChromeOptions()
            
            # === OPTIONS DOCKER/FLY.IO CRITIQUES ===
            options.add_argument('--headless=new')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-software-rasterizer')
            options.add_argument('--disable-background-timer-throttling')
            options.add_argument('--disable-renderer-backgrounding')
            options.add_argument('--disable-backgrounding-occluded-windows')
            options.add_argument('--disable-ipc-flooding-protection')
            options.add_argument('--disable-web-security')
            options.add_argument('--disable-features=TranslateUI,BlinkGenPropertyTrees')
            options.add_argument('--disable-extensions')
            options.add_argument('--disable-plugins')
            options.add_argument('--disable-default-apps')
            options.add_argument('--disable-sync')
            options.add_argument('--disable-background-networking')
            options.add_argument('--disable-blink-features=AutomationControlled')
            
            # Configuration mémoire et performance
            options.add_argument('--memory-pressure-off')
            options.add_argument('--max_old_space_size=4096')
            options.add_argument('--disable-background-timer-throttling')
            options.add_argument('--disable-renderer-backgrounding')
            options.add_argument('--disable-backgrounding-occluded-windows')
            
            # Taille de fenêtre optimale
            options.add_argument('--window-size=1280,720')
            options.add_argument('--start-maximized')
            
            # Locale française
            options.add_argument('--lang=fr-FR')
            options.add_argument('--accept-lang=fr-FR,fr,en-US,en')
            
            # User agent réaliste
            options.add_argument('--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            # Configuration proxy si activé
            if self.use_proxy:
                proxy_string = f"{self.proxy_user}:{self.proxy_pass}@{self.proxy_host}:{self.proxy_port}"
                options.add_argument(f'--proxy-server=http://{proxy_string}')
                self.logger.info("🔗 Proxy Webshare configured")
            else:
                self.logger.info("⚠️ PROXY DISABLED - Direct connection")
            
            # Timeouts plus courts pour éviter les blocages
            options.add_argument('--timeout=30000')
            options.add_argument('--page-load-strategy=eager')
            
            # Désactiver les images pour plus de rapidité
            options.add_argument('--disable-images')
            prefs = {
                "profile.managed_default_content_settings.images": 2,
                "profile.default_content_setting_values.notifications": 2,
                "profile.default_content_settings.popups": 0
            }
            options.add_experimental_option("prefs", prefs)
            
            # Configuration du service
            service = None
            try:
                service = Service()
                service.creation_flags = 0x08000000  # CREATE_NO_WINDOW pour Windows
            except:
                pass
            
            self.logger.info("⚙️ Creating Chrome instance...")
            
            # Créer le driver avec timeout court
            self.driver = uc.Chrome(
                options=options, 
                service=service,
                version_main=None,
                driver_executable_path=None
            )
            
            # Configuration post-création avec timeouts courts
            self.driver.set_page_load_timeout(30)
            self.driver.implicitly_wait(5)
            
            # Scripts anti-détection
            try:
                self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                self.driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")
                self.driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['fr-FR', 'fr', 'en-US', 'en']})")
            except Exception as e:
                self.logger.debug(f"Anti-detection script failed: {e}")
            
            # Test de connectivité rapide
            self.logger.info("🧪 Testing browser connectivity...")
            try:
                self.driver.get("https://httpbin.org/ip")
                time.sleep(2)
                page_source = self.driver.page_source
                if '"origin"' in page_source:
                    ip_info = json.loads(self.driver.find_element(By.TAG_NAME, "pre").text)
                    self.logger.info(f"✅ Connection working! IP: {ip_info.get('origin')}")
                else:
                    self.logger.warning("⚠️ Connection test unclear")
            except Exception as e:
                self.logger.warning(f"⚠️ Connection test failed: {e}")
            
            self.logger.info("✅ Chrome driver ready")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Driver setup failed: {e}")
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
                self.driver = None
            return False
    
    def extract_business_data(self, search_query: str) -> Optional[Dict]:
        """Extrait les données d'entreprise depuis Google Maps"""
        try:
            self.logger.info(f"🔍 Searching Maps: {search_query}")
            
            # URL de recherche Google Maps
            search_url = f"https://www.google.com/maps/search/{quote_plus(search_query)}"
            
            # Aller sur la page avec timeout court
            try:
                self.driver.get(search_url)
                time.sleep(random.uniform(2, 4))
            except TimeoutException:
                self.logger.error("❌ Page load timeout")
                return None
            
            # Accepter les cookies Google si nécessaire
            try:
                accept_buttons = [
                    "//button[contains(., 'Tout accepter')]",
                    "//button[contains(., 'Accept all')]",
                    "//button[contains(., 'J\\'accepte')]",
                    "#L2AGLb"
                ]
                
                for xpath in accept_buttons:
                    try:
                        if xpath.startswith('#'):
                            button = self.driver.find_element(By.CSS_SELECTOR, xpath)
                        else:
                            button = self.driver.find_element(By.XPATH, xpath)
                        button.click()
                        time.sleep(1)
                        self.logger.debug("✅ Cookies accepted")
                        break
                    except:
                        continue
            except Exception as e:
                self.logger.debug(f"Cookie handling: {e}")
            
            # Attendre que les résultats se chargent
            data = {
                'name': None,
                'address': None,
                'phone': None,
                'website': None,
                'has_website': False,
                'rating': None,
                'reviews_count': None,
                'search_query': search_query
            }
            
            try:
                # Attendre les résultats Maps
                WebDriverWait(self.driver, 10).until(
                    EC.any_of(
                        EC.presence_of_element_located((By.CSS_SELECTOR, '[role="feed"]')),
                        EC.presence_of_element_located((By.CSS_SELECTOR, '[role="main"]')),
                        EC.presence_of_element_located((By.CSS_SELECTOR, '.Nv2PK'))
                    )
                )
                
                # Chercher et cliquer sur le premier résultat
                result_selectors = [
                    'a[href*="/maps/place/"]',
                    '[data-result-index="0"] a',
                    '.Nv2PK .hfpxzc'
                ]
                
                clicked_result = False
                for selector in result_selectors:
                    try:
                        results = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if results:
                            first_result = results[0]
                            self.driver.execute_script("arguments[0].click();", first_result)
                            time.sleep(random.uniform(2, 3))
                            clicked_result = True
                            self.logger.debug("✅ Clicked on first result")
                            break
                    except Exception as e:
                        self.logger.debug(f"Result click failed with {selector}: {e}")
                        continue
                
                if not clicked_result:
                    self.logger.warning("⚠️ Could not click on any result")
                    return None
                
                # Attendre que les détails se chargent
                time.sleep(random.uniform(2, 3))
                
                # === EXTRACTION DES DONNÉES ===
                
                # 1. Nom de l'entreprise
                name_selectors = [
                    'h1.DUwDvf.fontHeadlineLarge',
                    'h1[data-attrid="title"]',
                    '.qBF1Pd.fontHeadlineSmall',
                    'h1.DUwDvf',
                    '[data-item-id="title"] h1'
                ]
                
                for selector in name_selectors:
                    try:
                        name_elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                        if name_elem and name_elem.text.strip():
                            data['name'] = name_elem.text.strip()
                            self.logger.debug(f"✅ Name found: {data['name']}")
                            break
                    except:
                        continue
                
                # 2. Site web - CRITIQUE pour le filtrage
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
                        if website_elem:
                            href = website_elem.get_attribute('href')
                            if href and 'http' in href and 'google' not in href and 'maps' not in href:
                                data['website'] = href
                                data['has_website'] = True
                                self.logger.info(f"🌐 Website found: {href}")
                                break
                    except:
                        continue
                
                # 3. Téléphone
                phone_selectors = [
                    'button[data-item-id^="phone:tel:"]',
                    '[data-item-id^="phone"] span',
                    'button[aria-label*="téléphone"]',
                    'span[dir="ltr"]'  # Les numéros sont souvent en LTR
                ]
                
                for selector in phone_selectors:
                    try:
                        phone_elems = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        for phone_elem in phone_elems:
                            phone_text = phone_elem.text.strip()
                            
                            # Si pas de texte, essayer l'attribut data-item-id
                            if not phone_text and 'data-item-id' in phone_elem.get_attribute('outerHTML'):
                                phone_id = phone_elem.get_attribute('data-item-id')
                                if 'tel:' in phone_id:
                                    phone_text = phone_id.split('tel:')[1]
                            
                            # Validation numéro français
                            if phone_text and re.search(r'0[1-9][\s\-\.]*(?:\d[\s\-\.]*){8}', phone_text):
                                data['phone'] = phone_text
                                self.logger.debug(f"📞 Phone found: {phone_text}")
                                break
                        
                        if data['phone']:
                            break
                    except:
                        continue
                
                # 4. Adresse
                address_selectors = [
                    'button[data-item-id="address"]',
                    '[data-item-id="address"] span',
                    'span[class*="rogA2c"]'
                ]
                
                for selector in address_selectors:
                    try:
                        addr_elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                        if addr_elem and addr_elem.text.strip():
                            data['address'] = addr_elem.text.strip()
                            self.logger.debug(f"📍 Address found: {data['address']}")
                            break
                    except:
                        continue
                
                # 5. Note et avis (bonus)
                try:
                    rating_elems = self.driver.find_elements(By.CSS_SELECTOR, 'span[role="img"][aria-label*="étoile"]')
                    for rating_elem in rating_elems:
                        aria_label = rating_elem.get_attribute('aria-label')
                        if aria_label:
                            rating_match = re.search(r'(\d+[,.]?\d*)', aria_label)
                            if rating_match:
                                data['rating'] = float(rating_match.group(1).replace(',', '.'))
                                break
                except:
                    pass
                
            except TimeoutException:
                self.logger.warning("⚠️ Timeout waiting for Maps results")
                return None
            except Exception as e:
                self.logger.error(f"❌ Error extracting data: {e}")
                return None
            
            # Validation minimale
            if not data['name'] or len(data['name']) < 2:
                self.logger.warning("⚠️ No valid business name found")
                return None
            
            # Log du résultat
            if data['has_website']:
                self.logger.info(f"✅ Business WITH website: {data['name']} -> {data['website']}")
            else:
                self.logger.info(f"❌ Business WITHOUT website: {data['name']}")
            
            return data
            
        except Exception as e:
            self.logger.error(f"❌ Search failed: {e}")
            return None
    
    def search_business(self, query: str, limit: int = 1) -> List[Dict]:
        """Recherche d'entreprises sur Google Maps"""
        results = []
        
        if not self.setup_driver():
            self.logger.error("❌ Failed to setup driver")
            return []
        
        try:
            business_data = self.extract_business_data(query)
            if business_data:
                # Enrichir avec métadonnées
                business_data.update({
                    'source': 'google_maps',
                    'scraped_at': datetime.now().isoformat(),
                    'session_id': self.session_id
                })
                results.append(business_data)
            
        except Exception as e:
            self.logger.error(f"❌ Search failed: {e}")
            
        finally:
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
        
        return results

def main():
    parser = argparse.ArgumentParser(description='Google Maps Scraper for Naosite - Optimized for Fly.io')
    parser.add_argument('query', help='Business query to search (e.g., "plombier nantes")')
    parser.add_argument('--limit', type=int, default=1, help='Number of results to return')
    parser.add_argument('--session-id', help='Session ID for tracking')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--exclude-with-website', action='store_true', help='Only return businesses without websites')
    parser.add_argument('--no-proxy', action='store_true', help='Disable proxy (for testing)')
    
    args = parser.parse_args()
    
    try:
        scraper = GoogleMapsScraper(
            session_id=args.session_id,
            debug=args.debug,
            use_proxy=not args.no_proxy
        )
        
        results = scraper.search_business(
            query=args.query,
            limit=args.limit
        )
        
        # Filtrer si demandé
        if args.exclude_with_website:
            results = [r for r in results if not r.get('has_website', False)]
        
        # Output JSON pour n8n
        for result in results:
            print(json.dumps(result, ensure_ascii=False))
            
        if args.debug:
            no_website_count = sum(1 for r in results if not r.get('has_website', False))
            logging.info(f"Found {len(results)} businesses ({no_website_count} without websites)")
            
    except Exception as e:
        error_result = {
            'search_query': args.query,
            'name': None,
            'website': None,
            'has_website': False,
            'source': 'error',
            'error': str(e),
            'scraped_at': datetime.now().isoformat()
        }
        print(json.dumps(error_result, ensure_ascii=False))
        logging.error(f"Scraper failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
