#!/usr/bin/env python3
"""
Pages Jaunes Scraper v5.0 - ROBUSTE 2025
Intègre une détection de sélecteurs adaptative, une configuration anti-détection avancée
et des attentes JavaScript pour contourner les protections modernes.
"""

import json
import time
import argparse
import sys
import logging
from typing import List, Dict, Optional
import random
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

class PagesJaunesScraperFixed:
    def __init__(self, debug=False):
        self.driver = None
        self.session_id = f"pj_sel_v5_{int(time.time())}"
        self.debug = debug
        self.setup_logging()
        self.fallback_selectors = [
            ".bi-result", "[data-test='business-result']",
            ".result-item", "article", "[role='article']"
        ]
        self.DATA_SELECTORS = {
            'name': ['h2', 'h3', '.business-name', '.denomination'],
            'address': ['.address', '.location', '.adresse'],
        }

    def setup_logging(self):
        level = logging.DEBUG if self.debug else logging.INFO
        logging.basicConfig(
            level=level,
            format=f'[{self.session_id}] %(levelname)s: %(message)s',
            stream=sys.stderr
        )
        self.logger = logging.getLogger(__name__)

    def create_driver(self):
        options = uc.ChromeOptions()
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-web-security')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

        # Mode non-headless est crucial pour Pages Jaunes
        self.driver = uc.Chrome(options=options, use_subprocess=False)
        self.driver.set_page_load_timeout(30)
        self.driver.implicitly_wait(5)
        self.logger.info("Driver optimisé créé.")

    def scrape_safely(self, url):
        try:
            # Navigation en deux étapes
            self.driver.get("https://www.google.com")
            self.logger.info("Navigation vers Google (étape 1/2)...")
            time.sleep(random.uniform(2, 4))
            
            self.driver.get(url)
            self.logger.info(f"Navigation vers Pages Jaunes (étape 2/2)...")

            # Attendre le chargement JavaScript
            wait = WebDriverWait(self.driver, 30)
            wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
            
            # Test des sélecteurs de fallback
            for selector in self.fallback_selectors:
                try:
                    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    if len(elements) > 0:
                        self.logger.info(f"✓ Sélecteur réussi: {selector}")
                        return self.extract_business_data(elements)
                        
                except Exception:
                    continue
            
            # Si aucun sélecteur ne fonctionne, debug
            self.logger.error("❌ Tous les sélecteurs ont échoué")
            self.debug_empty_selectors()
            return []
            
        except Exception as e:
            self.logger.error(f"Erreur de scraping: {e}")
            self.debug_empty_selectors()
            return []

    def extract_business_data(self, elements):
        results = []
        for element in elements:
            try:
                data = {}
                for key, selectors in self.DATA_SELECTORS.items():
                    for selector in selectors:
                        try:
                            el = element.find_element(By.CSS_SELECTOR, selector)
                            data[key] = el.text.strip()
                            if data.get(key): break
                        except NoSuchElementException:
                            continue
                
                if data.get('name'):
                    results.append(data)
            except Exception:
                continue
        
        return results

    def debug_empty_selectors(self):
        filename = f"debug_pages_jaunes_{self.session_id}.html"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(self.driver.page_source)
        self.logger.info(f"HTML sauvegardé dans {filename} pour analyse manuelle.")
    
    def cleanup(self):
        if self.driver:
            self.driver.quit()

def main():
    parser = argparse.ArgumentParser(description='Pages Jaunes Scraper v5 - Robuste 2025')
    parser.add_argument('query', help='Activité à rechercher')
    parser.add_argument('--city', required=True, help='Code postal ou ville')
    parser.add_argument('--debug', action='store_true', help='Activer les logs de débogage')
    args = parser.parse_args()

    scraper = PagesJaunesScraperFixed(debug=args.debug)
    
    try:
        scraper.create_driver()
        url = f"https://www.pagesjaunes.fr/annuaire/chercherlesprofessionnels?quoi={quote_plus(args.query)}&ou={quote_plus(args.city)}&page=1"
        
        results = scraper.scrape_safely(url)
        
        if results:
            # Output JSON pour n8n
            for result in results:
                print(json.dumps(result, ensure_ascii=False))
            scraper.logger.info(f"✓ {len(results)} résultats extraits.")
        else:
            scraper.logger.warning("❌ Aucun résultat - vérifiez le fichier HTML de débogage.")
    
    finally:
        scraper.cleanup()

if __name__ == "__main__":
    main()
