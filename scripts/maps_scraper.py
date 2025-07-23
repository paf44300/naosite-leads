#!/usr/bin/env python3
"""
Google Maps Scraper v1.5 - Harmonisation des données
Usage: python maps_scraper.py "plombier" --city "Nantes" --limit 50
"""

import os
import sys
import json
import time
import random
import argparse
import re
from datetime import datetime, timezone
from urllib.parse import quote_plus

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("ERREUR: Playwright non installé. Run: pip install playwright", file=sys.stderr)
    sys.exit(1)

# Configuration proxy Webshare
PROXY_HOST = os.getenv("p.webshare.io")
PROXY_PORT = os.getenv("80")
PROXY_USER = os.getenv("xftpfnvt")
PROXY_PASS = os.getenv("yulnmnbiq66j")

def log_error(message):
    """Log erreur vers stderr pour n8n monitoring"""
    print(f"[MAPS_SCRAPER ERROR] {message}", file=sys.stderr)

def log_info(message, debug=False):
    """Log info vers stderr si debug activé"""
    if debug:
        print(f"[MAPS_SCRAPER INFO] {message}", file=sys.stderr)

def normalize_activity(activity):
    """Standardise les activités selon les règles métier"""
    if not activity:
        return "Service"
    
    activity = activity.lower().strip()
    
    # Plombiers
    if any(word in activity for word in ['plomb', 'sanitaire', 'chauffage eau']):
        return 'Plombier'
    
    # Électriciens  
    if any(word in activity for word in ['électr', 'electric', 'éclairage', 'installation électrique']):
        return 'Électricien'
        
    # Chauffagistes
    if any(word in activity for word in ['chauff', 'climat', 'pompe à chaleur', 'chaudière']):
        return 'Chauffagiste'
        
    # Maçons
    if any(word in activity for word in ['maçon', 'macon', 'bâti', 'construction', 'gros œuvre']):
        return 'Maçon'
        
    # Autres métiers du bâtiment
    if any(word in activity for word in ['couvreur', 'toiture', 'étanchéité']):
        return 'Couvreur'
    if any(word in activity for word in ['menuisier', 'menuiserie', 'bois', 'fenêtre']):
        return 'Menuisier'
    if any(word in activity for word in ['peintre', 'peinture', 'décoration']):
        return 'Peintre'
    if any(word in activity for word in ['carreleur', 'carrelage', 'faïence']):
        return 'Carreleur'
    if any(word in activity for word in ['serrurier', 'serrurerie', 'métallerie']):
        return 'Serrurier'
    
    # Capitaliser première lettre si pas de correspondance
    return activity.title()

def normalize_phone(phone_raw):
    """Normalise téléphone au format E.164 français"""
    if not phone_raw:
        return None
    
    # Nettoyer : garder que les chiffres
    phone = re.sub(r'\D', '', str(phone_raw))
    
    if not phone:
        return None
    
    # Normalisation selon patterns français
    if phone.startswith('33'):
        phone = '+' + phone
    elif phone.startswith('0'):
        phone = '+33' + phone[1:]
    elif len(phone) == 9:
        phone = '+33' + phone
    elif len(phone) == 10 and phone.startswith('0'):
        phone = '+33' + phone[1:]
    
    # Validation longueur finale
    if len(phone) < 10 or len(phone) > 15:
        return None
        
    return phone

def extract_city_from_address(address):
    """Extrait la ville depuis une adresse complète"""
    if not address:
        return ""
    
    # Patterns pour extraire ville depuis adresse Google Maps
    patterns = [
        r'(\d{5})\s+([A-Z][a-zÀ-ÿ\s\-\']+)(?:,|$)',  # 44000 Nantes
        r'([A-Z][a-zÀ-ÿ\s\-\']+),?\s+(\d{5})',       # Nantes, 44000  
        r'([A-Z][a-zÀ-ÿ\s\-\']+)(?:,\s*France)?$',   # Nantes, France
    ]
    
    for pattern in patterns:
        match = re.search(pattern, address)
        if match:
            # Si le pattern contient un code postal, prendre le nom de ville
            if len(match.groups()) == 2:
                if match.group(1).isdigit():
                    return match.group(2).strip()
                else:
                    return match.group(1).strip()
            else:
                return match.group(1).strip()
    
    # Fallback : prendre le premier mot capitalisé
    words = address.split(',')
    for word in words:
        word = word.strip()
        if word and word[0].isupper() and not word.isdigit():
            return word
    
    return address.split(',')[0].strip() if ',' in address else address.strip()

