#!/usr/bin/env python3
"""
Google Maps Scraper v1.5 CORRIGÉ - Solution Immédiate pour Naosite
Basé sur IMPLEMENTATION_GUIDE.md avec corrections critiques
"""

import os
import sys
import json
import time
import random
import argparse
from datetime import datetime
from playwright.sync_api import sync_playwright

# Configuration proxy Webshare
PROXY_HOST = os.getenv("WEBSHARE_HOST", "proxy.webshare.io")
PROXY_PORT = os.getenv("WEBSHARE_PORT", "8000")
PROXY_USER = os.getenv("WEBSHARE_USERNAME")
PROXY_PASS = os.getenv("WEBSHARE_PASSWORD")

def normalize_data(raw_data):
    """Normalise les données selon le schéma unifié"""
    # Normalisation téléphone
    phone = (raw_data.get('phone', '') or '').strip()
    phone = ''.join(filter(str.isdigit, phone))
    if phone.startswith('33'): phone = '+' + phone
    elif phone.startswith('0'): phone = '+33' + phone[1:]
    elif len(phone) == 9: phone = '+33' + phone
    
    # Extraction ville avec patterns améliorés
    address = raw_data.get('address', '') or ''
    city_match = None
    
    # Patterns multiples pour extraction ville
    import re
    patterns = [
        r'(\d{5})\s+([A-Z][a-z\s\-\']+)',  # 44000 Nantes
        r'([A-Z][a-z\s\-\']+)\s+\((\d{5})\)',  # Nantes (44000)
        r'([A-Z][a-z\s\-\']+),?\s+\d{5}',  # Nantes, 44000
        r',\s*([A-Z][a-z\s\-\']+)$'  # ..., Nantes
    ]
    
    for pattern in patterns:
        match = re.search(pattern, address)
        if match:
            # Prendre le groupe qui contient la ville (pas le code postal)
            groups = match.groups()
            for group in groups:
                if group and not group.isdigit() and len(group) > 2:
                    city_match = group.strip()
                    break
            if city_match:
                break
    
    return {
        "name": (raw_data.get('name', '') or '').strip(),
        "activity": normalize_activity(raw_data.get('activity', '')),
        "phone": phone if len(phone) > 8 else None,
        "email": None,  # Google Maps rarely has emails
        "address": address,
        "city": city_match or extract_city_fallback(address),
        "website": None,  # Always null (filtering criteria)
        "source": "google_maps",
        "scraped_at": datetime.utcnow().isoformat() + "Z",
        "raw_data": raw_data  # Pour debug
    }

def normalize_activity(activity):
    """Standardise les activités"""
    activity = (activity or '').lower()
    if any(word in activity for word in ['plomb', 'sanitaire', 'plomberie']): return 'Plombier'
    if any(word in activity for word in ['électr', 'electric', 'électricité']): return 'Électricien'
    if any(word in activity for word in ['chauff', 'climat', 'chauffage']): return 'Chauffagiste'
    if any(word in activity for word in ['maçon', 'macon', 'bâti', 'maçonnerie']): return 'Maçon'
    if any(word in activity for word in ['couv', 'toiture']): return 'Couvreur'
    if any(word in activity for word in ['menuis', 'bois']): return 'Menuisier'
    if any(word in activity for word in ['peintre', 'peinture']): return 'Peintre'
    return activity.title()

def extract_city_fallback(address):
    """Extraction ville fallback si patterns principaux échouent"""
    if not address:
        return ""
    
    # Diviser par virgules et prendre le segment le plus probable
    segments = address.split(',')
    for segment in segments:
        segment = segment.strip()
        if len(segment) > 2 and not segment.isdigit():
            # Éviter les segments qui sont clairement des rues
            if not any(word in segment.lower() for word in ['rue', 'avenue', 'boulevard', 'place', 'chemin']):
                return segment
    
    # Dernier recours : prendre les mots qui ressemblent à une ville
    import re
    city_words = re.findall(r'\b[A-Z][a-z]{2,}\b', address)
    if city_words:
        return city_words[-1]  # Dernier mot capitalisé
    
    return ""

