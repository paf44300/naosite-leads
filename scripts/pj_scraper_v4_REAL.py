#!/usr/bin/env python3
"""
VRAI Pages Jaunes Scraper v4.0 - EXTRACTION RÉELLE uniquement
Finies les données fictives ! Extraction des vraies entreprises PJ seulement.
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

class RealPJScraperV4:
    def __init__(self, session_id: str = None, debug: bool = False):
        self.session_id = session_id or f"real_pj_{int(time.time())}"
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
        self.base_url = "https://www.pagesjaunes.fr"
        
        # Patterns email améliorés
        self.email_patterns = [
            r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b',
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
    
    def extract_email_from_text(self, text: str) -> Optional[str]:
        """Extrait l'email d'un texte avec validation"""
        if not text:
            return None
            
        for pattern in self.email_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                email = match.strip().lower() if isinstance(match, str) else match
                # Validation email basique
                if '@' in email and '.' in email and len(email) > 5 and len(email) < 100:
                    # Éviter les emails génériques/spam
                    spam_patterns = ['noreply', 'no-reply', 'contact@pagesjaunes', 'admin@']
                    if not any(spam in email for spam in spam_patterns):
                        return email
        return None
    
    def extract_real_business_data(self, html_content: str, query: str, page: int = 1) -> List[Dict]:
        """
        EXTRACTION RÉELLE des données business depuis le HTML de Pages Jaunes
        """
        results = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Sélecteurs PJ 2024-2025 (multiples versions)
            business_selectors = [
                '.bi',  # Ancien format
                '.bi-bloc',  # Nouveau format  
                '.search-result',  # Alternative
                '.listing-item',  # Autre alternative
                'article[data-pj-listing]',  # Format 2025
                '.pj-lb'  # Dernier format connu
            ]
            
            business_elements = []
            for selector in business_selectors:
                elements = soup.select(selector)
                if elements:
                    business_elements = elements
                    self.logger.debug(f"Found {len(elements)} businesses with: {selector}")
                    break
            
            if not business_elements:
                self.logger.warning("No business elements found in PJ HTML")
                # Essayer d'analyser la structure HTML pour debug
                if self.debug:
                    self.logger.debug(f"HTML sample: {html_content[:500]}...")
                return []
            
            for i, element in enumerate(business_elements[:20]):  # Max 20 par page
                try:
                    business_data = self.extract_single_business_pj(element, query, page)
                    if business_data:
                        results.append(business_data)
                        
                except Exception as e:
                    self.logger.error(f"Error extracting PJ business {i}: {e}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"PJ HTML parsing failed: {e}")
            
        return results
    
    def extract_single_business_pj(self, element, query: str, page: int) -> Optional[Dict]:
        """
        Extrait UNE entreprise réelle depuis un élément HTML PagesJaunes
        """
        data = {
            'name': None,
            'address': None,
            'phone': None,
            'email': None,
            'website': None,
            'activity': None
        }
        
        try:
            # EXTRACTION NOM - Sélecteurs PJ spécifiques
            name_selectors = [
                '.bi-denomination', '.denomination-links', 'h3.denomination',
                '.company-name', '.business-name', 'a.denomination',
                '.pj-lb-title', '.search-result-title', 'h2 a', 'h3 a'
            ]
            
            for selector in name_selectors:
                name_elem = element.select_one(selector)
                if name_elem and name_elem.get_text(strip=True):
                    name_text = name_elem.get_text(strip=True)
                    # Nettoyer les caractères parasites PJ
                    name_clean = re.sub(r'^[^\w]+|[^\w]+$', '', name_text)
                    if len(name_clean) > 2:
                        data['name'] = name_clean[:150]
                        break
            
            # EXTRACTION ADRESSE RÉELLE PJ
            address_selectors = [
                '.bi-adresse', '.adresse', '.address-container', '.pj-lb-address',
                '.search-result-address', '.listing-address', '.bi-adresse-container'
            ]
            
            for selector in address_selectors:
                addr_elem = element.select_one(selector)
                if addr_elem and addr_elem.get_text(strip=True):
                    address_text = addr_elem.get_text(strip=True)
                    # Nettoyer l'adresse PJ (souvent avec retours à la ligne)
                    address_clean = ' '.join(address_text.split())
                    if len(address_clean) > 5 and re.search(r'\d', address_clean):
                        data['address'] = address_clean[:200]
                        break
            
            # EXTRACTION TÉLÉPHONE RÉEL PJ
            phone_selectors = [
                '.bi-numero', '.coord-numero', 'a[href^="tel:"]', '.phone-number',
                '.pj-lb-phone', '.search-result-phone', '.listing-phone'
            ]
            
            for selector in phone_selectors:
                phone_elem = element.select_one(selector)
                if phone_elem:
                    phone_text = phone_elem.get('href') or phone_elem.get_text()
                    if phone_text:
                        if phone_text.startswith('tel:'):
                            phone_text = phone_text[4:]
                        # Nettoyer et valider téléphone français
                        phone_clean = re.sub(r'[^\d+\s\.\-\(\)]', '', phone_text)
                        # Vérifier format français
                        if re.search(r'0[1-9][\d\s\.\-]{8,}', phone_clean) or '+33' in phone_clean:
                            data['phone'] = phone_clean.strip()
                            break
            
            # EXTRACTION EMAIL RÉEL PJ (focus principal)
            try:
                # 1. Recherche liens mailto directs
                mailto_links = element.select('a[href^="mailto:"]')
                for link in mailto_links:
                    href = link.get('href')
                    email = self.extract_email_from_text(href)
                    if email:
                        data['email'] = email
                        break
                
                # 2. Recherche dans le texte complet de l'élément
                if not data['email']:
                    full_text = element.get_text()
                    email = self.extract_email_from_text(full_text)
                    if email:
                        data['email'] = email
                
                # 3. Recherche dans les attributs data-* ou autres
                if not data['email']:
                    for attr in element.attrs:
                        if isinstance(element.attrs[attr], str):
                            email = self.extract_email_from_text(element.attrs[attr])
                            if email:
                                data['email'] = email
                                break
                                
            except Exception as e:
                self.logger.debug(f"Email extraction error for PJ element: {e}")
            
            # EXTRACTION WEBSITE RÉEL PJ
            try:
                # Recherche liens externes (pas PJ)
                website_selectors = [
                    'a[href*="http"]:not([href*="pagesjaunes"]):not([href*="solocal"])',
                    '.bi-website a', '.website-link'
                ]
                
                for selector in website_selectors:
                    website_elem = element.select_one(selector)
                    if website_elem:
                        href = website_elem.get('href')
                        if href and 'http' in href and len(href) > 10:
                            # Vérifier que ce n'est pas un lien PJ interne
                            if not any(domain in href for domain in ['pagesjaunes.fr', 'solocal.com', 'google.com']):
                                data['website'] = href[:200]
                                break
                                
            except Exception as e:
                self.logger.debug(f"Website extraction error: {e}")
            
            # EXTRACTION ACTIVITÉ/RUBRIQUE PJ
            activity_selectors = [
                '.bi-rubrique', '.category', '.activity', '.pj-lb-category',
                '.search-result-category', '.listing-category'
            ]
            
            for selector in activity_selectors:
                activity_elem = element.select_one(selector)
                if activity_elem and activity_elem.get_text(strip=True):
                    data['activity'] = activity_elem.get_text(strip=True)[:100]
                    break
            
            # VALIDATION FINALE
            if not data['name'] or len(data['name']) < 3:
                if self.debug:
                    self.logger.warning(f"❌ NO NAME extracted from PJ element")
                return None
                
            # VALIDATION DÉPARTEMENT STRICTE
            if data['address']:
                dept = self.validate_department(data['address'])
                if not dept:
                    if self.debug:
                        self.logger.warning(f"❌ REJECTED PJ - Invalid dept: {data['name']} - {data['address']}")
                    return None
                data['department'] = dept
                data['geo_validated'] = True
            else:
                # PJ peut avoir des entreprises sans adresse complète
                if self.debug:
                    self.logger.warning(f"⚠️ NO ADDRESS: {data['name']}")
                return None
            
            # Compléter les métadonnées
            data.update({
                'activity': data['activity'] or query.title(),
                'source': 'pages_jaunes_real_v4',
                'scraped_at': datetime.now().isoformat(),
                'session_id': self.session_id,
                'page': page,
                'has_email': bool(data['email']),
                'extracted_from': 'real_pj_html'
            })
            
            if data['email']:
                self.logger.info(f"✅ EMAIL FOUND: {data['name']} -> {data['email']}")
            
            if self.debug:
                self.logger.info(f"✅ EXTRACTED PJ: {data['name']} - {data['address'][:50]}...")
                
            return data
            
        except Exception as e:
            self.logger.error(f"Single PJ business extraction failed: {e}")
            return None
    
    def search_pages_jaunes(self, query: str, city: str, limit: int = 15, max_pages: int = 2) -> List[Dict]:
        """
        Recherche RÉELLE sur Pages Jaunes avec HTTP requests (2 pages max)
        """
        self.logger.info(f"REAL Pages Jaunes search: {query} in {city} (limit: {limit}, max_pages: {max_pages})")
        
        all_results = []
        
        try:
            # Headers réalistes pour PJ
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
                'Cache-Control': 'max-age=0',
                'Referer': 'https://www.pagesjaunes.fr/'
            }
            
            self.session.headers.update(headers)
            
            # Recherche sur plusieurs pages (max 2)
            for page in range(1, min(max_pages + 1, 3)):  # Force max 2 pages
                try:
                    self.logger.info(f"Fetching PJ page {page}...")
                    
                    # URL PJ avec pagination
                    search_params = {
                        'quoi': query,
                        'ou': city,
                        'page': page
                    }
                    
                    search_url = f"{self.base_url}/annuaire/chercherlesprofessionnels?" + urlencode(search_params)
                    
                    self.logger.debug(f"PJ URL: {search_url}")
                    
                    # Délai réaliste entre pages
                    if page > 1:
                        time.sleep(random.uniform(3, 6))
                    else:
                        time.sleep(random.uniform(2, 4))
                    
                    response = self.session.get(search_url, timeout=20)
                    
                    if response.status_code == 200:
                        self.logger.info(f"✅ Got PJ HTML page {page} ({len(response.text)} chars)")
                        
                        # EXTRACTION RÉELLE depuis le HTML
                        page_businesses = self.extract_real_business_data(response.text, query, page)
                        
                        if page_businesses:
                            all_results.extend(page_businesses)
                            self.logger.info(f"✅ Page {page}: {len(page_businesses)} real businesses extracted")
                            
                            # Arrêter si on a assez de résultats
                            if len(all_results) >= limit:
                                break
                        else:
                            self.logger.warning(f"Page {page}: No businesses extracted")
                            if page == 1:
                                # Si première page vide, essayer format alternatif
                                alt_url = f"{self.base_url}/pagesblanches/recherche?quoi={quote_plus(query)}&ou={quote_plus(city)}"
                                alt_response = self.session.get(alt_url, timeout=20)
                                if alt_response.status_code == 200:
                                    alt_businesses = self.extract_real_business_data(alt_response.text, query, page)
                                    if alt_businesses:
                                        all_results.extend(alt_businesses)
                                        self.logger.info(f"✅ Alt format: {len(alt_businesses)} businesses")
                            
                    elif response.status_code == 429:
                        self.logger.warning(f"Rate limited on page {page}, waiting...")
                        time.sleep(random.uniform(10, 20))
                        continue
                        
                    else:
                        self.logger.warning(f"HTTP {response.status_code} on PJ page {page}")
                        
                except requests.exceptions.RequestException as e:
                    self.logger.error(f"Request failed on PJ page {page}: {e}")
                    continue
            
            # Appliquer limite finale
            final_results = all_results[:limit]
            
            self.logger.info(f"🎯 FINAL PJ: {len(final_results)} businesses from {max_pages} pages")
            
            return final_results
            
        except Exception as e:
            self.logger.error(f"Pages Jaunes search failed: {e}")
            return []

def main():
    parser = argparse.ArgumentParser(description='REAL Pages Jaunes Scraper v4.0 - Vraies données uniquement')
    parser.add_argument('query', help='Search query (e.g., "plombier")')
    parser.add_argument('--city', required=True, help='Code postal to search in (e.g., "44000")')
    parser.add_argument('--limit', type=int, default=14, help='Number of results to return')
    parser.add_argument('--session-id', help='Session ID for tracking')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--max-pages', type=int, default=2, help='Maximum pages to search (DEFAULT: 2)')
    
    args = parser.parse_args()
    
    try:
        scraper = RealPJScraperV4(
            session_id=args.session_id,
            debug=args.debug
        )
        
        results = scraper.search_pages_jaunes(
            query=args.query,
            city=args.city,
            limit=args.limit,
            max_pages=args.max_pages
        )
        
        # Output JSON pour n8n (un objet par ligne)
        for result in results:
            print(json.dumps(result, ensure_ascii=False))
            
        if args.debug:
            email_count = sum(1 for r in results if r.get('email'))
            valid_count = sum(1 for r in results if r.get('geo_validated'))
            logging.info(f"SUCCESS: {len(results)} real PJ results ({email_count} emails, {valid_count} geo-validated)")
            
    except Exception as e:
        logging.error(f"Real PJ scraper failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
