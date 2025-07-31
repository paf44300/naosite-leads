#!/usr/bin/env python3
"""
Pages Jaunes Scraper v5.0 - SELENIUM & ANTI-CLOUDFLARE
Utilise Selenium et undetected-chromedriver pour contourner Cloudflare.
Intègre un proxy authentifié Webshare.
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
import zipfile
import os

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

# --- Configuration du Proxy Webshare ---
PROXY_HOST = "p.webshare.io"
PROXY_PORT = "80"
PROXY_USER = "xftpfnvt"
PROXY_PASS = "yulnmnbiq66j"

class SeleniumPJScraper:
    def __init__(self, session_id: str = None, debug: bool = False, headless: bool = True):
        if not SELENIUM_AVAILABLE:
            raise ImportError("Veuillez installer les dépendances : pip install undetected-chromedriver selenium beautifulsoup4")

        self.session_id = session_id or f"pj_sel_{int(time.time())}"
        self.debug = debug
        self.headless = headless
        self.driver = None
        self.base_url = "https://www.pagesjaunes.fr"
        self.setup_logging()

    def setup_logging(self):
        level = logging.DEBUG if self.debug else logging.INFO
        logging.basicConfig(
            level=level,
            format=f'[{self.session_id}] %(levelname)s: %(message)s',
            stream=sys.stderr
        )
        self.logger = logging.getLogger(__name__)

    def get_proxy_extension(self):
        """Crée une extension Chrome pour gérer l'authentification du proxy."""
        manifest_json = """
        {
            "version": "1.0.0",
            "manifest_version": 2,
            "name": "Chrome Proxy",
            "permissions": ["proxy", "tabs", "unlimitedStorage", "storage", "<all_urls>", "webRequest", "webRequestBlocking"],
            "background": {"scripts": ["background.js"]},
            "minimum_chrome_version":"22.0.0"
        }
        """
        background_js = """
        var config = {
            mode: "fixed_servers",
            rules: {
                singleProxy: {
                    scheme: "http",
                    host: "%s",
                    port: parseInt(%s)
                },
                bypassList: ["localhost"]
            }
        };
        chrome.proxy.settings.set({value: config, scope: "regular"}, function() {});
        function callbackFn(details) {
            return {
                authCredentials: {
                    username: "%s",
                    password: "%s"
                }
            };
        }
        chrome.webRequest.onAuthRequired.addListener(
            callbackFn,
            {urls: ["<all_urls>"]},
            ['blocking']
        );
        """ % (PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS)

        plugin_file = 'proxy_auth_plugin.zip'
        with zipfile.ZipFile(plugin_file, 'w') as zp:
            zp.writestr("manifest.json", manifest_json)
            zp.writestr("background.js", background_js)
        return plugin_file

    def setup_driver(self):
        """Configure le driver Chrome non-détectable avec le proxy."""
        try:
            options = uc.ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--disable-blink-features=AutomationControlled')

            if self.headless:
                options.add_argument('--headless=new')
            
            # Ajout de l'extension pour le proxy
            proxy_extension = self.get_proxy_extension()
            options.add_extension(proxy_extension)

            self.logger.info("Initialisation du driver Chrome avec proxy...")
            self.driver = uc.Chrome(options=options, version_main=None) # Détection auto de la version
            
            # Nettoyage du fichier de l'extension
            if os.path.exists(proxy_extension):
                os.remove(proxy_extension)

            if self.driver:
                self.logger.info("Driver initialisé avec succès.")
                return True
            return False

        except Exception as e:
            self.logger.error(f"Erreur lors de la configuration du driver : {e}")
            return False

    def wait_for_cloudflare(self, max_wait: int = 45):
        """Attend que la vérification Cloudflare soit terminée."""
        self.logger.info("Attente de la résolution du challenge Cloudflare...")
        time.sleep(5) # Attente initiale
        try:
            WebDriverWait(self.driver, max_wait).until_not(
                EC.presence_of_element_located((By.ID, "cf-challenge-running"))
            )
            self.logger.info("Challenge Cloudflare passé avec succès.")
            return True
        except TimeoutException:
            self.logger.error("Timeout en attendant la fin du challenge Cloudflare.")
            return False

    def extract_business_details(self, soup_element: BeautifulSoup) -> Optional[Dict]:
        """Extrait les détails d'une entreprise à partir d'un élément BeautifulSoup."""
        # La logique d'extraction de pj_scraper_v4_REAL.py est conservée
        # et fonctionne bien avec BeautifulSoup.
        try:
            data = {'name': None, 'address': None, 'phone': None, 'email': None, 'website': None}
            
            # Nom
            name_elem = soup_element.select_one('.bi-denomination, .denomination-links, h3.denomination')
            if name_elem: data['name'] = name_elem.get_text(strip=True)[:150]

            # Adresse
            address_elem = soup_element.select_one('.bi-adresse, .adresse')
            if address_elem: data['address'] = address_elem.get_text(strip=True)[:200]

            # Téléphone
            phone_elem = soup_element.select_one('.bi-numero, .coord-numero, a[href^="tel:"]')
            if phone_elem:
                phone_raw = phone_elem.get('href') or phone_elem.get_text(strip=True)
                if 'tel:' in phone_raw: phone_raw = phone_raw.replace('tel:', '')
                if len(re.sub(r'\D', '', phone_raw)) >= 10: data['phone'] = phone_raw.strip()

            # Email
            email_elem = soup_element.select_one('a[href^="mailto:"]')
            if email_elem: data['email'] = email_elem.get('href').replace('mailto:', '')

            # Website (on s'assure de ne pas prendre les liens pagesjaunes)
            website_elem = soup_element.select_one('a.bi-site-web[href*="http"]:not([href*="pagesjaunes"])')
            if website_elem: data['website'] = website_elem.get('href')

            if not data['name']: return None
            return data

        except Exception as e:
            self.logger.error(f"Erreur d'extraction des détails : {e}")
            return None


    def search_pages_jaunes(self, query: str, city: str, limit: int = 15) -> List[Dict]:
        """Recherche sur Pages Jaunes en utilisant Selenium."""
        if not self.setup_driver():
            self.logger.error("Impossible de démarrer le driver. Abandon.")
            return []

        results = []
        try:
            search_url = f"{self.base_url}/annuaire/chercherlesprofessionnels?quoi={quote_plus(query)}&ou={quote_plus(city)}"
            self.logger.info(f"Navigation vers : {search_url}")
            self.driver.get(search_url)

            # Gérer le challenge Cloudflare
            self.wait_for_cloudflare()

            # Attendre que les résultats se chargent
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'ul.bi-list li.bi'))
            )
            self.logger.info("Liste de résultats chargée.")
            
            # Utiliser BeautifulSoup pour parser le HTML de la page, car c'est plus simple
            # et la logique d'extraction est déjà écrite pour ça.
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            business_elements = soup.select('ul.bi-list li.bi')
            
            self.logger.info(f"{len(business_elements)} fiches d'entreprises trouvées.")

            for element in business_elements[:limit]:
                business_data = self.extract_business_details(element)
                if business_data:
                    business_data.update({
                        'source': 'pages_jaunes_selenium_v5',
                        'city': city,
                        'scraped_at': datetime.now().isoformat(),
                        'session_id': self.session_id,
                        'has_email': bool(business_data.get('email'))
                    })
                    results.append(business_data)
        
        except Exception as e:
            self.logger.error(f"Une erreur est survenue pendant le scraping : {e}")
            # Sauvegarde de la page pour débogage
            with open('error_page.html', 'w', encoding='utf-8') as f:
                f.write(self.driver.page_source)
            self.logger.info("La page source a été sauvegardée dans error_page.html")
            
        finally:
            if self.driver:
                self.driver.quit()
        
        return results[:limit]

def main():
    parser = argparse.ArgumentParser(description="Pages Jaunes Scraper v5.0 - Selenium & Anti-Cloudflare")
    parser.add_argument('query', help='Activité à rechercher (ex: "plombier")')
    parser.add_argument('--city', required=True, help='Ville où chercher')
    parser.add_argument('--limit', type=int, default=15, help='Nombre de résultats à retourner')
    parser.add_argument('--session-id', help='ID de session pour le suivi')
    parser.add_argument('--debug', action='store_true', help='Activer les logs de débogage')
    parser.add_argument('--no-headless', dest='headless', action='store_false', help='Lancer le navigateur en mode visible pour le débogage')
    
    args = parser.parse_args()
    
    scraper = SeleniumPJScraper(
        session_id=args.session_id,
        debug=args.debug,
        headless=args.headless
    )
    
    results = scraper.search_pages_jaunes(
        query=args.query,
        city=args.city,
        limit=args.limit
    )
    
    for result in results:
        print(json.dumps(result, ensure_ascii=False))
        
    if args.debug:
        email_count = sum(1 for r in results if r.get('email'))
        scraper.logger.info(f"Scraping terminé. {len(results)} résultats extraits, dont {email_count} avec email.")

if __name__ == "__main__":
    main()
