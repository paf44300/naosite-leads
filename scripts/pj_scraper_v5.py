#!/usr/bin/env python3
"""
Pages Jaunes Scraper v5.0 - ROBUSTE 2025
Intègre une détection de sélecteurs adaptative, une configuration anti-détection avancée,
le contournement de Cloudflare et une configuration de proxy en clair.
"""

import json
import time
import argparse
import sys
import logging
import random
import os
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

# --- Configuration Proxy Webshare ---
PROXY_HOST = "p.webshare.io"
PROXY_PORT = 80
PROXY_USER = "xftpfnvt"
PROXY_PASS = "yulnmnbiq66j"
# ------------------------------------

class SeleniumPJScraperV5:
    """
    Scraper Pages Jaunes mis à jour pour 2025, avec proxy et contournement Cloudflare.
    """
    def __init__(self, session_id: str = None, debug: bool = False):
        if not SELENIUM_AVAILABLE:
            raise ImportError("Veuillez installer : pip install undetected-chromedriver selenium")

        self.session_id = session_id or f"pj_sel_v5_{int(time.time())}"
        self.debug = debug
        self.setup_logging()
        self.driver = None

        # Sélecteurs pour le challenge Cloudflare et les résultats
        self.CLOUDFLARE_CHALLENGE_SELECTOR = "h1.zone-name-title"
        self.RESULT_CONTAINER_SELECTORS = ["ul.bi-list", ".results-container", "#didomi-notice"]
        self.BUSINESS_ITEM_SELECTOR = "li.bi" # Sélecteur pour les fiches individuelles

    def setup_logging(self):
        level = logging.DEBUG if self.debug else logging.INFO
        logging.basicConfig(level=level, format=f'[{self.session_id}] %(levelname)s: %(message)s', stream=sys.stderr)
        self.logger = logging.getLogger(__name__)

    def create_driver(self):
        """Configure le driver avec les options anti-détection et le proxy."""
        try:
            options = uc.ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--window-size=1280,720')
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            
            # Création de l'extension pour l'authentification du proxy
            plugin_path = '/tmp/proxy_auth_plugin'
            manifest_json = """
            {
                "version": "1.0.0",
                "manifest_version": 2,
                "name": "Chrome Proxy",
                "permissions": ["proxy", "tabs", "unlimitedStorage", "storage", "<all_urls>", "webRequest", "webRequestBlocking"],
                "background": { "scripts": ["background.js"] }
            }
            """
            background_js = f"""
            var config = {{
                mode: "fixed_servers",
                rules: {{
                    singleProxy: {{ scheme: "http", host: "{PROXY_HOST}", port: {PROXY_PORT} }},
                    bypassList: ["localhost"]
                }}
            }};
            chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{}});
            function callbackFn(details) {{
                return {{ authCredentials: {{ username: "{PROXY_USER}", password: "{PROXY_PASS}" }} }};
            }}
            chrome.webRequest.onAuthRequired.addListener(
                callbackFn,
                {{urls: ["<all_urls>"]}},
                ['blocking']
            );
            """
            
            if not os.path.exists(plugin_path):
                os.makedirs(plugin_path)
            with open(os.path.join(plugin_path, "manifest.json"), "w") as f:
                f.write(manifest_json)
            with open(os.path.join(plugin_path, "background.js"), "w") as f:
                f.write(background_js)
            
            options.add_argument(f'--load-extension={plugin_path}')
            self.logger.info(f"Proxy Webshare configuré via extension : {PROXY_USER}@{PROXY_HOST}:{PROXY_PORT}")

            self.driver = uc.Chrome(options=options, version_main=None)
            self.driver.set_page_load_timeout(45)
            self.driver.implicitly_wait(10)
            self.logger.info("Driver Chrome v5 (avec proxy) initialisé.")
            return True
        except Exception as e:
            self.logger.error(f"Échec de la configuration du driver avec proxy : {e}")
            return False

    def search(self, query: str, city: str, limit: int = 15):
        if not self.create_driver():
            return []
            
        search_url = f"https://www.pagesjaunes.fr/annuaire/chercherlesprofessionnels?quoi={quote_plus(query)}&ou={quote_plus(city)}"
        results = []
        try:
            self.logger.info(f"Navigation vers : {search_url}")
            self.driver.get(search_url)

            time.sleep(10) # Attente généreuse pour le chargement initial avec le proxy

            # Gérer le consentement aux cookies s'il apparait
            try:
                cookie_button = WebDriverWait(self.driver, 5).until(EC.element_to_be_clickable((By.ID, 'didomi-notice-agree-button')))
                cookie_button.click()
                self.logger.info("Bannière de cookies acceptée.")
            except TimeoutException:
                self.logger.info("Pas de bannière de cookies détectée.")

            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ", ".join(self.RESULT_CONTAINER_SELECTORS)))
            )
            self.logger.info("✓ Conteneur de résultats trouvé.")

            business_elements = self.driver.find_elements(By.CSS_SELECTOR, self.BUSINESS_ITEM_SELECTOR)
            self.logger.info(f"Trouvé {len(business_elements)} fiches d'entreprises.")
            
            for element in business_elements[:limit]:
                 try:
                    name = element.find_element(By.CSS_SELECTOR, ".denomination-links").text.strip()
                    address = element.find_element(By.CSS_SELECTOR, ".adresse").text.strip()
                    results.append({'name': name, 'address': address, 'source': 'pj_v5_proxy'})
                 except NoSuchElementException:
                    continue
            
        except Exception as e:
            self.logger.error(f"Erreur critique de scraping : {e}")
            filename = f"debug_page_source_{self.session_id}.html"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(self.driver.page_source)
            self.logger.info(f"HTML sauvegardé dans : {filename}")
        finally:
            if self.driver:
                self.driver.quit()
        
        return results

def main():
    parser = argparse.ArgumentParser(description='Pages Jaunes Scraper v5.0 - Robuste avec Proxy')
    parser.add_argument('query', help='Activité à rechercher')
    parser.add_argument('--city', required=True, help='Code postal ou ville')
    parser.add_argument('--limit', type=int, default=15)
    parser.add_argument('--session-id', help='ID de session')
    parser.add_argument('--debug', action='store_true', help='Activer les logs détaillés')
    args = parser.parse_args()

    scraper = SeleniumPJScraperV5(session_id=args.session_id, debug=args.debug)
    results = scraper.search(query=args.query, city=args.city, limit=args.limit)

    if results:
        for result in results:
            print(json.dumps(result, ensure_ascii=False))
        scraper.logger.info(f"✓ Succès : {len(results)} résultats extraits via proxy.")
    else:
        scraper.logger.warning("❌ La recherche n'a retourné aucun résultat.")
        sys.exit(1)

if __name__ == "__main__":
    main()
