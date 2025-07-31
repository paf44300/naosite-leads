#!/usr/bin/env python3
"""
VRAI Google Maps Scraper v4.0 - EXTRACTION RÉELLE uniquement
Finies les données fictives ! Extraction des vraies entreprises seulement.
"""

import json
import time
import argparse
import sys
import logging
import re
from typing import List, Dict, Optional
import requests
from urllib.parse import quote_plus, urlencode
import random
from datetime import datetime
from bs4 import BeautifulSoup

class RealMapsScraperV4:
    def __init__(self, session_id: str = None, debug: bool = False):
        self.session_id = session_id or f"real_maps_{int(time.time())}"
        self.debug = debug
        self.setup_logging()
        
        # VALIDATION STRICTE - Départements autorisés
        self.VALID_DEPARTMENTS = ['44', '35', '29', '56', '85', '49', '53']
        
        # User agents réalistes
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]
        
        self.session = requests.Session()
        
    def setup_logging(self):
        level = logging.DEBUG if self.debug else logging.WARNING
        logging.basicConfig(
            level=level,
            format=f'[{self.session_id}] %(levelname)s: %(message)s',
            stream=sys.stderr
        )
        self.logger = logging.getLogger(__name__)
        
    def validate_department(self, address: str) -> Optional[str]:
        """
        VALIDATION STRICTE - Extrait et valide le code postal
        Retourne le département si valide, None sinon
        """
        if not address:
            return None
            
        # Recherche TOUS les codes postaux dans l'adresse
        postal_patterns = [
            r'\b(\d{5})\b',  # 44000
            r'(\d{2})\s*\d{3}',  # 44 000 ou 44000
            r'F-(\d{5})'  # F-44000
        ]
        
        for pattern in postal_patterns:
            matches = re.findall(pattern, address)
            for match in matches:
                postal_code = match if len(match) == 5 else match + '000'
                dept = postal_code[:2]
                
                if dept in self.VALID_DEPARTMENTS:
                    if self.debug:
                        self.logger.info(f"✅ VALID DEPT: {postal_code} -> {dept}")
                    return dept
                    
        if self.debug:
            self.logger.warning(f"❌ NO VALID DEPT in: {address}")
        return None
    
    def extract_real_business_data(self, html_content: str, query: str) -> List[Dict]:
        """
        EXTRACTION RÉELLE des données business depuis le HTML de Google Maps
        """
        results = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Patterns de sélecteurs Google Maps (version 2024-2025)
            business_selectors = [
                'div[data-result-index]',  # Nouveau format
                '.VkpGBb',  # Cards business
                '.Z8fK3b',  # Résultats liste
                'div[jsaction*="mouseover"]'  # Hover actions
            ]
            
            business_elements = []
            for selector in business_selectors:
                elements = soup.select(selector)
                if elements:
                    business_elements = elements
                    self.logger.debug(f"Found {len(elements)} businesses with: {selector}")
                    break
            
            if not business_elements:
                self.logger.warning("No business elements found in HTML")
                return []
            
            for i, element in enumerate(business_elements[:30]):  # Max 30 pour éviter spam
                try:
                    business_data = self.extract_single_business(element, query)
                    if business_data:
                        results.append(business_data)
                        
                except Exception as e:
                    self.logger.error(f"Error extracting business {i}: {e}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"HTML parsing failed: {e}")
            
        return results
    
    def extract_single_business(self, element, query: str) -> Optional[Dict]:
        """
        Extrait UNE entreprise réelle depuis un élément HTML
        """
        data = {
            'name': None,
            'address': None,
            'phone': None,
            'website': None,
            'rating': None,
            'reviews_count': None
        }
        
        try:
            # EXTRACTION NOM - Multiples sélecteurs
            name_selectors = [
                'h3', '.fontHeadlineSmall', '.qBF1Pd', '.fontDisplayLarge',
                '[data-value="name"]', '.section-result-title'
            ]
            
            for selector in name_selectors:
                name_elem = element.select_one(selector)
                if name_elem and name_elem.get_text(strip=True):
                    data['name'] = name_elem.get_text(strip=True)[:150]
                    break
            
            # EXTRACTION ADRESSE RÉELLE
            address_selectors = [
                '.W4Efsd:nth-of-type(1)', '.Z8fK3b span', '.section-result-location',
                '[data-value="address"]', '.fontBodyMedium'
            ]
            
            for selector in address_selectors:
                addr_elem = element.select_one(selector)
                if addr_elem and addr_elem.get_text(strip=True):
                    address_text = addr_elem.get_text(strip=True)
                    # Vérifier que c'est bien une adresse (contient chiffres)
                    if re.search(r'\d', address_text):
                        data['address'] = address_text[:200]
                        break
            
            # EXTRACTION TÉLÉPHONE RÉEL
            phone_selectors = [
                'a[href^="tel:"]', '.fontBodyMedium', '[data-value="phone_number"]'
            ]
            
            for selector in phone_selectors:
                phone_elem = element.select_one(selector)
                if phone_elem:
                    phone_text = phone_elem.get('href') or phone_elem.get_text()
                    if phone_text:
                        if phone_text.startswith('tel:'):
                            phone_text = phone_text[4:]
                        # Nettoyer et valider le téléphone français
                        phone_clean = re.sub(r'[^\d+]', '', phone_text)
                        if len(phone_clean) >= 10 and (phone_clean.startswith('0') or phone_clean.startswith('+33')):
                            data['phone'] = phone_text.strip()
                            break
            
            # EXTRACTION WEBSITE RÉEL
            website_links = element.select('a[href^="http"]:not([href*="google.com"]):not([href*="maps.google"])')
            for link in website_links:
                href = link.get('href')
                if href and len(href) > 10:
                    data['website'] = href[:200]
                    break
            
            # EXTRACTION RATING & REVIEWS
            rating_elem = element.select_one('.MW4etd, .fontBodyMedium')
            if rating_elem:
                rating_text = rating_elem.get_text()
                rating_match = re.search(r'(\d,\d|\d\.\d)', rating_text)
                if rating_match:
                    data['rating'] = float(rating_match.group(1).replace(',', '.'))
                    
                reviews_match = re.search(r'\((\d+)\)', rating_text)
                if reviews_match:
                    data['reviews_count'] = int(reviews_match.group(1))
            
            # VALIDATION FINALE
            if not data['name'] or len(data['name']) < 3:
                return None
                
            # VALIDATION DÉPARTEMENT si adresse disponible
            if data['address']:
                dept = self.validate_department(data['address'])
                if not dept:
                    if self.debug:
                        self.logger.warning(f"❌ REJECTED - Invalid dept: {data['name']} - {data['address']}")
                    return None
                data['department'] = dept
                data['geo_validated'] = True
            else:
                # Pas d'adresse = pas de validation possible
                if self.debug:
                    self.logger.warning(f"⚠️ NO ADDRESS: {data['name']}")
                return None
            
            # Compléter les métadonnées
            data.update({
                'activity': query.title(),
                'source': 'google_maps_real_v4',
                'scraped_at': datetime.now().isoformat(),
                'session_id': self.session_id,
                'extracted_from': 'real_html'
            })
            
            if self.debug:
                self.logger.info(f"✅ EXTRACTED: {data['name']} - {data['address']}")
                
            return data
            
        except Exception as e:
            self.logger.error(f"Single business extraction failed: {e}")
            return None
    
    def search_google_maps(self, query: str, city: str, limit: int = 20, offset: int = 0) -> List[Dict]:
        """
        Recherche RÉELLE sur Google Maps avec HTTP requests
        """
        self.logger.info(f"REAL Google Maps search: {query} in {city} (limit: {limit}, offset: {offset})")
        
        try:
            # Headers réalistes
            headers = {
                'User-Agent': random.choice(self.user_agents),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Cache-Control': 'max-age=0'
            }
            
            self.session.headers.update(headers)
            
            # Construction de l'URL de recherche RÉELLE
            search_query = f"{query} {city}".strip()
            encoded_query = quote_plus(search_query)
            
            # Différentes approches d'URL Google Maps
            search_urls = [
                f"https://www.google.com/maps/search/{encoded_query}",
                f"https://maps.google.com/maps?q={encoded_query}",
                f"https://www.google.fr/maps/search/{encoded_query}"
            ]
            
            results = []
            
            for attempt, url in enumerate(search_urls):
                try:
                    self.logger.debug(f"Trying URL {attempt + 1}: {url}")
                    
                    # Délai réaliste
                    time.sleep(random.uniform(2, 4))
                    
                    response = self.session.get(url, timeout=15)
                    
                    if response.status_code == 200:
                        self.logger.info(f"✅ Got HTML response ({len(response.text)} chars)")
                        
                        # EXTRACTION RÉELLE depuis le HTML
                        businesses = self.extract_real_business_data(response.text, query)
                        
                        if businesses:
                            results.extend(businesses)
                            self.logger.info(f"✅ Extracted {len(businesses)} real businesses")
                            break
                        else:
                            self.logger.warning("No businesses extracted from HTML")
                            
                    elif response.status_code == 429:
                        self.logger.warning("Rate limited, waiting...")
                        time.sleep(random.uniform(10, 20))
                        continue
                        
                    else:
                        self.logger.warning(f"HTTP {response.status_code} on attempt {attempt + 1}")
                        
                except requests.exceptions.RequestException as e:
                    self.logger.error(f"Request failed on attempt {attempt + 1}: {e}")
                    if attempt < len(search_urls) - 1:
                        time.sleep(random.uniform(5, 10))
                        continue
                    else:
                        self.logger.error("All request attempts failed")
                        break
            
            # Appliquer limit et offset
            start_idx = offset
            end_idx = offset + limit
            final_results = results[start_idx:end_idx]
            
            self.logger.info(f"🎯 FINAL: {len(final_results)} businesses (offset: {offset}, limit: {limit})")
            
            return final_results
            
        except Exception as e:
            self.logger.error(f"Google Maps search failed: {e}")
            return []

def main():
    parser = argparse.ArgumentParser(description='REAL Google Maps Scraper v4.0 - Vraies données uniquement')
    parser.add_argument('query', help='Search query (e.g., "plombier")')
    parser.add_argument('--city', required=True, help='Code postal to search in (e.g., "44000")')
    parser.add_argument('--limit', type=int, default=20, help='Number of results to return')
    parser.add_argument('--offset', type=int, default=0, help='Offset for pagination')
    parser.add_argument('--session-id', help='Session ID for tracking')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    try:
        scraper = RealMapsScraperV4(
            session_id=args.session_id,
            debug=args.debug
        )
        
        results = scraper.search_google_maps(
            query=args.query,
            city=args.city,
            limit=args.limit,
            offset=args.offset
        )
        
        # Output JSON pour n8n (un objet par ligne)
        for result in results:
            print(json.dumps(result, ensure_ascii=False))
            
        if args.debug:
            valid_count = len([r for r in results if r.get('geo_validated')])
            logging.info(f"SUCCESS: {len(results)} real results ({valid_count} geo-validated)")
            
    except Exception as e:
        logging.error(f"Real scraper failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