def normalize_data(raw_data, query, search_city="", debug=False): # Ajout de search_city
    """Normalise les données selon le schéma unifié Naosite."""
    
    phone = normalize_phone(raw_data.get('phone', ''))
    address = raw_data.get('address', '') or ''
    
    # Extraction de la ville depuis l'adresse, SI POSSIBLE
    extracted_city = extract_city_from_address(address)
    
    # Logique de fallback : si on n'a pas pu extraire la ville de l'adresse,
    # on utilise la ville de la recherche initiale.
    city = extracted_city if extracted_city and len(extracted_city) < len(address) else search_city.title()

    name = (raw_data.get('name', '') or '').strip()
    if len(name) > 150:
        name = name[:150] + '...'
    
    activity = raw_data.get('activity') or query or ''
    normalized_activity = normalize_activity(activity)
    
    normalized_phone_digits = phone.replace('+', '').replace('-', '').replace(' ', '') if phone else ''
    mobile_detected = bool(phone and re.match(r'^\+33[67]', phone))
    
    postal_match = re.search(r'\b(\d{5})\b', address)
    city_code = postal_match.group(1) if postal_match else None
    
    result = {
        "name": name,
        "activity": normalized_activity,
        "phone": phone,
        "email": None,
        "address": address,
        "city": city, # Le champ ville sera maintenant correct
        "website": None,
        "source": "Maps",
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "normalized_phone": normalized_phone_digits,
        "mobile_detected": mobile_detected,
        "city_code": city_code,
        "raw_data": raw_data if debug else None
    }
    
    if not debug:
        result = {k: v for k, v in result.items() if v is not None}
    
    return result

