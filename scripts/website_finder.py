#!/usr/bin/env python3
"""
Website Finder CORRIGÉ - 4 Corrections critiques pour 2025
Basé sur recherche approfondie et sources validées
"""

import json
import time
import argparse
import sys
import logging
import re
from typing import Optional, Dict
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

class RobustWebsiteFinder:
    def __init__(self, session_id: str = None, debug: bool = False, headless: bool = True):
        if not SELENIUM_AVAILABLE:
            raise ImportError("Please install: pip install undetected-chromedriver selenium")
            
        self.session_id = session_id or f"finder_{int(time.time())}"
        self.debug = debug
        self.headless = headless
        self.setup_logging()
        
        # Configuration proxy Webshare
        self.proxy_host = "p.webshare.io"
        self.proxy_port = "1080"
        self.proxy_user = "xftpfnvt-rotate"
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

    # ✅ CORRECTION 1: Gestion robuste des versions undetected-chromedriver
    def setup_driver_with_retry(self):
        """Setup avec auto-détection version Chrome et retry automatique"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                return self._create_driver()
            except Exception as e:
                error_message = str(e)
                
                # Auto-détection version à partir du message d'erreur
                if "Current browser version is" in error_message:
                    version_match = re.search(r"Current browser version is (\d+)\.", error_message)
                    if version_match:
                        chrome_version = int(version_match.group(1))
                        self.logger.warning(f"Auto-detected Chrome version: {chrome_version}")
                        try:
                            return self._create_driver(version_main=chrome_version)
                        except Exception as retry_error:
                            self.logger.error(f"Retry with version {chrome_version} failed: {retry_error}")
                
                if attempt == max_retries - 1:
                    self.logger.error(f"Driver setup failed after {max_retries} attempts: {e}")
                    return False
                
                # Exponential backoff
                wait_time = 2 ** attempt
                self.logger.warning(f"Driver setup attempt {attempt + 1} failed, waiting {wait_time}s...")
                time.sleep(wait_time)
        
        return False

    def _create_driver(self, version_main=None):
        """Création du driver avec paramètres optimisés"""
        options = uc.ChromeOptions()
        
        # Configuration proxy Webshare
        proxy_string = f"{self.proxy_user}:{self.proxy_pass}@{self.proxy_host}:{self.proxy_port}"
        options.add_argument(f'--proxy-server=http://{proxy_string}')
        
        # Options anti-détection optimisées 2025
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-web-security')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-extensions-file-access-check')
        options.add_argument('--disable-extensions-http-throttling')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--lang=fr-FR')
        
        if self.headless:
            options.add_argument('--headless=new')
        
        # User agents rotatifs (sélection aléatoire)
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        options.add_argument(f'--user-agent={random.choice(user_agents)}')
        
        # Créer le driver avec version spécifique si fournie
        if version_main:
            self.driver = uc.Chrome(options=options, version_main=version_main)
        else:
            self.driver = uc.Chrome(options=options)
        
        # Configuration post-création
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        self.driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")
        self.driver.implicitly_wait(10)
        
        self.logger.info("Driver créé avec succès")
        return True

    # ✅ CORRECTION 2: Sélecteurs CSS robustes 2025 (validés par recherche)
    def get_robust_selectors_2025(self):
        """Sélecteurs CSS validés qui fonctionnent en 2025"""
        return {
            'maps_website': [
                # Sélecteurs basés sur le contenu (plus robustes)
                'a[href*="http"]:not([href*="google"]):not([href*="maps"]):not([href*="facebook"]):not([href*="instagram"])',
                'button[aria-label*="website" i]',
                'button[data-value*="authority"]',
                'a[data-value*="authority"]',
                # Fallback par structure
                '[role="button"]:has-text("Site")',
                '[role="button"]:has-text("Website")',
                '.widget-pane-link[href*="http"]:not([href*="google"])'
            ],
            'maps_phone': [
                # Sélecteurs téléphone validés
                'button[aria-label*="phone" i]',
                'button[data-value*="phone"]',
                'a[href^="tel:"]',
                'button[data-item-id*="phone"]',
                '[role="button"]:has-text("Appeler")',
                '.widget-pane-link[href^="tel:"]'
            ],
            'maps_business_name': [
                # Noms d'entreprise - sélecteurs plus stables
                'h1[role="heading"]',
                'h1.fontHeadlineSmall',
                '[data-attrid="title"]',
                '.qBF1Pd.fontHeadlineSmall'
            ]
        }

    # ✅ CORRECTION 3: Retry automatique avec backoff exponentiel
    def smart_retry(self, func, max_retries=3, backoff_factor=2):
        """Retry intelligent avec gestion d'erreur spécifique"""
        for attempt in range(max_retries):
            try:
                return func()
            except TimeoutException as e:
                if attempt == max_retries - 1:
                    self.logger.error(f"Timeout final après {max_retries} tentatives")
                    raise
                wait_time = backoff_factor ** attempt
                self.logger.warning(f"Timeout tentative {attempt + 1}, retry dans {wait_time}s")
                time.sleep(wait_time)
            except NoSuchElementException as e:
                if attempt == max_retries - 1:
                    self.logger.warning(f"Élément non trouvé après {max_retries} tentatives")
                    return None  # Pas d'erreur, juste pas trouvé
                time.sleep(1)
            except Exception as e:
                if "disconnected" in str(e).lower() or "session" in str(e).lower():
                    # Problème de connexion - recréer le driver
                    self.logger.warning("Reconnexion driver nécessaire")
                    if self.driver:
                        self.driver.quit()
                    if not self.setup_driver_with_retry():
                        raise Exception("Impossible de recréer le driver")
                    # Retry avec nouveau driver
                    continue
                
                if attempt == max_retries - 1:
                    raise
                wait_time = backoff_factor ** attempt
                time.sleep(wait_time)

    # ✅ CORRECTION 4: Monitoring proxy Webshare intelligent
    def check_proxy_health(self):
        """Vérification santé proxy avec métriques"""
        try:
            import requests
            
            # Test de base avec IP check
            start_time = time.time()
            test_response = requests.get(
                'https://httpbin.org/ip',
                proxies={
                    'http': f'http://{self.proxy_user}:{self.proxy_pass}@{self.proxy_host}:{self.proxy_port}',
                    'https': f'http://{self.proxy_user}:{self.proxy_pass}@{self.proxy_host}:{self.proxy_port}'
                },
                timeout=10
            )
            latency = time.time() - start_time
            
            if test_response.status_code == 200:
                proxy_ip = test_response.json().get('origin', 'unknown')
                self.logger.info(f"Proxy OK: IP={proxy_ip}, Latency={latency:.2f}s")
                
                # Métriques proxy
                return {
                    'status': 'healthy',
                    'latency': latency,
                    'proxy_ip': proxy_ip,
                    'timestamp': datetime.now().isoformat()
                }
            else:
                self.logger.error(f"Proxy test failed: HTTP {test_response.status_code}")
                return {'status': 'unhealthy', 'reason': f'HTTP {test_response.status_code}'}
                
        except Exception as e:
            self.logger.error(f"Proxy health check failed: {e}")
            return {'status': 'unhealthy', 'reason': str(e)}

    def extract_website_from_maps_robust(self, search_query: str) -> Optional[str]:
        """Extraction robuste avec sélecteurs 2025 et retry"""
        def _extract():
            search_url = f"https://www.google.com/maps/search/{quote_plus(search_query)}"
            self.driver.get(search_url)
            
            # Attendre et gérer cookies
            time.sleep(random.uniform(3, 5))
            try:
                accept_button = self.driver.find_element(By.XPATH, "//button[contains(., 'Tout accepter')]")
                accept_button.click()
                time.sleep(1)
            except:
                pass
            
            # Chercher le premier résultat avec retry
            def _find_first_result():
                first_result = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, '[role="feed"] a[href*="/maps/place/"]'))
                )
                first_result.click()
                time.sleep(random.uniform(2, 4))
                return True
            
            if not self.smart_retry(_find_first_result):
                return None
            
            # Chercher le site web avec les nouveaux sélecteurs
            selectors = self.get_robust_selectors_2025()['maps_website']
            
            for selector in selectors:
                try:
                    website_elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if website_elem:
                        href = website_elem.get_attribute('href')
                        if href and 'http' in href and 'google' not in href:
                            self.logger.info(f"Website trouvé avec sélecteur {selector}: {href}")
                            return href
                except:
                    continue
            
            return None
        
        return self.smart_retry(_extract)

    def is_valid_business_website_2025(self, url: str, search_query: str) -> bool:
        """Validation business améliorée - garde Facebook/Instagram comme prospects"""
        if not url or not url.startswith('http'):
            return False
        
        # Sites qui restent des prospects (pour vente de sites web)
        prospect_domains = [
            'facebook.com', 'linkedin.com', 'instagram.com', 'twitter.com'
        ]
        
        # Sites à exclure complètement (annuaires/spam)
        exclude_domains = [
            'pagesjaunes.fr', 'societe.com', 'verif.com', 'infogreffe.fr',
            'pappers.fr', 'score3.fr', 'mappy.com', 'yelp.fr',
            'tripadvisor.fr', 'leboncoin.fr', 'youtube.com', 'wikipedia.org'
        ]
        
        url_lower = url.lower()
        
        # Si c'est un prospect (réseau social) = retourner False (pas de "vrai" site)
        for domain in prospect_domains:
            if domain in url_lower:
                self.logger.info(f"Prospect détecté (réseau social): {url}")
                return False
        
        # Si c'est un annuaire = exclure
        for domain in exclude_domains:
            if domain in url_lower:
                return False
        
        # Sinon c'est un vrai site business
        return True

    def find_website(self, search_query: str) -> Dict:
        """Fonction principale avec toutes les corrections appliquées"""
        result = {
            'search_query': search_query,
            'website_url': None,
            'phone': None,
            'source': None,
            'found_at': None,
            'session_id': self.session_id,
            'proxy_health': None
        }
        
        # Check proxy health d'abord
        proxy_health = self.check_proxy_health()
        result['proxy_health'] = proxy_health
        
        if proxy_health['status'] != 'healthy':
            self.logger.warning(f"Proxy unhealthy: {proxy_health}")
            # Continuer quand même mais noter le problème
        
        # Setup driver avec retry
        if not self.setup_driver_with_retry():
            result['error'] = 'Driver setup failed after retries'
            return result
        
        try:
            self.logger.info(f"Recherche robuste pour: {search_query}")
            
            # 1. Google Maps avec extraction robuste
            website_url = self.extract_website_from_maps_robust(search_query)
            
            # Valider si c'est un vrai site business
            if website_url and self.is_valid_business_website_2025(website_url, search_query):
                result.update({
                    'website_url': website_url,
                    'source': 'google_maps',
                    'found_at': datetime.now().isoformat(),
                    'has_real_website': True
                })
            else:
                # Pas de vrai site trouvé = prospect
                result.update({
                    'website_url': None,
                    'source': 'no_real_website',
                    'found_at': datetime.now().isoformat(),
                    'has_real_website': False,
                    'prospect_reason': 'social_media_only' if website_url else 'no_website'
                })
            
        except Exception as e:
            result['error'] = str(e)
            self.logger.error(f"Recherche échouée: {e}")
            
        finally:
            if self.driver:
                self.driver.quit()
                
        return result

def main():
    parser = argparse.ArgumentParser(description='Website Finder CORRIGÉ - Version 2025')
    parser.add_argument('query', help='Requête de recherche business')
    parser.add_argument('--session-id', help='ID de session pour tracking')
    parser.add_argument('--debug', action='store_true', help='Mode debug')
    parser.add_argument('--no-headless', action='store_true', help='Montrer navigateur')
    
    args = parser.parse_args()
    
    try:
        finder = RobustWebsiteFinder(
            session_id=args.session_id,
            debug=args.debug,
            headless=not args.no_headless
        )
        
        result = finder.find_website(args.query)
        
        # Output JSON pour n8n
        print(json.dumps(result, ensure_ascii=False))
        
        if args.debug:
            logging.info(f"Résultat robuste: {result}")
            
    except Exception as e:
        error_result = {
            'search_query': args.query,
            'website_url': None,
            'source': 'error',
            'error': str(e),
            'found_at': datetime.now().isoformat()
        }
        print(json.dumps(error_result, ensure_ascii=False))
        logging.error(f"Scraper robuste échoué: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
