#!/usr/bin/env python3
"""
Pages Jaunes Scraper v5.0 (FINAL) - Robuste avec Proxy et Bypass Cloudflare
Combine une navigation directe avec une attente intelligente de la résolution
du challenge Cloudflare avant de scraper les données.
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

# --- Configuration Proxy Webshare (en clair) ---
PROXY_HOST = "p.webshare.io"
PROXY_PORT = 80
PROXY_USER = "xftpfnvt"
PROXY_PASS = "yulnmnbiq66j"
# ----------------------------------------------

class SeleniumPJScraperV5:
    def __init__(self, session_id: str = None, debug: bool = False):
        if not SELENIUM_AVAILABLE:
            raise ImportError("Veuillez installer : pip install undetected-chromedriver selenium")

        self.session_id = session_id or f"pj_sel_v5_{int(time.time())}"
        self.debug = debug
        self.setup_logging()
        self.driver = None

        # Sélecteurs critiques
        self.CLOUDFLARE_CHALLENGE_SELECTOR = "body[class*='no-js']" # Sélecteur présent sur la page "Just a moment..."
        self.RESULT_CONTAINER_SELECTOR = "#list-container" # Conteneur principal des résultats
        self.BUSINESS_ITEM_SELECTOR = "li.bi" 

    def setup_logging(self):
        level = logging.DEBUG if self.debug else logging.INFO
        logging.basicConfig(level=level, format=f'[{self.session_id}] %(levelname)s: %(message)s', stream=sys.stderr)
        self.logger = logging.getLogger(__name__)

    def create_driver(self):
        try:
            options = uc.ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--window-size=1366,768')
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')
            
            # Configuration du proxy via une extension
            plugin_path = '/tmp/proxy_auth_plugin'
            manifest_json = """
            { "version": "1.0.0", "manifest_version": 2, "name": "Chrome Proxy", "permissions": ["proxy", "<all_urls>", "webRequest", "webRequestBlocking"], "background": { "scripts": ["background.js"] } }
            """
            background_js = f"""
            var config = {{ mode: "fixed_servers", rules: {{ singleProxy: {{ scheme: "http", host: "{PROXY_HOST}", port: {PROXY_PORT} }} }} }};
            chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{}});
            function callbackFn(details) {{ return {{ authCredentials: {{ username: "{PROXY_USER}", password: "{PROXY_PASS}" }} }}; }}
            chrome.webRequest.onAuthRequired.addListener(callbackFn, {{urls: ["<all_urls>"]}}, ['blocking']);
            """
            if not os.path.exists(plugin_path): os.makedirs(plugin_path)
            with open(os.path.join(plugin_path, "manifest.json"), "w") as f: f.write(manifest_json)
            with open(os.path.join(plugin_path, "background.js"), "w") as f: f.write(background_js)
            options.add_argument(f'--load-extension={plugin_path}')
            self.logger.info(f"Proxy Webshare configuré : {PROXY_USER}@{PROXY_HOST}")

            self.driver = uc.Chrome(options=options, version_main=None, enable_cdp_events=True)
            self.driver.set_page_load_timeout(60)
            self.driver.implicitly_wait(15)
            self.logger.info("Driver Chrome v5 (avec proxy) initialisé.")
            return True
        except Exception as e:
            self.logger.error(f"Échec de la configuration du driver : {e}", exc_info=True)
            return False

    def search(self, query: str, city: str, limit: int = 15):
        if not self.create_driver(): return []
            
        search_url = f"https://www.pagesjaunes.fr/annuaire/chercherlesprofessionnels?quoi={quote_plus(query)}&ou={quote_plus(city)}"
        results = []
        try:
            self.logger.info(f"Navigation directe vers : {search_url}")
            self.driver.get(search_url)

            # **Attente active de la fin du challenge Cloudflare**
            self.logger.info("Attente de la résolution du challenge Cloudflare (max 40s)...")
            WebDriverWait(self.driver, 40).until_not(
                EC.presence_of_element_located((By.CSS_SELECTOR, self.CLOUDFLARE_CHALLENGE_SELECTOR))
            )
            self.logger.info("✓ Challenge Cloudflare passé.")
            time.sleep(random.uniform(2, 4)) # Attente pour la stabilisation de la page

            # Accepter les cookies
            try:
                cookie_button = WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.ID, 'didomi-notice-agree-button')))
                cookie_button.click()
                self.logger.info("Bannière de cookies acceptée.")
            except TimeoutException:
                self.logger.info("Pas de bannière de cookies détectée.")

            # Attendre que les résultats soient chargés
            WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, self.RESULT_CONTAINER_SELECTOR)))
            self.logger.info("✓ Conteneur de résultats trouvé.")

            business_elements = self.driver.find_elements(By.CSS_SELECTOR, self.BUSINESS_ITEM_SELECTOR)
            self.logger.info(f"Trouvé {len(business_elements)} fiches d'entreprises.")
            
            for element in business_elements[:limit]:
                 try:
                    name = element.find_element(By.CSS_SELECTOR, "h3.denomination, .denomination-links").text.strip()
                    address = element.find_element(By.CSS_SELECTOR, ".adresse").text.strip()
                    results.append({'name': name, 'address': address, 'source': 'pj_v5_proxy'})
                 except NoSuchElementException:
                    continue
            
        except TimeoutException:
            self.logger.error("Timeout: La page ou les résultats n'ont pas chargé à temps après le challenge.")
            self.debug_and_save_page()
        except Exception as e:
            self.logger.error(f"Erreur critique de scraping : {e}", exc_info=True)
            self.debug_and_save_page()
        finally:
            if self.driver:
                self.driver.quit()
        
        return results

    def debug_and_save_page(self):
        if not self.driver: return
        filename = f"debug_page_source_{self.session_id}.html"
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(self.driver.page_source)
            self.logger.info(f"HTML sauvegardé dans : {filename}")
        except Exception as e:
            self.logger.error(f"Impossible de sauvegarder le fichier de débogage : {e}")

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
        scraper.logger.info(f"✓ Succès : {len(results)} résultats extraits.")
    else:
        scraper.logger.warning("❌ La recherche n'a retourné aucun résultat.")
        sys.exit(1)

if __name__ == "__main__":
    main()
