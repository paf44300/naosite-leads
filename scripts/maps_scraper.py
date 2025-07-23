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
    # on utilise la ville de la recherche initiale. Si l'adresse contient un code postal,
    # extracted_city sera prioritaire.
    city = extracted_city if re.search(r'\d{5}', address) else search_city.title()

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
    """Scraper Google Maps avec anti-détection et harmonisation"""
    results = []
    
    log_info(f"Démarrage scraping Maps: query='{query}', city='{city}', limit={limit}", debug)
    
    with sync_playwright() as p:
        # 1. Configuration des args Chrome
        browser_args = [
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-blink-features=AutomationControlled',
            '--disable-extensions',
            '--no-first-run',
            '--disable-default-apps'
        ]

        # 2. Lancement du navigateur via le Backbone Connection Webshare EN CLAIR
        browser = p.chromium.launch(
            headless=True,
            args=browser_args,
            proxy={
                "server":   "http://p.webshare.io:80",
                "username": "xftpfnvt-1",
                "password": "yulnmnbiq66j"
            }
        )
        log_info("Backbone proxy configuré: xftpfnvt-1@p.webshare.io:80", debug)

        # Context avec user agent réaliste
        context = browser.new_context(
            viewport={'width': 1366, 'height': 768},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        page = context.new_page()
        
        try:
            # Construction URL de recherche
            search_query = f"{query} {city}".strip()
            maps_url = f"https://www.google.com/maps/search/{quote_plus(search_query)}"
            
            log_info(f"Accès URL: {maps_url}", debug)
            
            # Navigation avec timeout
            page.goto(maps_url, wait_until='networkidle', timeout=30000)
            
            # Attente chargement initial
            time.sleep(random.uniform(3, 5))
            
            # Scroll pour charger plus de résultats
            scroll_attempts = 0
            max_scrolls = min(10, (limit // 10) + 2)  # Adaptive selon limite
            
            for scroll in range(max_scrolls):
                try:
                    # Scroll dans la liste des résultats
                    page.evaluate("""
                        const sidebar = document.querySelector('[role="main"]');
                        if (sidebar) {
                            sidebar.scrollTop += 1000;
                        } else {
                            window.scrollBy(0, 1000);
                        }
                    """)
                    
                    time.sleep(random.uniform(1.5, 3))
                    scroll_attempts += 1
                    
                    log_info(f"Scroll {scroll + 1}/{max_scrolls} effectué", debug)
                    
                except Exception as e:
                    log_error(f"Erreur scroll {scroll}: {e}")
                    break
            
            # Extraction des résultats
            log_info("Début extraction données", debug)
            
            # Sélecteurs Google Maps (multiples pour robustesse)
            business_selectors = [
                '[data-result-index]',
                '[role="article"]',
                '.Nv2PK',
                '[jsaction*="mouseover"]'
            ]
            
            businesses = []
            for selector in business_selectors:
                try:
                    businesses = page.query_selector_all(selector)
                    if businesses:
                        log_info(f"Trouvé {len(businesses)} éléments avec sélecteur {selector}", debug)
                        break
                except:
                    continue
            
            if not businesses:
                log_error("Aucun élément business trouvé sur la page")
                return []
            
            extracted_count = 0
            
            for idx, business in enumerate(businesses):
                if extracted_count >= limit:
                    break
                
                try:
                    # Extraction nom
                    name_selectors = [
                        'h3', '.fontHeadlineSmall', '.qBF1Pd', 
                        '[role="button"] span', '.OSrXXb'
                    ]
                    
                    name = ""
                    for name_sel in name_selectors:
                        try:
                            name_el = business.query_selector(name_sel)
                            if name_el:
                                name = name_el.inner_text().strip()
                                if name and len(name) > 2:
                                    break
                        except:
                            continue
                    
                    if not name:
                        continue
                    
                    # Vérification absence site web (critère principal)
                    website_indicators = [
                        '[aria-label*="Site Web"]',
                        '[aria-label*="Website"]', 
                        '[data-value="Website"]',
                        'a[href^="http"]:not([href*="google"]):not([href*="maps"])'
                    ]
                    
                    has_website = False
                    for indicator in website_indicators:
                        try:
                            if business.query_selector(indicator):
                                has_website = True
                                break
                        except:
                            continue
                    
                    if has_website:
                        log_info(f"Ignoré {name}: site web détecté", debug)
                        continue
                    
                  # --- NOUVELLE LOGIQUE D'EXTRACTION ADRESSE ET TÉLÉPHONE ---
                    
                    # 1. On récupère tout le bloc d'infos textuelles du business
                    # Ce sélecteur est plus générique et cible le conteneur d'infos
                    info_block_el = business.query_selector('.fontBodyMedium')
                    info_text = info_block_el.inner_text().strip() if info_block_el else ""

                    phone = ""
                    address = ""

                    # 2. On cherche un numéro de téléphone dans ce bloc
                    phone_match = re.search(r'(\+?\d{1,2}[\s\.\-]?\d([\s\.\-]?\d{2}){4})', info_text)
                    if phone_match:
                        phone = phone_match.group(1)
                        # On nettoie le bloc d'infos du téléphone pour isoler l'adresse
                        info_text = info_text.replace(phone, '').strip()

                    # 3. On nettoie ce qui reste pour obtenir l'adresse
                    # On supprime les horaires et autres indicateurs comme "·"
                    address_cleaned = re.sub(r'^(Open|Closes|Ouvert|Ferme)[\s\S]*?·', '', info_text)
                    address_cleaned = address_cleaned.strip(' ·-').strip()
                    
                    # S'il reste quelque chose qui ressemble à une adresse, on la prend
                    if len(address_cleaned) > 5:
                         address = address_cleaned
                    else: # Fallback sur les anciens sélecteurs si la nouvelle méthode échoue
                        # --- NOUVELLE LOGIQUE D'EXTRACTION ADRESSE ---
                    
                    # 1. On récupère tout le texte du bloc business
                    full_text = business.inner_text()
                    address = ""

                    # 2. On extrait l'adresse avec une regex qui cible un format d'adresse
                    # Cherche : un numéro, un type de voie (Rue, Quai, etc.), et le reste de la ligne.
                    address_match = re.search(
                        r'(\d+[\s,]+(?:Quai|Rue|Boulevard|Avenue|Allée|Place|Impasse|Chemin|Route|Cours|Voie|Passage|Lieu-dit)[\s\S]*?)(?:\n|$)',
                        full_text
                    )
                    if address_match:
                        # On prend le résultat et on nettoie les espaces superflus
                        address = address_match.group(1).strip()
                    
                    # Construction données brutes
                    raw_data = {
                        'name': name,
                        'activity': query,  # Utilise la query comme activité de base
                        'phone': phone,
                        'address': address,
                        'index': idx
                    }
                    
                    # Normalisation selon schéma unifié
                    normalized = normalize_data(raw_data, query, city, debug)
                    
                    # Validation données minimales
                    if normalized.get('name') and (normalized.get('phone') or normalized.get('address')):
                        results.append(normalized)
                        extracted_count += 1
                        log_info(f"Extrait {extracted_count}/{limit}: {normalized['name']}", debug)
                    
                except Exception as e:
                    log_error(f"Erreur extraction business {idx}: {e}")
                    continue
            
            log_info(f"Extraction terminée: {len(results)} résultats valides", debug)
            
        except Exception as e:
            log_error(f"Erreur scraping Maps: {e}")
        finally:
            try:
                browser.close()
            except:
                pass
    
    return results

def main():
    """Point d'entrée principal"""
    parser = argparse.ArgumentParser(description='Google Maps Scraper v1.5 avec harmonisation')
    parser.add_argument('query', help='Activité à rechercher (ex: "plombier")')
    parser.add_argument('--city', default='', help='Ville de recherche (ex: "Nantes")')
    parser.add_argument('--limit', type=int, default=50, help='Limite de résultats (défaut: 50)')
    parser.add_argument('--debug', action='store_true', help='Mode debug avec logs détaillés')
    
    args = parser.parse_args()
    
    # Validation des arguments
    if not args.query.strip():
        log_error("Query ne peut pas être vide")
        sys.exit(1)
    
    if args.limit <= 0 or args.limit > 1000:
        log_error("Limit doit être entre 1 et 1000")
        sys.exit(1)
    
    # Lancement du scraping
    try:
        start_time = time.time()
        results = scrape_maps(args.query, args.city, args.limit, args.debug)
        duration = time.time() - start_time
        
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
