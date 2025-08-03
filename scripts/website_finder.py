#!/usr/bin/env python3
"""
Google Maps Scraper pour Naosite - Version ultra-robuste
Détecte les entreprises avec/sans site web via Google Maps
Optimisé pour containers Docker et proxy Webshare
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
import subprocess
import os

try:
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
    from selenium.webdriver.chrome.options import Options
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

class GoogleMapsScraper:
    def __init__(self, session_id: str = None, debug: bool = False, headless: bool = True):
        if not SELENIUM_AVAILABLE:
            raise ImportError("Please install: pip install undetected-chromedriver selenium")
            
        self.session_id = session_id or f"maps_{int(time.time())}"
        self.debug = debug
        self.headless = headless
        self.setup_logging()
        
        # Configuration proxy Webshare rotatif
        self.proxy_endpoints = [
            "p.webshare.io:80",
            "proxy.webshare.io:8000",
            "rotating-residential.webshare.io:80"
        ]
        self.proxy_user = "xftpfnvt-rotate"
        self.proxy_pass = "yulnmnbiq66j"
        
        self.driver = None
        self.driver_failures = 0
        self.max_failures = 3
        
    def setup_logging(self):
        level = logging.DEBUG if self.debug else logging.WARNING
        logging.basicConfig(
            level=level,
            format=f'[{self.session_id}] %(levelname)s: %(message)s',
            stream=sys.stderr
        )
        self.logger = logging.getLogger(__name__)
    
    def check_chrome_available(self):
        """Vérifier que Chrome fonctionne"""
        chrome_paths = [
            '/usr/bin/google-chrome-stable',
            '/usr/bin/google-chrome',
            '/usr/bin/chromium-browser'
        ]
        
        for path in chrome_paths:
            if os.path.exists(path):
                try:
                    result = subprocess.run([path, '--version'], 
                                          capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        self.logger.info(f"✅ Chrome found: {result.stdout.strip()}")
                        return path
                except Exception as e:
                    self.logger.debug(f"Chrome test failed: {e}")
                    continue
        
        self.logger.error("❌ No working Chrome found!")
        return None
    
    def get_random_proxy(self):
        """Obtenir un proxy aléatoire de la liste"""
        endpoint = random.choice(self.proxy_endpoints)
        return f"http://{self.proxy_user}:{self.proxy_pass}@{endpoint}"
    
    def setup_driver(self):
        """Configure Chrome avec toutes les optimisations"""
        try:
            self.logger.info("🚀 Setting up Chrome driver...")
            
            # Vérifier Chrome
            chrome_binary = self.check_chrome_available()
            if not chrome_binary:
                raise Exception("Chrome not available")
            
            # Nettoyer processus Chrome existants
            try:
                subprocess.run(['pkill', '-f', 'chrome'], capture_output=True, timeout=3)
                time.sleep(1)
            except:
                pass
            
            # Configuration Chrome
            options = uc.ChromeOptions()
            
            # === OPTIONS CONTAINER-FRIENDLY ===
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-software-rasterizer')
            options.add_argument('--disable-background-timer-throttling')
            options.add_argument('--disable-backgrounding-occluded-windows')
            options.add_argument('--disable-renderer-backgrounding')
            options.add_argument('--disable-features=TranslateUI,VizDisplayCompositor')
            options.add_argument('--disable-web-security')
            options.add_argument('--disable-extensions')
            options.add_argument('--disable-plugins')
            options.add_argument('--disable-default-apps')
            options.add_argument('--disable-sync')
            options.add_argument('--disable-background-networking')
            options.add_argument('--disable-blink-features=AutomationControlled')
            
            # === HEADLESS MODE ===
            if self.headless:
                options.add_argument('--headless=new')
            
            # === PERFORMANCE ===
            options.add_argument('--memory-pressure-off')
            options.add_argument('--max_old_space_size=512')
            options.add_argument('--window-size=1280,720')
            
            # === DISPLAY ===
            if os.environ.get('DISPLAY'):
                options.add_argument(f'--display={os.environ["DISPLAY"]}')
            
            # === PROXY ROTATIF ===
            proxy_url = self.get_random_proxy()
            options.add_argument(f'--proxy-server={proxy_url}')
            self.logger.info(f"🔗 Using proxy: {proxy_url}")
            
            # === LOCALE ===
            options.add_argument('--lang=fr-FR')
            options.add_argument('--accept-lang=fr-FR,fr,en-US,en')
            
            # === USER AGENT ===
            options.add_argument('--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            # === STABILITÉ ===
            options.add_argument('--disable-crash-reporter')
            options.add_argument('--disable-logging')
            options.add_argument('--disable-breakpad')
            options.add_argument('--no-first-run')
            options.add_argument('--no-default-browser-check')
            
            # === PREFS POUR PERFORMANCE ===
            prefs = {
                "profile.managed_default_content_settings.images": 2,  # Bloquer images
                "profile.default_content_setting_values.notifications": 2,
                "profile.default_content_settings.popups": 0,
                "profile.default_content_settings.geolocation": 2,
                "profile.default_content_settings.media_stream": 2
            }
            options.add_experimental_option("prefs", prefs)
            
            # === BINARY PATH ===
            options.binary_location = chrome_binary
            
            # Créer le driver
            self.logger.info("⚙️ Creating Chrome driver...")
            try:
                self.driver = uc.Chrome(
                    options=options,
                    version_main=None
                )
            except Exception as e:
                self.logger.warning(f"undetected-chromedriver failed: {e}, trying regular selenium...")
                from selenium import webdriver
                from selenium.webdriver.chrome.service import Service
                service = Service()
                self.driver = webdriver.Chrome(service=service, options=options)
            
            # Configuration post-création
            self.driver.set_page_load_timeout(20)
            self.driver.implicitly_wait(5)
            
            # Test de base
            self.logger.info("🧪 Testing driver...")
            self.driver.get("data:text/html,<html><body><h1>Test</h1></body></html>")
            time.sleep(1)
            
            self.logger.info("✅ Chrome driver setup successful")
            self.driver_failures = 0
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
    
    def ensure_driver_ready(self):
        """S'assurer que le driver est prêt"""
        if not self.driver:
            return self.setup_driver()
        
        try:
            # Test simple
            current_url = self.driver.current_url
            return True
        except Exception as e:
            self.logger.warning(f"Driver check failed: {e}")
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
                self.driver = None
            
            if self.driver_failures < self.max_failures:
                self.logger.info("🔄 Restarting driver...")
                return self.setup_driver()
            else:
                self.logger.error(f"❌ Max driver failures reached")
                return False
    
    def search_google_maps(self, search_query: str, limit: int = 1, exclude_with_website: bool = False) -> List[Dict]:
        """Recherche sur Google Maps avec extraction complète"""
        results = []
        
        if not self.ensure_driver_ready():
            self.logger.error("❌ Driver not ready, cannot proceed")
            return []
        
        try:
            self.logger.info(f"🔍 Searching Google Maps: {search_query}")
            
            # URL Google Maps
            maps_url = f"https://www.google.com/maps/search/{quote_plus(search_query)}"
            
            self.driver.get(maps_url)
            time.sleep(random.uniform(3, 5))
            
            # Accepter cookies Google
            try:
                cookie_selectors = [
                    "//button[contains(text(), 'Tout accepter')]",
                    "//button[contains(text(), 'Accept all')]",
                    "//button[@id='L2AGLb']"
                ]
                
                for selector in cookie_selectors:
                    try:
                        button = self.driver.find_element(By.XPATH, selector)
                        if button.is_displayed():
                            button.click()
                            time.sleep(1)
                            self.logger.debug("✅ Cookies accepted")
                            break
                    except:
                        continue
            except:
                pass
            
            # Attendre résultats Maps
            try:
                WebDriverWait(self.driver, 15).until(
                    EC.any_of(
                        EC.presence_of_element_located((By.CSS_SELECTOR, '[role="feed"]')),
                        EC.presence_of_element_located((By.CSS_SELECTOR, '[role="main"]')),
                        EC.presence_of_element_located((By.CSS_SELECTOR, '.Nv2PK'))
                    )
                )
                
                # Trouver et cliquer sur les résultats business
                business_selectors = [
                    'a[href*="/maps/place/"]',
                    '[data-result-index] a',
                    '.Nv2PK .hfpxzc'
                ]
                
                business_links = []
                for selector in business_selectors:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if elements:
                            business_links = elements[:limit]
                            break
                    except:
                        continue
                
                if not business_links:
                    self.logger.warning("⚠️ No business results found")
                    return []
                
                # Traiter chaque business
                for i, link in enumerate(business_links):
                    try:
                        self.logger.info(f"📋 Processing business {i+1}/{len(business_links)}")
                        
                        # Cliquer sur le business
                        self.driver.execute_script("arguments[0].click();", link)
                        time.sleep(random.uniform(2, 4))
                        
                        # Extraire les données
                        business_data = self.extract_business_data()
                        
                        if business_data:
                            # Enrichir avec métadonnées
                            business_data.update({
                                'source': 'google_maps',
                                'search_query': search_query,
                                'position': i + 1,
                                'scraped_at': datetime.now().isoformat(),
                                'session_id': self.session_id
                            })
                            
                            # Filtrer si demandé
                            if exclude_with_website:
                                if not business_data.get('has_website', False):
                                    results.append(business_data)
                                    self.logger.info(f"✅ Added (no website): {business_data.get('name', 'Unknown')}")
                                else:
                                    self.logger.info(f"🌐 Excluded (has website): {business_data.get('name', 'Unknown')}")
                            else:
                                results.append(business_data)
                        
                        # Délai entre businesses
                        if i < len(business_links) - 1:
                            time.sleep(random.uniform(1, 2))
                            
                    except Exception as e:
                        self.logger.error(f"❌ Error processing business {i+1}: {e}")
                        continue
                        
            except TimeoutException:
                self.logger.warning("⚠️ Timeout waiting for Maps results")
                return []
                
        except Exception as e:
            self.logger.error(f"❌ Maps search error: {e}")
            return []
        
        self.logger.info(f"📊 Extracted {len(results)} results from Google Maps")
        return results
    
    def extract_business_data(self) -> Optional[Dict]:
        """Extraire les données d'un business depuis la page Maps"""
        try:
            data = {
                'name': None,
                'address': None,
                'phone': None,
                'website': None,
                'has_website': False,
                'rating': None,
                'reviews_count': None
            }
            
            # === NOM DE L'ENTREPRISE ===
            name_selectors = [
                'h1.DUwDvf.fontHeadlineLarge',
                '.qBF1Pd',
                'h1[class*="fontHeadline"]',
                '[role="heading"][aria-level="1"]',
                'h1'
            ]
            
            for selector in name_selectors:
                try:
                    name_elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if name_elem and name_elem.text.strip():
                        data['name'] = name_elem.text.strip()[:150]
                        break
                except:
                    continue
            
            # === SITE WEB (CRITIQUE) ===
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
                        if href and 'http' in href and self.is_valid_website(href):
                            data['website'] = href[:200]
                            data['has_website'] = True
                            self.logger.info(f"🌐 Website found: {href}")
                            break
                except:
                    continue
            
            # === TÉLÉPHONE ===
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
                        
                        # Essayer data-item-id si pas de texte
                        if not phone_text and 'data-item-id' in phone_elem.get_attribute('outerHTML'):
                            phone_id = phone_elem.get_attribute('data-item-id')
                            if 'tel:' in phone_id:
                                phone_text = phone_id.split('tel:')[1]
                        
                        # Valider numéro français
                        if phone_text and self.is_valid_french_phone(phone_text):
                            data['phone'] = phone_text[:50]
                            self.logger.info(f"📞 Phone found: {phone_text}")
                            break
                    
                    if data.get('phone'):
                        break
                except:
                    continue
            
            # === ADRESSE ===
            address_selectors = [
                'button[data-item-id="address"]',
                '[data-item-id="address"] span',
                '.W4Efsd:last-child > .W4Efsd:nth-of-type(1) > span:last-child'
            ]
            
            for selector in address_selectors:
                try:
                    addr_elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if addr_elem and addr_
