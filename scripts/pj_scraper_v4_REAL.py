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
import re
from typing import List, Dict, Optional
import random
from datetime import datetime
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

class SeleniumPJScraperV5:
    """
    Scraper Pages Jaunes mis à jour pour 2025, basé sur l'analyse de la nouvelle
    architecture anti-scraping du site.
    """
    def __init__(self, session_id: str = None, debug: bool = False, headless: bool = False):
        if not SELENIUM_AVAILABLE:
            raise ImportError("Veuillez installer : pip install undetected-chromedriver selenium")

        self.session_id = session_id or f"pj_sel_v5_{int(time.time())}"
        self.debug = debug
        
        # Le mode headless est désactivé par défaut car il est facilement détectable
        self.headless = headless
        self.setup_logging()

        # NOUVEAUX SÉLECTEURS DE FALLBACK (2025)
        self.FALLBACK_SELECTORS = [
            ".bi-result",
            "[data-test='business-result']",
            ".result-item",
            "[class*='result-item']",
            "article[role='article']",
            ".listing-item",
            "[role='listitem']"
        ]
        
        # Sélecteurs internes pour extraire les données d'une fiche
        self.DATA_SELECTORS = {
            'name': ['h3', 'h2', '.denomination', '[itemprop="name"]'],
            'address': ['.adresse', '[itemprop="address"]', '.address-container'],
            'phone': ['.num', '[itemprop="telephone"]', 'a[href^="tel:"]'],
            'website': ['a[href*="http"]:not([href*="pagesjaunes"])']
        }

        self.driver = None

    def setup_logging(self):
        level = logging.DEBUG if self.debug else logging.INFO
        logging.basicConfig(
            level=level,
            format=f'[{self.session_id}] %(levelname)s: %(message)s',
            stream=sys.stderr
        )
        self.logger = logging.getLogger(__name__)

    def create_optimized_driver(self):
        """Configuration du driver avec les options anti-détection critiques."""
        try:
            options = uc.ChromeOptions()
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--disable-web-security')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--no-sandbox')
            options.add_argument('--window-size=1280,720')
            options.add_argument('--disable-images')
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

            if self.headless:
                self.logger.warning("Le mode headless est activé, la détection par Pages Jaunes est probable.")
                options.add_argument('--headless=new')

            self.driver = uc.Chrome(options=options, version_main=None, use_subprocess=True)
            self.driver.set_page_load_timeout(45)
            self.driver.implicitly_wait(5)
            
            self.logger.info("Driver Chrome optimisé initialisé avec succès.")
            return True
        except Exception as e:
            self.logger.error(f"Échec de la configuration du driver : {e}")
            return False

    def wait_for_full_load(self, timeout: int = 30):
        """Attend que la page, y compris les scripts JS et Cloudflare, soit chargée."""
        wait = WebDriverWait(self.driver, timeout)
        try:
            # 1. Attendre que le DOM soit prêt
            wait.until(lambda d: d.execute_script('return document.readyState') == 'complete')
            self.logger.debug("document.readyState est 'complete'.")

            # 2. Attendre la fin des requêtes AJAX (si jQuery est utilisé)
            try:
                wait.until(lambda d: d.execute_script('return (typeof jQuery === "undefined") || (jQuery.active === 0)'))
                self.logger.debug("jQuery.active est 0.")
            except TimeoutException:
                self.logger.warning("Timeout sur l'attente jQuery, continuation.")

            # 3. Attendre qu'un des sélecteurs de résultats soit présent
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ", ".join(self.FALLBACK_SELECTORS))))
            self.logger.info("Contenu dynamique (fiches) détecté.")
            
            # 4. Pause finale pour simuler un comportement humain
            time.sleep(random.uniform(2, 4))
            return True
        except TimeoutException:
            self.logger.error("Timeout: La page ou le contenu dynamique n'a pas chargé à temps.")
            return False

    def access_safely(self, url: str):
        """Accède à l'URL cible en deux étapes pour paraître plus humain."""
        try:
            # Étape 1 : Visiter un site neutre
            self.driver.get("https://www.google.com")
            self.logger.info("Navigation vers google.com (étape 1/2)")
            time.sleep(random.uniform(1.5, 3))
            
            # Étape 2 : Accéder à Pages Jaunes
            self.logger.info(f"Navigation vers Pages Jaunes (étape 2/2): {url}")
            self.driver.get(url)

            # Gérer le consentement aux cookies
            try:
                consent_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, '#toutAccepter'))
                )
                consent_button.click()
                self.logger.info("Consentement aux cookies accepté.")
                time.sleep(1)
            except TimeoutException:
                self.logger.info("Pas de bannière de cookies ou déjà acceptée.")

            return self.wait_for_full_load()
        except Exception as e:
            self.logger.error(f"Erreur lors de la navigation sécurisée : {e}")
            return False

    def find_business_elements(self) -> List:
        """Tente de trouver les fiches de résultats en testant les sélecteurs de fallback."""
        self.logger.info("Recherche des fiches de résultats avec les sélecteurs de fallback...")
        for selector in self.FALLBACK_SELECTORS:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    self.logger.info(f"✓ Sélecteur valide trouvé : '{selector}' ({len(elements)} fiches)")
                    return elements
            except NoSuchElementException:
                continue
        self.logger.error("❌ Aucun sélecteur de fiche n'a fonctionné.")
        return []

    def extract_data_from_element(self, element) -> Optional[Dict]:
        """Extrait les données d'une seule fiche entreprise."""
        data = {}
        for key, selectors in self.DATA_SELECTORS.items():
            for selector in selectors:
                try:
                    el = element.find_element(By.CSS_SELECTOR, selector)
                    if key == 'phone':
                        # Gérer les numéros cachés derrière un clic
                        try:
                            # Tenter de cliquer pour afficher le numéro
                            display_button = el.find_element(By.XPATH, ".//span[contains(text(), 'Afficher le N')]")
                            self.driver.execute_script("arguments[0].click();", display_button)
                            time.sleep(0.5)
                        except:
                            pass
                        data[key] = el.text.strip() or el.get_attribute('href').replace('tel:', '')
                    elif key == 'website':
                        data[key] = el.get_attribute('href')
                    else:
                        data[key] = el.text.strip()
                    
                    if data.get(key):
                        break
                except NoSuchElementException:
                    continue
        
        if not data.get('name'):
            return None # Rejeter les fiches sans nom (souvent des pubs)
            
        return data

    def search(self, query: str, city: str, limit: int = 15) -> List[Dict]:
        """Lance une recherche complète et robuste."""
        if not self.create_optimized_driver():
            return []

        search_url = f"https://www.pagesjaunes.fr/annuaire/chercherlesprofessionnels?quoi={quote_plus(query)}&ou={quote_plus(city)}"
        
        results = []
        try:
            if not self.access_safely(search_url):
                self.debug_and_save_page()
                return []
            
            business_elements = self.find_business_elements()
            if not business_elements:
                self.debug_and_save_page()
                return []

            self.logger.info(f"Extraction des données de {len(business_elements)} fiches...")
            for element in business_elements[:limit]:
                business_data = self.extract_data_from_element(element)
                if business_data:
                    business_data.update({
                        'source': 'pages_jaunes_selenium_v5',
                        'activity': query.title(),
                        'city': city,
                        'scraped_at': datetime.now().isoformat(),
                        'session_id': self.session_id,
                    })
                    results.append(business_data)
                    self.logger.info(f"Données extraites pour : {business_data.get('name')}")
            
        except Exception as e:
            self.logger.error(f"Une erreur critique est survenue pendant la recherche : {e}")
            self.debug_and_save_page()
        finally:
            if self.driver:
                self.driver.quit()
                self.logger.info("Driver fermé.")
        
        return results

    def debug_and_save_page(self):
        """Sauvegarde le HTML de la page pour une analyse manuelle en cas d'échec."""
        if not self.driver:
            return
        
        filename = f"debug_page_source_{self.session_id}.html"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(self.driver.page_source)
        self.logger.error(f"Échec de l'extraction. Le code source de la page a été sauvegardé dans : {filename}")


def main():
    parser = argparse.ArgumentParser(description='Pages Jaunes Scraper v5.0 - Robuste 2025')
    parser.add_argument('query', help='Profession à rechercher (ex: "plombier")')
    parser.add_argument('--city', required=True, help='Code postal ou ville (ex: "44000")')
    parser.add_argument('--limit', type=int, default=10, help='Nombre de résultats à extraire')
    parser.add_argument('--session-id', help='ID de session pour le suivi')
    parser.add_argument('--debug', action='store_true', help='Activer les logs de débogage')
    parser.add_argument('--headless', action='store_true', help='(NON RECOMMANDÉ) Activer le mode headless')
    
    args = parser.parse_args()
    
    scraper = SeleniumPJScraperV5(
        session_id=args.session_id,
        debug=args.debug,
        headless=args.headless
    )
    
    results = scraper.search(
        query=args.query,
        city=args.city,
        limit=args.limit
    )
    
    if results:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        scraper.logger.info(f"✓ Succès ! {len(results)} résultats extraits et affichés en JSON.")
    else:
        scraper.logger.warning("❌ La recherche n'a retourné aucun résultat. Vérifiez les logs et le fichier HTML de débogage.")
        sys.exit(1)

if __name__ == "__main__":
    main()
