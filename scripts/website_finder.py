#!/usr/bin/env python3
"""
Website Finder pour Naosite - Trouve les sites web d'entreprises
Combine Google Maps + Google Search pour localiser les sites existants
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
    from bs4 import BeautifulSoup
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

class WebsiteFinder:
def extract_phone_from_maps(self, search_query: str) -> Optional[str]:
    """Cherche le téléphone sur Google Maps"""
    try:
        search_url = f"https://www.google.com/maps/search/{quote_plus(search_query)}"
        self.driver.get(search_url)
        
        # Attendre le chargement
        time.sleep(random.uniform(3, 5))
        
        # Chercher le premier résultat
        try:
            first_result = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, '[role="feed"] a[href*="/maps/place/"]'))
            )
            first_result.click()
            time.sleep(random.uniform(2, 4))
            
            # Chercher le téléphone dans les détails
            phone_selectors = [
                'button[data-item-id^="phone:tel:"]',
                '[data-item-id^="phone"] span',
                '.W4Efsd:nth-child(2) span[jsinstance="*1"]',
                'span[role="text"]:has-text("02")',  # Numéros français
                'span[role="text"]:has-text("01")',
                'span[role="text"]:has-text("03")',
                'span[role="text"]:has-text("04")',
                'span[role="text"]:has-text("05")',
                'span[role="text"]:has-text("06")',
                'span[role="text"]:has-text("07")',
                'span[role="text"]:has-text("09")'
            ]
            
            for selector in phone_selectors:
                try:
                    phone_elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if phone_elem:
                        phone_text = phone_elem.text.strip()
                        
                        # Si pas de texte, essayer l'attribut data
                        if not phone_text and 'data-item-id' in phone_elem.get_attribute('outerHTML'):
                            phone_id = phone_elem.get_attribute('data-item-id')
                            if 'tel:' in phone_id:
                                phone_text = phone_id.split('tel:')[1]
                        
                        # Valider le format français
                        if phone_text and self.is_valid_french_phone(phone_text):
                            self.logger.info(f"Found phone on Maps: {phone_text}")
                            return phone_text
                except:
                    continue
                    
        except TimeoutException:
            self.logger.debug("No Maps results found for phone")
            
    except Exception as e:
        self.logger.error(f"Error in Maps phone search: {e}")
        
    return None

def is_valid_french_phone(self, phone: str) -> bool:
    """Valide un numéro de téléphone français"""
    if not phone:
        return False
    
    # Nettoyer le numéro
    clean_phone = re.sub(r'[^\d+]', '', phone)
    
    # Formats français valides
    patterns = [
        r'^0[1-9]\d{8}$',      # 01 23 45 67 89
        r'^\+33[1-9]\d{8}$',   # +33 1 23 45 67 89
        r'^33[1-9]\d{8}$',     # 33 1 23 45 67 89
    ]
    
    for pattern in patterns:
        if re.match(pattern, clean_phone):
            return True
    
    return False

def find_website_and_phone(self, search_query: str) -> Dict:
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
        self.logger.info(f"Searching website and phone for: {search_query}")
        
        # 1. Essayer Google Maps (site web ET téléphone)
        website_url = self.extract_website_from_maps(search_query)
        phone = self.extract_phone_from_maps(search_query)
        
        if website_url or phone:
            result.update({
                'website_url': website_url,
                'phone': phone,
                'source': 'google_maps',
                'found_at': datetime.now().isoformat()
            })
            return result
        
        # 2. Fallback sur Google Search (site web seulement)
        website_url = self.extract_website_from_google_search(search_query)
        if website_url:
            result.update({
                'website_url': website_url,
                'phone': None,
                'source': 'google_search',
                'found_at': datetime.now().isoformat()
            })
            return result
        
        # 3. Pas de site ni téléphone trouvé
        result['source'] = 'not_found'
        self.logger.info(f"No website or phone found for: {search_query}")
        
    except Exception as e:
        result['error'] = str(e)
        self.logger.error(f"Search failed: {e}")
        
    finally:
        if self.driver:
            self.driver.quit()
            
    return result
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
    
    def extract_website_from_maps(self, search_query: str) -> Optional[str]:
        """Cherche le site web sur Google Maps"""
        try:
            search_url = f"https://www.google.com/maps/search/{quote_plus(search_query)}"
            self.driver.get(search_url)
            
            # Attendre le chargement
            time.sleep(random.uniform(3, 5))
            
            # Accepter cookies si nécessaire
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
                
                # Chercher le site web dans les détails
                website_selectors = [
                    'a[data-item-id="authority"]',
                    'a.lcr4fd',
                    'a[href*="http"]:not([href*="google.com"]):not([href*="maps"])',
                    '[data-item-id="authority"] span'
                ]
                
                for selector in website_selectors:
                    try:
                        website_elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                        if website_elem:
                            href = website_elem.get_attribute('href')
                            if href and 'http' in href and 'google' not in href:
                                self.logger.info(f"Found website on Maps: {href}")
                                return href
                    except:
                        continue
                        
            except TimeoutException:
                self.logger.debug("No Maps results found")
                
        except Exception as e:
            self.logger.error(f"Error in Maps search: {e}")
            
        return None
    
    def extract_website_from_google_search(self, search_query: str) -> Optional[str]:
        """Cherche le site web via Google Search"""
        try:
            # Requête optimisée pour trouver le site officiel
            search_url = f"https://www.google.com/search?q={quote_plus(search_query + ' site officiel')}"
            self.driver.get(search_url)
            
            time.sleep(random.uniform(2, 4))
            
            # Accepter cookies Google
            try:
                accept_button = self.driver.find_element(By.XPATH, "//button[contains(., 'Tout accepter')]")
                accept_button.click()
                time.sleep(1)
            except:
                pass
            
            # Analyser les premiers résultats
            result_selectors = [
                'div.g h3 a',
                'div.tF2Cxc a h3',
                'div.yuRUbf a'
            ]
            
            for selector in result_selectors:
                try:
                    results = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for result in results[:5]:  # Analyser les 5 premiers résultats
                        try:
                            href = result.get_attribute('href')
                            if href and self.is_valid_business_website(href, search_query):
                                self.logger.info(f"Found website via Google Search: {href}")
                                return href
                        except:
                            continue
                    break
                except:
                    continue
                    
        except Exception as e:
            self.logger.error(f"Error in Google search: {e}")
            
        return None
    
    def is_valid_business_website(self, url: str, search_query: str) -> bool:
        """Valide si l'URL est bien le site de l'entreprise"""
        if not url or not url.startswith('http'):
            return False
            
        # Exclure les sites génériques
        exclude_domains = [
            'facebook.com', 'linkedin.com', 'instagram.com', 'twitter.com',
            'pagesjaunes.fr', 'societe.com', 'verif.com', 'infogreffe.fr',
            'pappers.fr', 'score3.fr', 'mappy.com', 'yelp.fr',
            'tripadvisor.fr', 'leboncoin.fr', 'youtube.com', 'wikipedia.org'
        ]
        
        for domain in exclude_domains:
            if domain in url.lower():
                return False
        
        # Bonus si le domaine contient des mots de la recherche
        domain = urlparse(url).netloc.lower()
        search_words = [word.lower() for word in search_query.split() if len(word) > 3]
        
        for word in search_words:
            if word in domain:
                return True
        
        # Si pas de correspondance évidente, c'est quand même un site potentiel
        return True
    
    def find_website(self, search_query: str) -> Dict:
        """Fonction principale - trouve le site web d'une entreprise"""
        result = {
            'search_query': search_query,
            'website_url': None,
            'source': None,
            'found_at': None,
            'session_id': self.session_id
        }
        
        if not self.setup_driver():
            result['error'] = 'Driver setup failed'
            return result
        
        try:
            self.logger.info(f"Searching website for: {search_query}")
            
            # 1. Essayer Google Maps d'abord (plus précis pour les entreprises locales)
            website_url = self.extract_website_from_maps(search_query)
            if website_url:
                result.update({
                    'website_url': website_url,
                    'source': 'google_maps',
                    'found_at': datetime.now().isoformat()
                })
                return result
            
            # 2. Fallback sur Google Search
            website_url = self.extract_website_from_google_search(search_query)
            if website_url:
                result.update({
                    'website_url': website_url,
                    'source': 'google_search',
                    'found_at': datetime.now().isoformat()
                })
                return result
            
            # 3. Pas de site trouvé
            result['source'] = 'not_found'
            self.logger.info(f"No website found for: {search_query}")
            
        except Exception as e:
            result['error'] = str(e)
            self.logger.error(f"Search failed: {e}")
            
        finally:
            if self.driver:
                self.driver.quit()
                
        return result

    def is_valid_french_phone(self, phone: str) -> bool:
    """Valide un numéro de téléphone français"""
        if not phone:
        return False
    
    # Nettoyer le numéro
        clean_phone = re.sub(r'[^\d+]', '', phone)
    
    # Formats français valides
    patterns = [
        r'^0[1-9]\d{8}$',      # 01 23 45 67 89
        r'^\+33[1-9]\d{8}$',   # +33 1 23 45 67 89
        r'^33[1-9]\d{8}$',     # 33 1 23 45 67 89
    ]
    
        for pattern in patterns:
        if re.match(pattern, clean_phone):
            return True
    
    return False
    
    def generate_fallback_result(self, search_query: str) -> Dict:
        """Génère un résultat de fallback si le scraping échoue"""
        return {
            'search_query': search_query,
            'website_url': None,
            'source': 'fallback_no_scraping',
            'found_at': datetime.now().isoformat(),
            'session_id': self.session_id,
            'note': 'Scraping failed, manual verification recommended'
        }

