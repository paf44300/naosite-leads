#!/usr/bin/env python3
"""
Pages Jaunes Scraper v5.0 (FINAL) - Inspiré de la v4 avec Proxy et Bypass Cloudflare
Combine la navigation directe et la logique de 'wait_for_cloudflare' de la v4 avec
une configuration de proxy robuste pour une performance optimale en 2025.
"""

import json
import time
import argparse
import sys
import logging
import re
from typing import List, Dict, Optional
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
    def __init__(self, session_id: str = None, debug: bool = False, headless: bool = True):
        if not SELENIUM_AVAILABLE:
            raise ImportError("Veuillez installer : pip install undetected-chromedriver selenium")
            
        self.session_id = session_id or f"pj_sel_v5_{int(time.time())}"
        self.debug = debug
        # Le mode headless est souvent détecté, mais on le garde comme option
        self.headless = headless
        self.setup_logging()
        
        self.driver = None
        self.base_url = "https://www.pagesjaunes.fr"

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
            options.add_argument('--window-size=1366,768')
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')

            if self.headless:
                self.logger.warning("Mode headless activé. La détection par Cloudflare est plus probable.")
                options.add_argument('--headless=new')

            # --- Configuration du Proxy ---
            plugin_path = '/tmp/proxy_auth_plugin'
            manifest_json = """
            { "version": "1.0.0", "manifest_version": 2, "name": "Chrome Proxy", "permissions": ["proxy", "<all_urls>", "webRequest", "webRequestBlocking"], "background": { "scripts": ["background.js"] } }
            """
            background_js = f'''
            var config = {{ mode: "fixed_servers", rules: {{ singleProxy: {{ scheme: "http", host: "{PROXY_HOST}", port: {PROXY_PORT} }} }} }};
            chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{}});
            function callbackFn(details) {{ return {{ authCredentials: {{ username: "{PROXY_USER}", password: "{PROXY_PASS}" }} }}; }}
            chrome.webRequest.onAuthRequired.addListener(callbackFn, {{urls: ["<all_urls>"]}}, ['blocking']);
            '''
            if not os.path.exists(plugin_path): os.makedirs(plugin_path)
            with open(os.path.join(plugin_path, "manifest.json"), "w") as f: f.write(manifest_json)
            with open(os.path.join(plugin_path, "background.js"), "w") as f: f.write(background_js)
            options.add_argument(f'--load-extension={plugin_path}')
            self.logger.info(f"Proxy Webshare configuré : {PROXY_USER}@{PROXY_HOST}")

            self.driver = uc.Chrome(options=options, version_main=None)
            self.driver.set_page_load_timeout(60)
            self.driver.implicitly_wait(10)
            self.logger.info("Driver Chrome v5 (avec proxy) initialisé.")
            return True
        except Exception as e:
            self.logger.error(f"Échec de la configuration du driver : {e}", exc_info=True)
            return False
    
    def wait_for_cloudflare(self, max_wait: int = 40) -> bool:
        """Attend activement que le challenge Cloudflare se termine."""
        self.logger.info("Attente de la résolution du challenge Cloudflare...")
        try:
            WebDriverWait(self.driver, max_wait).until_not(
                EC.title_contains("Just a moment...")
            )
            # Vérification supplémentaire qu'on est bien sur PagesJaunes
            time.sleep(2)
            if "pagesjaunes.fr" in self.driver.current_url:
                self.logger.info("✓ Challenge Cloudflare passé avec succès.")
                return True
            else:
                self.logger.warning("La page n'est pas PagesJaunes après le challenge.")
                return False
        except TimeoutException:
            self.logger.error("Timeout : Le challenge Cloudflare n'a pas été résolu à temps.")
            return False
        except Exception as e:
            self.logger.error(f"Erreur inattendue pendant l'attente Cloudflare: {e}")
            return False

    def search(self, query: str, city: str, limit: int = 15):
        if not self.create_driver(): return []
            
        search_url = f"https://www.pagesjaunes.fr/annuaire/chercherlesprofessionnels?quoi={quote_plus(query)}&ou={quote_plus(city)}"
        results = []
        try:
            self.logger.info(f"Navigation directe vers : {search_url}")
            self.driver.get(search_url)

            if not self.wait_for_cloudflare():
                self.debug_and_save_page("cloudflare_failed")
                return []

            # Accepter les cookies
            try:
                cookie_button = WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.ID, 'didomi-notice-agree-button')))
                cookie_button.click()
                self.logger.info("Bannière de cookies acceptée.")
            except TimeoutException:
                self.logger.info("Pas de bannière de cookies détectée.")

            # Attendre que les résultats soient chargés
            WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, "li.bi")))
            self.logger.info("✓ Conteneur de résultats trouvé.")

            business_elements = self.driver.find_elements(By.CSS_SELECTOR, "li.bi")
            self.logger.info(f"Trouvé {len(business_elements)} fiches d'entreprises.")
            
            for element in business_elements[:limit]:
                try:
                    name = element.find_element(By.CSS_SELECTOR, "h3.denomination, .denomination-links").text.strip()
                    address = element.find_element(By.CSS_SELECTOR, ".adresse").text.strip()
                    results.append({'name': name, 'address': address, 'source': 'pj_v5_proxy'})
                except NoSuchElementException:
                    continue
            
        except Exception as e:
            self.logger.error(f"Erreur critique de scraping : {e}", exc_info=True)
            self.debug_and_save_page("critical_error")
        finally:
            if self.driver:
                self.driver.quit()
        
        return results

    def debug_and_save_page(self, reason: str):
        if not self.driver: return
        filename = f"debug_{reason}_{self.session_id}.html"
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(self.driver.page_source)
            self.logger.info(f"HTML sauvegardé dans : {filename}")
        except Exception as e:
            self.logger.error(f"Impossible de sauvegarder le fichier de débogage : {e}")

def main():
    # Correction de l'parser d'arguments pour correspondre à n8n
    parser = argparse.ArgumentParser(description='Pages Jaunes Scraper v5 - Robuste avec Proxy')
    parser.add_argument('query', help='Activité à rechercher (ex: "plombier")')
    parser.add_argument('--city', required=True, help='Code postal ou ville (ex: "44000")')
    parser.add_argument('--limit', type=int, default=15)
    parser.add_argument('--session-id', help='ID de session pour le suivi')
    parser.add_argument('--debug', action='store_true', help='Activer les logs détaillés')
    parser.add_argument('--no-headless', action='store_true', help='(NON RECOMMANDÉ) Exécuter avec une interface graphique')
    args = parser.parse_args()

    scraper = SeleniumPJScraperV5(
        session_id=args.session_id,
        debug=args.debug,
        headless=not args.no_headless
    )
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
