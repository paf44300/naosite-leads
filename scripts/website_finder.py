#!/usr/bin/env python3
"""
Website Finder pour Naosite - Mode Batch
Traite plusieurs entreprises en une seule exécution
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
    from bs4 import BeautifulSoup
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
        """Cherche le site web ET le téléphone sur Google Maps en une seule requête"""
        website_url = None
        phone = None
        
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
                
                # ✅ CHERCHER LE SITE WEB
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
                                website_url = href
                                self.logger.info(f"Found website on Maps: {href}")
                                break
                    except:
                        continue
                
                # ✅ CHERCHER LE TÉLÉPHONE (dans la même page)
                phone_selectors = [
                    'button[data-item-id^="phone:tel:"]',
                    '[data-item-id^="phone"] span',
                    '.W4Efsd:nth-child(2) span[jsinstance="*1"]'
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
                                phone = phone_text
                                self.logger.info(f"Found phone on Maps: {phone_text}")
                                break
                    except:
                        continue
                
                # ✅ CHERCHER TÉLÉPHONE DANS LE TEXTE (fallback)
                if not phone:
                    try:
                        page_text = self.driver.find_element(By.TAG_NAME, 'body').text
                        # Chercher patterns téléphone français
                        phone_patterns = [
                            r'0[1-9](?:[-.\s]?\d{2}){4}',  # 01 23 45 67 89
                            r'\+33[1-9](?:[-.\s]?\d{2}){4}',  # +33 1 23 45 67 89
                        ]
                        
                        for pattern in phone_patterns:
                            matches = re.findall(pattern, page_text)
                            for match in matches:
                                clean_phone = re.sub(r'[^\d+]', '', match)
                                if self.is_valid_french_phone(clean_phone):
                                    phone = match
                                    self.logger.info(f"Found phone in text: {match}")
                                    break
                            if phone:
                                break
                    except:
                        pass
                        
            except TimeoutException:
                self.logger.debug("No Maps results found")
                
        except Exception as e:
            self.logger.error(f"Error in Maps search: {e}")
            
        return website_url, phone

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
        
        return True
    
    def find_website(self, search_query: str) -> Dict:
        """Fonction principale - trouve le site web ET le téléphone en une seule passe"""
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
            
            # 1. Essayer Google Maps (site web ET téléphone en une fois)
            website_url, phone = self.extract_website_and_phone_from_maps(search_query)
            
            if website_url:
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
                    'phone': phone,  # Garder le téléphone de Maps si trouvé
                    'source': 'google_search',
                    'found_at': datetime.now().isoformat()
                })
                return result
            
            # 3. Pas de site trouvé, mais peut-être un téléphone
            if phone:
                result.update({
                    'website_url': None,
                    'phone': phone,
                    'source': 'phone_only',
                    'found_at': datetime.now().isoformat()
                })
                return result
            
            # 4. Rien trouvé du tout
            result['source'] = 'not_found'
            self.logger.info(f"No website or phone found for: {search_query}")
            
        except Exception as e:
            result['error'] = str(e)
            self.logger.error(f"Search failed: {e}")
            
        finally:
            if self.driver:
                self.driver.quit()
                
        return result

def main():
    parser = argparse.ArgumentParser(description='Website Finder for Naosite - Batch Mode')
    
    # ✅ MODE BATCH PRINCIPAL
    parser.add_argument('--batch-mode', action='store_true', help='Process multiple companies from stdin JSON')
    
    # Arguments optionnels
    parser.add_argument('--find-websites-only', action='store_true', help='Only find websites, do not analyze quality')
    parser.add_argument('--session-id', help='Session ID for tracking')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--no-headless', action='store_true', help='Show browser window')
    
    # Arguments pour compatibilité (mode simple)
    parser.add_argument('query', nargs='?', help='Business search query')
    parser.add_argument('--siren', help='SIREN de l\'entreprise')
    parser.add_argument('--siret', help='SIRET de l\'entreprise')
    parser.add_argument('--company-name', help='Nom de l\'entreprise')
    parser.add_argument('--activity', help='Activité de l\'entreprise')
    parser.add_argument('--city', help='Ville de l\'entreprise')
    parser.add_argument('--zip-code', help='Code postal')
    parser.add_argument('--address', help='Adresse complète')
    parser.add_argument('--is-ei', action='store_true', help='Est un entrepreneur individuel')
    parser.add_argument('--batch-number', type=int, help='Numéro de batch')
    
    args = parser.parse_args()
    
    if args.batch_mode:
        # ✅ MODE BATCH: Lire tous les items depuis stdin
        try:
            # Lire le JSON depuis stdin
            input_line = sys.stdin.read().strip()
            if not input_line:
                print(json.dumps({'error': 'No input data'}, ensure_ascii=False))
                sys.exit(1)
            
            # Parser le JSON
            input_data = json.loads(input_line)
            if not isinstance(input_data, list):
                input_data = [input_data]
            
            # Créer une instance du finder (réutilisée pour tout le batch)
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
                    # Petit délai entre les recherches
                    if i > 0:
                        time.sleep(random.uniform(2, 4))
                    
                    result = finder.find_website(query)
                    
                    # Enrichir avec les données de l'item
                    enhanced_result = {
                        # Données de recherche
                        'search_query': result['search_query'],
                        'website_url': result.get('website_url'),
                        'phone': result.get('phone'),
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
                        
                        # ✅ ADRESSE COMPLÈTE
                        'adresseComplete': item.get('adresseComplete'),
                        
                        # Données dérivées
                        'hasWebsite': bool(result.get('website_url')),
                        'websiteSource': result.get('source', 'not_found')
                    }
                    
                    # Nettoyer les valeurs None
                    enhanced_result = {k: v for k, v in enhanced_result.items() if v is not None}
                    
                    results.append(enhanced_result)
                    
                    # Log du progrès
                    progress = f"({i+1}/{len(input_data)})"
                    if result.get('website_url'):
                        logging.info(f"🌐 {progress} Website found: {item.get('searchName')}")
                    elif result.get('phone'):
                        logging.info(f"📞 {progress} Phone found: {item.get('searchName')}")
                    else:
                        logging.info(f"❌ {progress} Nothing found: {item.get('searchName')}")
                    
                except Exception as e:
                    # En cas d'erreur, garder les données de base
                    error_result = {
                        'search_query': query,
                        'website_url': None,
                        'phone': None,
                        'source': 'error',
                        'error': str(e),
                        'siren': item.get('siren'),
                        'searchName': item.get('searchName'),
                        'hasWebsite': False,
                        'adresseComplete': item.get('adresseComplete')
                    }
                    results.append({k: v for k, v in error_result.items() if v is not None})
                    logging.error(f"Error processing {item.get('searchName')}: {e}")
            
            # Output tous les résultats (un par ligne pour n8n)
            for result in results:
                print(json.dumps(result, ensure_ascii=False))
                
            # Stats finales
            total = len(results)
            with_website = sum(1 for r in results if r.get('hasWebsite'))
            with_phone = sum(1 for r in results if r.get('phone'))
            logging.info(f"📊 Batch complete: {total} processed, {with_website} websites, {with_phone} phones")
                
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
            
            # ✅ ENRICHIR avec les données passées en paramètres
            enhanced_result = {
                'search_query': result['search_query'],
                'website_url': result.get('website_url'),
                'phone': result.get('phone'),
                'source': result.get('source'),
                'found_at': result.get('found_at'),
                'session_id': result.get('session_id'),
                
                # Données de l'entreprise
                'siren': args.siren,
                'siret': args.siret,
                'searchName': args.company_name,
                'activity': args.activity,
                'ville': args.city,
                'codePostal': args.zip_code,
                'departement': args.zip_code[:2] if args.zip_code else None,
                'adresseComplete': args.address,
                'isEI': args.is_ei,
                'batchNumber': args.batch_number,
                'searchQuery': args.query,
                
                # Données dérivées
                'hasWebsite': bool(result.get('website_url')),
                'websiteSource': result.get('source', 'not_found')
            }
            
            # Nettoyer les valeurs None
            enhanced_result = {k: v for k, v in enhanced_result.items() if v is not None}
            
            # Output JSON pour n8n
            print(json.dumps(enhanced_result, ensure_ascii=False))
            
        except Exception as e:
            error_result = {
                'search_query': args.query,
                'website_url': None,
                'phone': None,
                'source': 'error',
                'error': str(e),
                'found_at': datetime.now().isoformat(),
                'siren': args.siren,
                'searchName': args.company_name,
                'hasWebsite': False
            }
            # Nettoyer les valeurs None
            error_result = {k: v for k, v in error_result.items() if v is not None}
            
            print(json.dumps(error_result, ensure_ascii=False))
            logging.error(f"Website finder failed: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()
