#!/usr/bin/env python3
"""
LeBonCoin Pro Scraper v1.5 - Annonces entreprises sans site
Usage: python lbc_scraper.py "plombier" --city "Nantes" --limit 30
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

# Configuration proxy Webshare (identique autres scrapers)
PROXY_HOST = os.getenv("WEBSHARE_HOST", "proxy.webshare.io")
PROXY_PORT = os.getenv("WEBSHARE_PORT", "8000")
PROXY_USER = os.getenv("WEBSHARE_USERNAME")
PROXY_PASS = os.getenv("WEBSHARE_PASS")

def log_error(message):
    """Log erreur vers stderr pour n8n monitoring"""
    print(f"[LBC_SCRAPER ERROR] {message}", file=sys.stderr)

def log_info(message, debug=False):
    """Log info vers stderr si debug activé"""
    if debug:
        print(f"[LBC_SCRAPER INFO] {message}", file=sys.stderr)

def normalize_activity(activity):
    """Standardise les activités (fonction identique autres scrapers)"""
    if not activity:
        return "Service"
    
    activity = activity.lower().strip()
    
    # Patterns métiers du bâtiment
    if any(word in activity for word in ['plomb', 'sanitaire', 'chauffage eau', 'dépannage plomberie']):
        return 'Plombier'
    
    if any(word in activity for word in ['électr', 'electric', 'éclairage', 'dépannage électrique']):
        return 'Électricien'
        
    if any(word in activity for word in ['chauff', 'climat', 'pompe à chaleur', 'chaudière', 'climatisation']):
        return 'Chauffagiste'
        
    if any(word in activity for word in ['maçon', 'macon', 'bâti', 'construction', 'gros œuvre', 'maçonnerie']):
        return 'Maçon'
    
    # Autres métiers fréquents sur LBC
    if any(word in activity for word in ['couvreur', 'toiture', 'charpente']):
        return 'Couvreur'
    if any(word in activity for word in ['menuisier', 'menuiserie', 'bois', 'agencement']):
        return 'Menuisier'
    if any(word in activity for word in ['peintre', 'peinture', 'rénovation']):
        return 'Peintre'
    if any(word in activity for word in ['carreleur', 'carrelage', 'faïence']):
        return 'Carreleur'
    if any(word in activity for word in ['serrurier', 'serrurerie', 'dépannage serrure']):
        return 'Serrurier'
    
    # Services
    if any(word in activity for word in ['nettoyage', 'ménage', 'entretien']):
        return 'Nettoyage'
    if any(word in activity for word in ['jardinage', 'paysage', 'espaces verts']):
        return 'Jardinage'
    if any(word in activity for word in ['déménagement', 'transport']):
        return 'Déménagement'
    
    return activity.title()

def normalize_phone(phone_raw):
    """Normalise téléphone (LBC souvent mobiles)"""
    if not phone_raw:
        return None
    
    # LBC affiche souvent les téléphones avec espaces
    phone = re.sub(r'[^\d]', '', str(phone_raw))
    
    if not phone:
        return None
    
    # Normalisation française
    if phone.startswith('33'):
        phone = '+' + phone
    elif phone.startswith('0'):
        phone = '+33' + phone[1:]
    elif len(phone) == 9:
        phone = '+33' + phone
    elif len(phone) == 10 and phone.startswith('0'):
        phone = '+33' + phone[1:]
    
    # Validation
    if len(phone) < 10 or len(phone) > 15:
        return None
        
    return phone

def extract_city_lbc(address):
    """Extraction ville format LeBonCoin"""
    if not address:
        return ""
    
    # LBC patterns : "Nantes et périphérie", "44000", "Loire-Atlantique"
    patterns = [
        r'(\w+)\s+et\s+périphérie',                    # Nantes et périphérie
        r'(\w+)\s+\(\d{5}\)',                          # Nantes (44000)
        r'(\d{5})',                                     # 44000
        r'([A-Z][a-zÀ-ÿ\s\-\']+)(?:,|$)',             # Première ville
    ]
    
    for pattern in patterns:
        match = re.search(pattern, address)
        if match:
            city = match.group(1)
            
            # Si code postal, convertir en ville
            if city.isdigit():
                dept_mapping = {
                    '44': 'Nantes',
                    '49': 'Angers', 
                    '85': 'La Roche-sur-Yon',
                    '35': 'Rennes',
                    '56': 'Vannes'
                }
                return dept_mapping.get(city[:2], city)
            
            return city
    
    # Fallback
    return address.split(',')[0].strip() if ',' in address else address.strip()

def normalize_data(raw_data, query, debug=False):
    """Normalise données LBC selon schéma unifié Naosite"""
    
    # Téléphone (LBC souvent mobiles)
    phone = normalize_phone(raw_data.get('phone', ''))
    
    # Email rare sur LBC (masqué)
    email = None  # LBC masque généralement les emails
    
    # Ville LBC
    address = raw_data.get('address', '') or ''
    city = extract_city_lbc(address)
    
    # Nom (souvent nom du vendeur professionnel)
    name = (raw_data.get('name', '') or '').strip()
    if len(name) > 150:
        name = name[:150] + '...'
    
    # Activité (dérivée du titre de l'annonce)
    activity = raw_data.get('activity') or query or ''
    normalized_activity = normalize_activity(activity)
    
    # Champs calculés
    normalized_phone_digits = phone.replace('+', '').replace('-', '').replace(' ', '') if phone else ''
    mobile_detected = bool(phone and re.match(r'^\+33[67]', phone))
    
    # Code postal
    postal_match = re.search(r'\b(\d{5})\b', address)
    city_code = postal_match.group(1) if postal_match else None
    
    result = {
        "name": name,
        "activity": normalized_activity,
        "phone": phone,
        "email": email,  # Généralement null pour LBC
        "address": address,
        "city": city,
        "website": None,  # Toujours null (critère filtrage)
        "source": "leboncoin",
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        
        # Champs calculés
        "normalized_phone": normalized_phone_digits,
        "mobile_detected": mobile_detected,
        "city_code": city_code,
        
        # Debug
        "raw_data": raw_data if debug else None
    }
    
    # Nettoyer les None si pas debug
    if not debug:
        result = {k: v for k, v in result.items() if v is not None}
    
    return result

def scrape_lbc(query, city="", limit=30, debug=False):
    """Scraper LeBonCoin Pro annonces services"""
    results = []
    
    log_info(f"Démarrage scraping LBC: query='{query}', city='{city}', limit={limit}", debug)
    
    with sync_playwright() as p:
        # Configuration navigateur
        browser_args = [
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-blink-features=AutomationControlled',
            '--disable-extensions'
        ]
        
        browser_kwargs = {'headless': True, 'args': browser_args}
        
        # Proxy si disponible
        if PROXY_USER and PROXY_PASS and PROXY_HOST:
            proxy_config = {
                "server": f"http://{PROXY_HOST}:{PROXY_PORT}",
                "username": PROXY_USER,
                "password": PROXY_PASS
            }
            browser_kwargs['proxy'] = proxy_config
            log_info(f"Proxy configuré: {PROXY_HOST}:{PROXY_PORT}", debug)
        
        try:
            browser = p.chromium.launch(**browser_kwargs)
        except Exception as e:
            log_error(f"Erreur lancement navigateur: {e}")
            return []
        
        context = browser.new_context(
            viewport={'width': 1366, 'height': 768},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        page = context.new_page()
        
        try:
            # URL LBC services pros (catégorie 34 = services)
            search_query = f"{query} {city}".strip()
            lbc_url = f"https://www.leboncoin.fr/recherche?category=34&text={quote_plus(query)}&locations={quote_plus(city)}"
            
            log_info(f"Accès URL LBC: {lbc_url}", debug)
            
            page.goto(lbc_url, wait_until='networkidle', timeout=30000)
            time.sleep(random.uniform(4, 6))  # LBC plus lent à charger
            
            # Gestion cookies/RGPD
            try:
                cookie_selectors = [
                    'button[id*="accept"]',
                    'button[id*="consent"]', 
                    'button[data-testid="accept"]',
                    '#didomi-notice-agree-button'
                ]
                
                for cookie_sel in cookie_selectors:
                    try:
                        cookie_btn = page.query_selector(cookie_sel)
                        if cookie_btn:
                            cookie_btn.click()
                            time.sleep(1)
                            log_info("Cookies LBC acceptés", debug)
                            break
                    except:
                        continue
            except:
                pass
            
            # Scroll progressif pour charger annonces (LBC lazy loading)
            scroll_count = 0
            max_scrolls = min(8, (limit // 10) + 2)
            
            for scroll in range(max_scrolls):
                try:
                    page.evaluate("window.scrollBy(0, 800)")
                    time.sleep(random.uniform(2, 3))
                    scroll_count += 1
                    log_info(f"Scroll LBC {scroll + 1}/{max_scrolls}", debug)
                except:
                    break
            
            # Extraction annonces
            log_info("Début extraction annonces LBC", debug)
            
            # Sélecteurs LBC (adaptatifs selon évolution site)
            ad_selectors = [
                '[data-qa-id="aditem_container"]',
                '.styles_AdCard__container',
                '[data-testid="ad-item"]',
                '.ad-item'
            ]
            
            ads = []
            for selector in ad_selectors:
                try:
                    ads = page.query_selector_all(selector)
                    if ads:
                        log_info(f"Trouvé {len(ads)} annonces avec sélecteur {selector}", debug)
                        break
                except:
                    continue
            
            if not ads:
                log_error("Aucune annonce trouvée sur LBC")
                return []
            
            extracted_count = 0
            
            for idx, ad in enumerate(ads):
                if extracted_count >= limit:
                    break
                
                try:
                    # Extraction titre annonce
                    title_selectors = [
                        '[data-qa-id="aditem_title"]',
                        '.styles_AdCardTitle__title',
                        '[data-testid="ad-title"]',
                        'h3'
                    ]
                    
                    title = ""
                    for title_sel in title_selectors:
                        try:
                            title_el = ad.query_selector(title_sel)
                            if title_el:
                                title = title_el.inner_text().strip()
                                if title and len(title) > 5:
                                    break
                        except:
                            continue
                    
                    if not title:
                        continue
                    
                    # Vérification absence site web dans titre/description
                    website_keywords = ['site', 'web', 'www', 'http', '.fr', '.com', 'internet']
                    if any(keyword in title.lower() for keyword in website_keywords):
                        log_info(f"Ignoré {title[:50]}: mention site web", debug)
                        continue
                    
                    # Extraction vendeur/entreprise
                    seller_selectors = [
                        '.styles_AdCardSellerName__name',
                        '[data-qa-id="aditem_seller"]',
                        '.seller-name',
                        '.advertiser-name'
                    ]
                    
                    seller = ""
                    for seller_sel in seller_selectors:
                        try:
                            seller_el = ad.query_selector(seller_sel)
                            if seller_el:
                                seller = seller_el.inner_text().strip()
                                if seller and len(seller) > 2:
                                    break
                        except:
                            continue
                    
                    # Extraction localisation
                    location_selectors = [
                        '[data-qa-id="aditem_location"]',
                        '.styles_AdCardLocation__location',
                        '.ad-location',
                        '.location'
                    ]
                    
                    location = ""
                    for loc_sel in location_selectors:
                        try:
                            loc_el = ad.query_selector(loc_sel)
                            if loc_el:
                                location = loc_el.inner_text().strip()
                                if location:
                                    break
                        except:
                            continue
                    
                    # Prix (pour vérifier que c'est une offre de service)
                    price_selectors = [
                        '[data-qa-id="aditem_price"]',
                        '.styles_AdCardPrice__price',
                        '.price'
                    ]
                    
                    price = ""
                    for price_sel in price_selectors:
                        try:
                            price_el = ad.query_selector(price_sel)
                            if price_el:
                                price = price_el.inner_text().strip()
                                break
                        except:
                            continue
                    
                    # Validation : c'est bien un service professionnel
                    service_indicators = ['€', 'prix', 'tarif', 'devis', 'intervention']
                    is_service = any(indicator in (title + ' ' + price).lower() for indicator in service_indicators)
                    
                    if not is_service:
                        continue
                    
                    # Construction données (pas de téléphone disponible sans cliquer)
                    raw_data = {
                        'name': seller or f"Annonceur {title[:30]}",
                        'activity': title,
                        'phone': "",  # Nécessiterait clic sur annonce
                        'address': location,
                        'price': price,
                        'index': idx
                    }
                    
                    # Normalisation
                    normalized = normalize_data(raw_data, query, debug)
                    
                    # Validation minimale : nom et adresse
                    if normalized['name'] and normalized['address']:
                        results.append(normalized)
                        extracted_count += 1
                        log_info(f"Extrait LBC {extracted_count}/{limit}: {normalized['name'][:50]}", debug)
                    
                except Exception as e:
                    log_error(f"Erreur extraction annonce {idx}: {e}")
                    continue
            
            log_info(f"Extraction LBC terminée: {len(results)} annonces", debug)
            
        except Exception as e:
            log_error(f"Erreur scraping LBC: {e}")
        finally:
            try:
                browser.close()
            except:
                pass
    
    return results

def main():
    """Point d'entrée principal"""
    parser = argparse.ArgumentParser(description='LeBonCoin Pro Scraper v1.5 - Services sans site')
    parser.add_argument('query', help='Service à rechercher (ex: "plombier")')
    parser.add_argument('--city', default='', help='Ville de recherche (ex: "Nantes")')
    parser.add_argument('--limit', type=int, default=30, help='Limite de résultats (défaut: 30)')
    parser.add_argument('--debug', action='store_true', help='Mode debug avec logs détaillés')
    
    args = parser.parse_args()
    
    # Validation
    if not args.query.strip():
        log_error("Query ne peut pas être vide")
        sys.exit(1)
    
    if args.limit <= 0 or args.limit > 500:
        log_error("Limit doit être entre 1 et 500")
        sys.exit(1)
    
    # Scraping
    try:
        start_time = time.time()
        results = scrape_lbc(args.query, args.city, args.limit, args.debug)
        duration = time.time() - start_time
        
        # Stats si debug
        if args.debug:
            log_info(f"Scraping LBC terminé en {duration:.2f}s: {len(results)} annonces", True)
            
            # Stats activités détectées
            activities = {}
            for r in results:
                activity = r.get('activity', 'Inconnu')
                activities[activity] = activities.get(activity, 0) + 1
            
            top_activities = sorted(activities.items(), key=lambda x: x[1], reverse=True)[:5]
            log_info(f"Top activités: {dict(top_activities)}", True)
            
            # Stats localisation
            cities = {}
            for r in results:
                city = r.get('city', 'Inconnu')
                cities[city] = cities.get(city, 0) + 1
            log_info(f"Répartition villes: {dict(list(cities.items())[:3])}", True)
        
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