def scrape_maps(query, city="", limit=50, debug=False):
    """Scraper Google Maps avec une recherche de sélecteurs robuste."""
    results = []
    log_info(f"Démarrage scraping Maps: query='{query}', city='{city}', limit={limit}", debug)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
            context = browser.new_context(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')
            page = context.new_page()

            search_query = f"{query} {city}".strip()
            # Utilisation d'une URL standard de Google Maps pour plus de stabilité
            maps_url = f"https://www.google.com/maps/search/{quote_plus(search_query)}"
            log_info(f"Accès URL: {maps_url}", debug)

            page.goto(maps_url, wait_until='domcontentloaded', timeout=60000)
            page.wait_for_selector('div[role="feed"]', timeout=30000) # Attendre que le conteneur principal des résultats soit chargé
            time.sleep(random.uniform(2, 4))

            # Scroll pour charger la page
            for _ in range(min(5, (limit // 10))):
                main_feed = page.query_selector('div[role="feed"]')
                if main_feed:
                    page.evaluate('(feed) => feed.scrollTop = feed.scrollHeight', main_feed)
                else: # Fallback si le feed n'est pas trouvé
                    page.mouse.wheel(0, 15000)
                time.sleep(random.uniform(1, 2))

            # Liste de sélecteurs potentiels pour les fiches business
            business_selectors = [
                'div[role="feed"] > div > div[role="article"]', # Sélecteur plus précis
                'div[role="article"]',
                'div[jsaction*="mouseover.search_result"]',
                'div.Nv2PK',
                'div.qBF1Pd'
            ]

            businesses = []
            for selector in business_selectors:
                businesses = page.query_selector_all(selector)
                if businesses:
                    log_info(f"Trouvé {len(businesses)} éléments avec le sélecteur: '{selector}'", debug)
                    break

            if not businesses:
                log_error("Aucun élément business trouvé sur la page avec les sélecteurs actuels.")
                browser.close()
                return []

            # (Le reste de la logique d'extraction reste identique)
            extracted_count = 0
            for idx, business in enumerate(businesses):
                if extracted_count >= limit:
                    break
                try:
                    name_el = business.query_selector('h3, .fontHeadlineSmall, [role="heading"], .qBF1Pd')
                    name = name_el.inner_text().strip() if name_el else ""
                    if not name:
                        continue
                    
                    has_website = business.query_selector('[data-value="Website"]')
                    if has_website:
                        log_info(f"Ignoré {name}: site web détecté", debug)
                        continue

                    full_text = business.inner_text()
                    phone, address = "", ""
                    
                    phone_match = re.search(r'(\+?\d{1,2}[\s\.\-]?\d([\s\.\-]?\d{2}){4})', full_text)
                    if phone_match: phone = phone_match.group(1)

                    address_match = re.search(r'(\d+[\s,]+(?:Quai|Rue|Boulevard|Avenue|Allée|Place|Impasse|Chemin)[\s\S]*?)(?:\n|$)', full_text)
                    if address_match: address = address_match.group(1).strip()
                    
                    raw_data = {'name': name, 'activity': query, 'phone': phone, 'address': address}
                    normalized = normalize_data(raw_data, query, city, debug)

                    if normalized.get('name') and (normalized.get('phone') or normalized.get('address')):
                        results.append(normalized)
                        extracted_count += 1
                except Exception as e:
                    log_error(f"Erreur extraction business {idx} ({name}): {e}")
                    continue
            
            log_info(f"Extraction terminée: {len(results)} résultats valides", debug)
            browser.close()
            
    except Exception as e:
        log_error(f"Erreur majeure dans scrape_maps: {e}")
    
    return results

def main():
    """Point d'entrée principal"""
    parser = argparse.ArgumentParser(description='Google Maps Scraper v1.5 avec harmonisation')
    parser.add_argument('query', help='Activité à rechercher (ex: "plombier")')
    parser.add_argument('--city', default='', help='Ville de recherche (ex: "Nantes")')
    parser.add_argument('--limit', type=int, default=50, help='Limite de résultats (défaut: 50)')
    parser.add_argument('--debug', action='store_true', help='Mode debug avec logs détaillés')
    
    args = parser.parse_args()
    
    if not args.query.strip():
        log_error("Query ne peut pas être vide")
        sys.exit(1)
    
    try:
        start_time = time.time()
        # Correction du typo : 'rresults' -> 'results'
        results = scrape_maps(args.query, args.city, args.limit, args.debug)
        duration = time.time() - start_time
        
        log_info(f"Scraping terminé en {duration:.2f}s: {len(results)} résultats", args.debug)
        
        for result in results:
            print(json.dumps(result, ensure_ascii=False))
            
    except Exception as e:
        log_error(f"Erreur fatale: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
    
    
        
        # Logs de résumé
        if args.debug:
            log_info(f"Scraping terminé en {duration:.2f}s: {len(results)} résultats", True)
            
            # Stats par type de téléphone
            mobile_count = sum(1 for r in results if r.get('mobile_detected'))
            log_info(f"Téléphones mobiles: {mobile_count}/{len(results)}", True)
            
            # Stats par ville
            cities = {}
            for r in results:
                city = r.get('city', 'Inconnu')
                cities[city] = cities.get(city, 0) + 1
            log_info(f"Répartition villes: {dict(list(cities.items())[:5])}", True)
        
        # Output JSON Lines pour n8n
        for result in results:
            print(json.dumps(result, ensure_ascii=False))
            
    except KeyboardInterrupt:
        log_info("Arrêt demandé par utilisateur", args.debug)
        sys.exit(0)
    except Exception as e:
        log_error(f"Erreur fatale: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