def scrape_maps(query, city="", limit=50, offset=0):
    """
    Scraper Google Maps avec corrections critiques v1.5
    - Pagination corrigée (incréments de 20 au lieu de 5)
    - Sélecteurs CSS mis à jour pour 2025
    - Anti-détection amélioré
    """
    results = []
    
    with sync_playwright() as p:
        # Configuration navigateur avec proxy
        browser_args = [
            '--no-sandbox', 
            '--disable-dev-shm-usage',
            '--disable-blink-features=AutomationControlled',
            '--disable-extensions',
            '--no-first-run',
            '--disable-default-apps'
        ]
        
        if PROXY_USER and PROXY_PASS:
            proxy_config = {
                "server": f"http://{PROXY_HOST}:{PROXY_PORT}",
                "username": PROXY_USER,
                "password": PROXY_PASS
            }
            browser = p.chromium.launch(headless=True, args=browser_args, proxy=proxy_config)
        else:
            browser = p.chromium.launch(headless=True, args=browser_args)
        
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            extra_http_headers={
                'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
            }
        )
        
        # Masquer les traces d'automation
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            window.chrome = {
                runtime: {},
            };
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
        """)
        
        page = context.new_page()
        
        try:
            # Construction URL avec pagination CORRIGÉE
            search_query = f"{query} {city}".strip()
            
            # CORRECTION CRITIQUE : pagination par 20 (au lieu de 5)
            # Selon la recherche technique, Google Maps pagine par blocs de 20
            corrected_offset = (offset // 20) * 20  # Aligner sur multiples de 20
            
            maps_url = f"https://www.google.com/maps/search/{search_query}"
            if corrected_offset > 0:
                maps_url += f"/@46.603354,1.8883335,6z/data=!3m1!4b1!4m2!2m1!6e5?start={corrected_offset}"
            
            print(f"🔍 Searching Maps: {maps_url}", file=sys.stderr)
            
            page.goto(maps_url, wait_until='networkidle', timeout=30000)
            time.sleep(random.uniform(3, 5))
            
            # Attendre que la carte se charge
            page.wait_for_selector('div[role="main"]', timeout=10000)
            
            # SÉLECTEURS CSS MIS À JOUR (version 2025)
            business_selectors = [
                'div[data-result-index]',  # Sélecteur principal
                'div[role="article"]',     # Alternative 2025
                '.Nv2PK',                  # Cards business
                'a[data-result-index]',    # Liens business
                '.VkpGBb',                 # Ancien format
                '[jsaction*="mouseover"]'  # Hover elements
            ]
            
            businesses_found = []
            
            for selector in business_selectors:
                try:
                    businesses = page.query_selector_all(selector)
                    if businesses and len(businesses) > 0:
                        businesses_found = businesses
                        print(f"✅ Found {len(businesses)} businesses with selector: {selector}", file=sys.stderr)
                        break
                except Exception as e:
                    continue
            
            if not businesses_found:
                # Fallback: scroll et recherche dynamique
                print("🔄 No static elements found, trying dynamic scroll...", file=sys.stderr)
                
                for i in range(5):  # Max 5 scrolls
                    page.evaluate("window.scrollBy(0, 800)")
                    time.sleep(random.uniform(1, 2))
                    
                    # Recherche de nouveaux éléments après scroll
                    for selector in business_selectors:
                        businesses = page.query_selector_all(selector)
                        if businesses:
                            businesses_found.extend(businesses)
                
                # Déduplication
                businesses_found = list(dict.fromkeys(businesses_found))
            
            # Extraction des données business
            for i, business in enumerate(businesses_found[:limit]):
                try:
                    # Vérifier que l'élément est visible
                    if not business.is_visible():
                        continue
                    
                    # EXTRACTION AMÉLIORÉE
                    name = None
                    name_selectors = ['h3', '.fontHeadlineSmall', '.qBF1Pd', '.fontDisplayLarge']
                    for selector in name_selectors:
                        name_elem = business.query_selector(selector)
                        if name_elem:
                            name = name_elem.inner_text().strip()
                            if name:
                                break
                    
                    if not name:
                        continue
                    
                    # Vérifier absence site web (critère de filtrage)
                    website_button = business.query_selector('[aria-label*="Site"], [aria-label*="Website"], a[href^="http"]:not([href*="google"])')
                    if website_button:
                        print(f"❌ Skipping {name} - has website", file=sys.stderr)
                        continue
                    
                    # Téléphone
                    phone = ""
                    phone_selectors = [
                        '[aria-label*="Téléphone"]', '[aria-label*="Phone"]',
                        'a[href^="tel:"]', '.fontBodyMedium'
                    ]
                    for selector in phone_selectors:
                        phone_elem = business.query_selector(selector)
                        if phone_elem:
                            phone_text = phone_elem.get_attribute('aria-label') or phone_elem.inner_text()
                            if phone_text and ('0' in phone_text or '+' in phone_text):
                                phone = phone_text
                                break
                    
                    # Adresse
                    address = ""
                    address_selectors = [
                        '.W4Efsd:nth-of-type(2)', '.fontBodyMedium', '[title]'
                    ]
                    for selector in address_selectors:
                        addr_elem = business.query_selector(selector)
                        if addr_elem:
                            addr_text = addr_elem.get_attribute('title') or addr_elem.inner_text()
                            if addr_text and len(addr_text) > 10:
                                address = addr_text
                                break
                    
                    if name:  # Au minimum un nom
                        raw_data = {
                            'name': name,
                            'activity': query,
                            'phone': phone,
                            'address': address
                        }
                        
                        normalized = normalize_data(raw_data)
                        results.append(normalized)
                        
                        print(f"✅ Extracted: {name}", file=sys.stderr)
                        
                        if len(results) >= limit:
                            break
                            
                except Exception as e:
                    print(f"❌ Error extracting business {i}: {e}", file=sys.stderr)
                    continue
                    
        except Exception as e:
            print(f"❌ Maps scraping error: {e}", file=sys.stderr)
        finally:
            browser.close()
    
    return results

# Script PJ corrigé également
def scrape_pj(query, city="", limit=15):
    """Pages Jaunes scraper corrigé v1.5"""
    results = []
    
    with sync_playwright() as p:
        # Configuration identique à Maps
        browser_args = ['--no-sandbox', '--disable-dev-shm-usage']
        if PROXY_USER and PROXY_PASS:
            proxy_config = {
                "server": f"http://{PROXY_HOST}:{PROXY_PORT}",
                "username": PROXY_USER,
                "password": PROXY_PASS
            }
            browser = p.chromium.launch(headless=True, args=browser_args, proxy=proxy_config)
        else:
            browser = p.chromium.launch(headless=True, args=browser_args)
        
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        
        page = context.new_page()
        
        try:
            # URL PJ corrigée
            search_query = f"{query} {city}".strip()
            pj_url = f"https://www.pagesjaunes.fr/annuaire/chercherlesprofessionnels?quoi={query}&ou={city}"
            
            page.goto(pj_url, wait_until='networkidle')
            time.sleep(random.uniform(3, 5))
            
            # Sélecteurs PJ mis à jour
            business_selectors = [
                '.bi',
                '.bi-bloc',
                '.search-result',
                '.listing-item',
                'article[data-pj-listing]'
            ]
            
            businesses_found = []
            for selector in business_selectors:
                businesses = page.query_selector_all(selector)
                if businesses:
                    businesses_found = businesses
                    print(f"✅ Found {len(businesses)} PJ businesses with: {selector}", file=sys.stderr)
                    break
            
            for business in businesses_found[:limit]:
                try:
                    # Nom
                    name_elem = business.query_selector('.bi-denomination, .denomination-links, h3.denomination')
                    name = name_elem.inner_text().strip() if name_elem else ""
                    
                    if not name:
                        continue
                    
                    # Email (spécificité PJ)
                    email = ""
                    email_elem = business.query_selector('a[href^="mailto:"]')
                    if email_elem:
                        email = email_elem.get_attribute('href').replace('mailto:', '')
                    
                    # Téléphone
                    phone = ""
                    phone_elem = business.query_selector('.bi-numero, a[href^="tel:"]')
                    if phone_elem:
                        phone = phone_elem.get_attribute('href') or phone_elem.inner_text()
                        if phone.startswith('tel:'):
                            phone = phone[4:]
                    
                    # Adresse
                    address = ""
                    addr_elem = business.query_selector('.bi-adresse')
                    if addr_elem:
                        address = addr_elem.inner_text()
                    
                    if name and (phone or email):
                        raw_data = {
                            'name': name,
                            'activity': query,
                            'phone': phone,
                            'email': email,
                            'address': address
                        }
                        
                        normalized = normalize_data(raw_data)
                        normalized['email'] = email  # Préserver email PJ
                        normalized['source'] = 'pages_jaunes'
                        results.append(normalized)
                        
                        print(f"✅ PJ Extracted: {name}" + (f" (email: {email})" if email else ""), file=sys.stderr)
                        
                except Exception as e:
                    print(f"❌ PJ extraction error: {e}", file=sys.stderr)
                    continue
                    
        except Exception as e:
            print(f"❌ PJ scraping error: {e}", file=sys.stderr)
        finally:
            browser.close()
    
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("query", help="Activité à rechercher")
    parser.add_argument("--city", default="", help="Ville")
    parser.add_argument("--limit", type=int, default=50, help="Limite résultats")
    parser.add_argument("--offset", type=int, default=0, help="Offset pour pagination")
    parser.add_argument("--debug", action="store_true", help="Mode debug")
    parser.add_argument("--source", choices=['maps', 'pj'], default='maps', help="Source à scraper")
    
    args = parser.parse_args()
    
    if args.source == 'maps':
        results = scrape_maps(args.query, args.city, args.limit, args.offset)
    else:
        results = scrape_pj(args.query, args.city, args.limit)
    
    if args.debug:
        print(f"✅ {args.source.upper()} Scraper: {len(results)} résultats pour '{args.query}'", file=sys.stderr)
    
    # Output JSON lines pour n8n
    for result in results:
        print(json.dumps(result, ensure_ascii=False))