def main():
    parser = argparse.ArgumentParser(description='Website Finder for Naosite - Find business websites')
    
    # ✅ NOUVEAU: Mode batch pour traiter plusieurs entreprises
    parser.add_argument('--batch-mode', action='store_true', help='Process multiple companies from stdin JSON')
    
    # Arguments classiques (pour compatibilité)
    parser.add_argument('query', nargs='?', help='Business search query (e.g., "Plomberie Martin Nantes")')
    parser.add_argument('--find-websites-only', action='store_true', help='Only find websites, do not analyze quality')
    parser.add_argument('--session-id', help='Session ID for tracking')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--no-headless', action='store_true', help='Show browser window')
    
    args = parser.parse_args()
    
    if args.batch_mode:
        # ✅ MODE BATCH: Lire tous les items depuis stdin
        try:
            # Lire toutes les lignes JSON depuis stdin
            input_data = []
            for line in sys.stdin:
                line = line.strip()
                if line:
                    try:
                        item = json.loads(line)
                        input_data.append(item)
                    except json.JSONDecodeError:
                        continue
            
            # Traiter chaque entreprise
            results = []
            for item in input_data:
                query = item.get('searchQuery', '')
                if not query:
                    continue
                
                try:
                    finder = WebsiteFinder(
                        session_id=args.session_id,
                        debug=args.debug,
                        headless=not args.no_headless
                    )
                    
                    result = finder.find_website(query)
                    
                    # Enrichir avec les données de l'item
                    enhanced_result = {
                        # Données de recherche
                        'search_query': result['search_query'],
                        'website_url': result.get('website_url'),
                        'source': result.get('source'),
                        'found_at': result.get('found_at'),
                        'session_id': result.get('session_id'),
                        
                        # ✅ DONNÉES ORIGINALES DE L'ENTREPRISE
                        'siren': item.get('siren'),
                        'siret': item.get('siret'),
                        'searchName': item.get('searchName'),
                        'activity': item.get('activity'),
                        'ville': item.get('ville'),
                        'codePostal': item.get('codePostal'),
                        'departement': item.get('departement'),
                        'isEI': item.get('isEI'),
                        'batchNumber': item.get('batchNumber'),
                        'searchQuery': query,
                        
                        # ✅ ADRESSE COMPLÈTE (NOUVEAU)
                        'adresseComplete': item.get('adresseComplete'),
                        
                        # Données dérivées
                        'hasWebsite': bool(result.get('website_url')),
                        'websiteSource': result.get('source', 'not_found')
                    }
                    
                    # Nettoyer les valeurs None
                    enhanced_result = {k: v for k, v in enhanced_result.items() if v is not None}
                    
                    results.append(enhanced_result)
                    
                except Exception as e:
                    # En cas d'erreur, garder les données de base
                    error_result = {
                        'search_query': query,
                        'website_url': None,
                        'source': 'error',
                        'error': str(e),
                        'siren': item.get('siren'),
                        'searchName': item.get('searchName'),
                        'hasWebsite': False,
                        'adresseComplete': item.get('adresseComplete')
                    }
                    results.append({k: v for k, v in error_result.items() if v is not None})
            
            # Output tous les résultats
            for result in results:
                print(json.dumps(result, ensure_ascii=False))
                
        except Exception as e:
            print(json.dumps({'error': f'Batch processing failed: {e}'}, ensure_ascii=False))
            sys.exit(1)
    
    else:
        # ✅ MODE CLASSIQUE: Un seul item (pour compatibilité)
        if not args.query:
            print("Error: query required in non-batch mode")
            sys.exit(1)
            
        try:
            finder = WebsiteFinder(
                session_id=args.session_id,
                debug=args.debug,
                headless=not args.no_headless
            )
            
            result = finder.find_website(args.query)
            print(json.dumps(result, ensure_ascii=False))
            
        except Exception as e:
            error_result = {
                'search_query': args.query,
                'website_url': None,
                'source': 'error',
                'error': str(e),
                'found_at': datetime.now().isoformat()
            }
            print(json.dumps(error_result, ensure_ascii=False))
            sys.exit(1)

if __name__ == "__main__":
    main()
