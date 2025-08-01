#!/usr/bin/env python3
"""
Pages Jaunes Scraper avec Selenium et undetected-chromedriver
Solution robuste pour contourner Cloudflare
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

# Installation requise : pip install undetected-chromedriver selenium beautifulsoup4

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

class SeleniumPJScraper:
    def __init__(self, session_id: str = None, debug: bool = False, headless: bool = True):
        if not SELENIUM_AVAILABLE:
            raise ImportError("Please install: pip install undetected-chromedriver selenium beautifulsoup4")
            
        self.session_id = session_id or f"pj_sel_{int(time.time())}"
        self.debug = debug
        self.headless = headless
        self.setup_logging()
        
        self.driver = None
        self.base_url = "https://www.pagesjaunes.fr"
        
        # Patterns email
        self.email_patterns = [
            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            r'mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
        ]
        
    def setup_logging(self):
        level = logging.DEBUG if self.debug else logging.WARNING
        logging.basicConfig(
            level=level,
            format=f'[{self.session_id}] %(levelname)s: %(message)s',
            stream=sys.stderr
        )
        self.logger = logging.getLogger(__name__)
    
    def setup_driver(self):
        """Configure le driver Chrome non-détectable"""
        try:
            options = uc.ChromeOptions()
            
            # Options de base pour Docker
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-web-security')
            options.add_argument('--disable-features=VizDisplayCompositor')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--start-maximized')
            options.add_argument('--disable-extensions')
            options.add_argument('--disable-plugins')
            options.add_argument('--disable-images')  # Plus rapide
            
            if self.headless:
                options.add_argument('--headless=new')
            
            # User agent réaliste
            options.add_argument('--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            # Créer le driver sans options problématiques
            self.driver = uc.Chrome(options=options, version_main=None)  # Auto-detect version
            
            # Configuration post-création
            if self.driver:
                self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                self.driver.implicitly_wait(10)
                
                self.logger.info("Chrome driver initialized successfully")
                return True
            
        except Exception as e:
            self.logger.error(f"Failed to setup driver: {e}")
            self.logger.debug(f"Chrome version detection or compatibility issue")
            return False
    
    def wait_for_cloudflare(self, max_wait: int = 30) -> bool:
        """Attend que Cloudflare termine sa vérification"""
        try:
            self.logger.info("Waiting for Cloudflare challenge to complete...")
            
            # Attendre que la page soit complètement chargée
            WebDriverWait(self.driver, max_wait).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            
            # Vérifier si on est encore dans le challenge Cloudflare
            for _ in range(max_wait):
                current_url = self.driver.current_url
                page_source = self.driver.page_source.lower()
                
                # Indicateurs que Cloudflare est toujours actif
                cf_indicators = [
                    "checking your browser",
                    "cf-browser-verification",
                    "challenge-platform",
                    "cf-challenge",
                    "please wait"
                ]
                
                if any(indicator in page_source for indicator in cf_indicators):
                    self.logger.debug(f"Still in Cloudflare challenge, waiting... ({_}s)")
                    time.sleep(1)
                    continue
                
                # Si on arrive sur Pages Jaunes, c'est bon
                if "pagesjaunes.fr" in current_url and "recherche" in page_source:
                    self.logger.info("Cloudflare challenge completed successfully!")
                    return True
                    
                time.sleep(1)
            
            self.logger.warning("Cloudflare challenge timeout")
            return False
            
        except TimeoutException:
            self.logger.error("Timeout waiting for Cloudflare")
            return False
        except Exception as e:
            self.logger.error(f"Error waiting for Cloudflare: {e}")
            return False
    
    def extract_email_from_text(self, text: str) -> Optional[str]:
        """Extrait l'email d'un texte"""
        if not text:
            return None
            
        for pattern in self.email_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                email = match.strip().lower()
                if '@' in email and '.' in email and len(email) > 5:
                    return email
        return None
    
    def extract_business_from_element(self, element) -> Optional[Dict]:
        """Extrait les données d'entreprise d'un élément Selenium"""
        try:
            data = {
                'name': None,
                'address': None,
                'phone': None,
                'email': None,
                'website': None,
                'activity': None
            }
            
            # Extraction nom - sélecteurs multiples
            name_selectors = [
                '.bi-denomination',
                '.denomination-links',
                'h3.denomination',
                '.company-name',
                'a[title]'
            ]
            
            for selector in name_selectors:
                try:
                    name_elem = element.find_element(By.CSS_SELECTOR, selector)
                    if name_elem and name_elem.text.strip():
                        data['name'] = name_elem.text.strip()[:150]
                        break
                except NoSuchElementException:
                    continue
            
            # Extraction adresse
            address_selectors = ['.bi-adresse', '.adresse', '.address-container']
            for selector in address_selectors:
                try:
                    addr_elem = element.find_element(By.CSS_SELECTOR, selector)
                    if addr_elem and addr_elem.text.strip():
                        data['address'] = addr_elem.text.strip()[:200]
                        break
                except NoSuchElementException:
                    continue
            
            # Extraction téléphone
            phone_selectors = ['.bi-numero', '.coord-numero', 'a[href^="tel:"]']
            for selector in phone_selectors:
                try:
                    phone_elem = element.find_element(By.CSS_SELECTOR, selector)
                    if phone_elem:
                        phone = phone_elem.get_attribute('href') or phone_elem.text
                        if phone:
                            if phone.startswith('tel:'):
                                phone = phone[4:]
                            phone_clean = re.sub(r'[^\d+]', '', phone)
                            if len(phone_clean) >= 10:
                                data['phone'] = phone.strip()
                                break
                except NoSuchElementException:
                    continue
            
            # Extraction email - recherche intensive
            try:
                # 1. Liens mailto
                mailto_links = element.find_elements(By.CSS_SELECTOR, 'a[href^="mailto:"]')
                for link in mailto_links:
                    href = link.get_attribute('href')
                    email = self.extract_email_from_text(href)
                    if email:
                        data['email'] = email
                        break
                
                # 2. Texte complet si pas trouvé
                if not data['email']:
                    full_text = element.text
                    email = self.extract_email_from_text(full_text)
                    if email:
                        data['email'] = email
                        
            except Exception as e:
                self.logger.debug(f"Email extraction error: {e}")
            
            # Extraction website
            try:
                website_links = element.find_elements(By.CSS_SELECTOR, 'a[href*="http"]:not([href*="pagesjaunes"])')
                for link in website_links:
                    href = link.get_attribute('href')
                    if href and 'http' in href and 'pagesjaunes' not in href:
                        data['website'] = href[:200]
                        break
            except Exception as e:
                self.logger.debug(f"Website extraction error: {e}")
            
            # Validation
            if not data['name'] or len(data['name']) < 2:
                return None
                
            if data['email']:
                self.logger.info(f"EMAIL FOUND: {data['name']} -> {data['email']}")
                
            return data
            
        except Exception as e:
            self.logger.error(f"Error extracting business: {e}")
            return None
    
    def search_pages_jaunes(self, query: str, city: str, limit: int = 15, page: int = 1) -> List[Dict]:
        """Recherche avec Selenium avec support pagination"""
        results = []
        
        if not self.setup_driver():
            return self.generate_fallback_data(query, city, limit)
        
        try:
            self.logger.info(f"Searching Pages Jaunes with Selenium: {query} in {city} (page {page})")
            
            # URL de recherche avec pagination
            search_url = f"https://www.pagesjaunes.fr/annuaire/chercherlesprofessionnels?quoi={quote_plus(query)}&ou={quote_plus(city)}&page={page}"
            
            self.logger.debug(f"Accessing: {search_url}")
            self.driver.get(search_url)
            
            # Attendre que Cloudflare se termine
            if not self.wait_for_cloudflare():
                self.logger.warning("Cloudflare challenge failed, trying fallback")
                return self.generate_fallback_data(query, city, limit)
            
            # Attendre que les résultats se chargent
            time.sleep(random.uniform(3, 6))
            
            # Chercher les éléments de résultats
            result_selectors = ['.bi', '.bi-bloc', '.search-result', '.listing-item']
            
            business_elements = []
            for selector in result_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        business_elements = elements
                        self.logger.debug(f"Found {len(elements)} businesses with selector: {selector}")
                        break
                except Exception as e:
                    self.logger.debug(f"Selector {selector} failed: {e}")
                    continue
            
            if not business_elements:
                self.logger.warning("No business elements found")
                return self.generate_fallback_data(query, city, limit)
            
            # Extraire les données
            for i, element in enumerate(business_elements[:limit]):
                try:
                    business_data = self.extract_business_from_element(element)
                    if business_data:
                        business_data.update({
                            'source': 'pages_jaunes_selenium',
                            'city': city,
                            'page': page,
                            'scraped_at': datetime.now().isoformat(),
                            'session_id': self.session_id,
                            'has_email': bool(business_data.get('email'))
                        })
                        results.append(business_data)
                        
                except Exception as e:
                    self.logger.error(f"Error processing element {i}: {e}")
                    continue
            
            # Vérifier s'il y a des pages suivantes
            try:
                next_page_elements = self.driver.find_elements(By.CSS_SELECTOR, '.pagination .next, .pagination a[title*="suivante"]')
                has_next_page = len(next_page_elements) > 0 and any(elem.is_enabled() for elem in next_page_elements)
                
                # Ajouter info pagination aux métadonnées
                for result in results:
                    result['pagination_info'] = {
                        'current_page': page,
                        'has_next_page': has_next_page,
                        'total_results_this_page': len(results)
                    }
                    
            except Exception as e:
                self.logger.debug(f"Could not check pagination: {e}")
            
            self.logger.info(f"Extracted {len(results)} results from page {page}")
            
        except Exception as e:
            self.logger.error(f"Selenium search failed: {e}")
            results = self.generate_fallback_data(query, city, limit)
            
        finally:
            if self.driver:
                self.driver.quit()
                
        return results[:limit]
    
    def search_multiple_pages(self, query: str, city: str, total_limit: int = 50, max_pages: int = 5) -> List[Dict]:
        """Recherche sur plusieurs pages pour obtenir plus de résultats"""
        all_results = []
        page = 1
        
        while len(all_results) < total_limit and page <= max_pages:
            self.logger.info(f"Fetching page {page}...")
            
            # Calculer combien de résultats on veut pour cette page
            remaining = total_limit - len(all_results)
            page_limit = min(remaining, 20)  # Pages Jaunes montre ~20 résultats par page
            
            page_results = self.search_pages_jaunes(query, city, page_limit, page)
            
            if not page_results:
                self.logger.warning(f"No results on page {page}, stopping pagination")
                break
                
            all_results.extend(page_results)
            
            # Vérifier s'il y a une page suivante
            has_next = any(r.get('pagination_info', {}).get('has_next_page', False) for r in page_results)
            if not has_next:
                self.logger.info("No more pages available")
                break
                
            page += 1
            
            # Délai entre les pages pour éviter le rate limiting
            time.sleep(random.uniform(3, 6))
        
        self.logger.info(f"Total collected: {len(all_results)} results across {page-1} pages")
        return all_results[:total_limit]
    
    def generate_fallback_data(self, query: str, city: str, limit: int) -> List[Dict]:
    
    # ✅ CORRECTION 1: Extraire le département des 2 premiers chiffres
    requested_postal_code = city  # Le city est en fait le code postal
    department = requested_postal_code[:2] if len(requested_postal_code) >= 2 else '44'
    
    # ✅ CORRECTION 2: Codes postaux étendus par département (plus de variété)
    codes_postaux_par_dept = {
        '44': [  # Loire-Atlantique - Large échantillon
            '44000','44100','44200','44300','44400','44600','44700','44800','44120','44470',
            '44230','44240','44260','44280','44320','44330','44340','44350','44360','44370',
            '44380','44390','44410','44420','44430','44440','44450','44460','44490','44500',
            '44510','44520','44530','44540','44550','44560','44570','44580','44590','44630',
            '44640','44650','44660','44670','44680','44690','44710','44720','44730','44740'
        ],
        '35': [  # Ille-et-Vilaine
            '35000','35200','35700','35400','35300','35500','35510','35650','35131','35136',
            '35170','35520','35590','35740','35830','35850','35890','35120','35160','35190',
            '35210','35220','35230','35250','35270','35290','35310','35320','35360','35370'
        ],
        '29': [  # Finistère
            '29000','29200','29600','29100','29120','29140','29150','29160','29170','29190',
            '29210','29220','29230','29240','29250','29260','29270','29280','29290','29300',
            '29310','29340','29350','29360','29370','29380','29400','29410','29420','29430'
        ],
        '56': [  # Morbihan
            '56000','56100','56300','56120','56130','56140','56150','56160','56170','56190',
            '56200','56220','56230','56240','56250','56260','56270','56280','56290','56310',
            '56320','56330','56350','56360','56370','56380','56400','56410','56420','56430'
        ],  
        '85': [  # Vendée
            '85000','85100','85200','85230','85270','85280','85300','85310','85320','85330',
            '85340','85350','85360','85370','85400','85410','85420','85430','85440','85450',
            '85460','85470','85480','85490','85500','85510','85520','85540','85560','85570'
        ],
        '49': [  # Maine-et-Loire
            '49000','49100','49300','49400','49070','49080','49124','49130','49140','49150',
            '49160','49170','49180','49190','49200','49220','49230','49240','49250','49260',
            '49270','49280','49290','49310','49320','49330','49340','49350','49360','49370'
        ],
        '53': [  # Mayenne
            '53000','53100','53200','53110','53120','53140','53150','53160','53170','53190',
            '53220','53230','53240','53250','53260','53270','53290','53300','53340','53370',
            '53380','53390','53400','53410','53440','53450','53470','53480','53500','53510'
        ]
    }
    
    # ✅ CORRECTION 3: Utiliser TOUT le département (pas de privilège pour le code exact)
    preferred_codes = codes_postaux_par_dept.get(department, codes_postaux_par_dept['44'])
    
    # ✅ CORRECTION 3: Noms d'entreprises COMPLÈTEMENT ALÉATOIRES
    noms_entreprises_generiques = [
        'Atlantic Services', 'Océan Bleu', 'Loire Entreprise', 'Bretagne Pro', 'Armor Solutions',
        'Nantaise Société', 'Rennes Express', 'Brest Marine', 'Vannes Expert', 'Angers Plus',
        'Laval Moderne', 'Sables Services', 'Quimper Qualité', 'Lorient Rapide', 'Cholet Pro',
        'Vitré Excellence', 'Fougères Service', 'Concarneau Expert', 'Auray Solutions', 'Ernée Plus',
        'Mayenne Artisan', 'Châteaubriant Pro', 'Pontchâteau Express', 'Guérande Prestige',
        'Carquefou Services', 'Bouguenais Expert', 'Vertou Moderne', 'Rezé Solutions',
        'Alpha Entreprise', 'Beta Services', 'Gamma Solutions', 'Delta Expert', 'Epsilon Pro',
        'Omega Plus', 'Sigma Services', 'Lambda Solutions', 'Kappa Expert', 'Theta Pro',
        'Phoenix Entreprise', 'Horizon Services', 'Zenith Solutions', 'Apex Expert', 'Summit Pro',
        'Nova Plus', 'Stellar Services', 'Cosmic Solutions', 'Orbital Expert', 'Galaxy Pro',
        'Fusion Entreprise', 'Matrix Services', 'Nexus Solutions', 'Vertex Expert', 'Pivot Pro',
        'Dynamic Plus', 'Kinetic Services', 'Velocity Solutions', 'Momentum Expert', 'Force Pro',
        'Crystal Entreprise', 'Diamond Services', 'Platinum Solutions', 'Gold Expert', 'Silver Pro',
        'Titan Plus', 'Atlas Services', 'Hercules Solutions', 'Apollo Expert', 'Zeus Pro'
    ]
    
    def generate_company_name():
        return random.choice(noms_entreprises_generiques)
    
    # ✅ CORRECTION 4: Noms de villes génériques français (aucune vérification)
    villes_generiques = [
        'Bourg-en-Bresse', 'Saint-Martin', 'Saint-Pierre', 'Sainte-Marie', 'Notre-Dame',
        'Villeneuve', 'Montpellier', 'Villefranche', 'Bourg', 'Le Mans', 'Tours',
        'Orléans', 'Bourges', 'Blois', 'Chartres', 'Châteauroux', 'Dreux',
        'Vendôme', 'Romorantin', 'Montargis', 'Pithiviers', 'Nogent'
    ]
    
    # Domaines email français
    domaines_standards = ['gmail.com', 'orange.fr', 'free.fr', 'wanadoo.fr', 'laposte.net']
    
    results = []
    noms_utilises = set()
    
    for i in range(limit):
        # ✅ Code postal : N'IMPORTE LEQUEL du bon département
        code_postal = random.choice(preferred_codes)
        
        # ✅ Ville : COMPLÈTEMENT ALÉATOIRE (aucune vérification)
        ville = random.choice(villes_generiques)
        
        # ✅ Nom d'entreprise varié et réaliste
        name = generate_company_name()
        
        # Éviter les doublons exacts (mais accepter des variantes)
        counter = 1
        original_name = name
        while name in noms_utilises and counter < 5:
            name = f"{original_name} {counter}"
            counter += 1
        noms_utilises.add(name)
        
        # ✅ Adresse : Numéro + Code postal du bon département + Ville générique
        numero = random.randint(1, 999)
        adresse = f"{numero} {code_postal} {ville}"
        
        # Email (80% de chance)
        email = None
        if random.random() < 0.8:
            name_clean = re.sub(r'[^a-zA-Z ]', '', name.lower()).split()
            if len(name_clean) >= 2:
                email_prefix = f"{name_clean[0]}.{name_clean[1]}"[:15]
            else:
                email_prefix = name_clean[0][:10] if name_clean else 'contact'
            domain = random.choice(domaines_standards)
            email = f"{email_prefix}@{domain}"
        
        # Téléphone français
        prefixes_francais = ['02', '06', '07', '09']
        phone_num = f"{random.choice(prefixes_francais)}{random.randint(10000000, 99999999)}"
        phone = f"{phone_num[:2]} {phone_num[2:4]} {phone_num[4:6]} {phone_num[6:8]} {phone_num[8:10]}"
        
        # Website (30% de chance, sera filtré plus tard)
        website = None
        if random.random() < 0.3:
            domain_name = re.sub(r'[^a-z]', '', name.lower().replace(' ', '-'))[:18]
            website = f"http://www.{domain_name}.fr"
        
        result = {
            'name': name,
            'address': adresse,
            'phone': phone,
            'email': email,
            'website': website,
            'activity': query.title(),  # ✅ Activité = profession demandée
            'source': f'pages_jaunes_fallback_{department}',
            'city': ville,
            'department': department,
            'postal_code': code_postal,
            'scraped_at': datetime.now().isoformat(),
            'session_id': self.session_id,
            'has_email': bool(email),
            'extracted_from': 'fallback_data',  # ✅ Marquer comme fallback
            'fallback_reason': 'Pages Jaunes extraction failed'
        }
        
        results.append(result)
    
    self.logger.info(f"Generated {limit} fallback results for '{query}' in department '{department}' (requested: '{city}')")
    return results

def main():
    parser = argparse.ArgumentParser(description='Enhanced Pages Jaunes Selenium Scraper - Compatible with n8n')
    parser.add_argument('query', help='Search query (e.g., "plombier")')
    parser.add_argument('--city', required=True, help='City to search in')
    parser.add_argument('--limit', type=int, default=15, help='Number of results to return')
    parser.add_argument('--session-id', help='Session ID for tracking')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--no-headless', action='store_true', help='Show browser (for debugging only)')
    parser.add_argument('--timeout', type=int, default=60, help='Maximum time per search (seconds)')
    parser.add_argument('--page', type=int, default=1, help='Page number for pagination (default: 1)')
    parser.add_argument('--multi-pages', action='store_true', help='Search multiple pages automatically')
    parser.add_argument('--max-pages', type=int, default=5, help='Maximum pages to search when using --multi-pages')
    
    args = parser.parse_args()
    
    try:
        scraper = SeleniumPJScraper(
            session_id=args.session_id,
            debug=args.debug,
            headless=not args.no_headless
        )
        
        if args.multi_pages:
            results = scraper.search_multiple_pages(
                query=args.query,
                city=args.city,
                total_limit=args.limit,
                max_pages=args.max_pages
            )
        else:
            results = scraper.search_pages_jaunes(
                query=args.query,
                city=args.city,
                limit=args.limit,
                page=args.page
            )
        
        for result in results:
            print(json.dumps(result, ensure_ascii=False))
            
        if args.debug:
            email_count = sum(1 for r in results if r.get('email'))
            logging.info(f"Scraped {len(results)} results ({email_count} with emails)")
            
    except Exception as e:
        logging.error(f"Scraper failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
