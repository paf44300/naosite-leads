#!/usr/bin/env python3
"""
LeBonCoin Pro Scraper v2.0 - CORRIGÉ avec extraction téléphone anti-horaires
Usage: python lbc_scraper.py "plombier" --city "Nantes" --limit 30 --session-id "abc123"
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

def log_error(message):
    """Log erreur vers stderr pour n8n monitoring"""
    print(f"[LBC_SCRAPER ERROR] {message}", file=sys.stderr)

def log_info(message, debug=False):
    """Log info vers stderr si debug activé"""
    if debug:
        print(f"[LBC_SCRAPER INFO] {message}", file=sys.stderr)

def extract_clean_phone_lbc(phone_text, debug=False):
    """
    CORRECTION CRITIQUE : Extraction téléphone LBC anti-contamination horaires
    LBC souvent mobiles : 06 12 34 56 78
    """
    if not phone_text:
        return None
    
    # Nettoyer d'abord les patterns d'horaires courants
    cleaned_text = phone_text.lower()
    
    # Supprimer les patterns d'horaires spécifiques LBC
    business_hours_patterns = [
        r'\b(?:open|closed|ouvert|fermé|disponible|dispo)\b',
        r'\b(?:lun|mar|mer|jeu|ven|sam|dim)\w*',
        r'\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
        r'\b(?:2[0-4]|1[0-9])[h:]?\d{0,2}\b',  # 20h, 21:00, etc.
        r'\b(?:matin|après-midi|soir|journée|soirée)\b',
        r'\b(?:de|à|from|to|until|jusqu)\b',   # Connecteurs temporels
    ]
    
    for pattern in business_hours_patterns:
        cleaned_text = re.sub(pattern, ' ', cleaned_text, flags=re.IGNORECASE)
    
    # LBC patterns téléphone (souvent mobiles)
    lbc_phone_patterns = [
        r'(\+33[67]\d{8})',                    # Mobile +33 6/7
        r'(0[67](?:[\s\.-]?\d){8})',           # Mobile 06/07
        r'(\+33[1-5]\d{8})',                   # Fixe +33
        r'(0[1-5](?:[\s\.-]?\d){8})',          # Fixe 01-05
        r'(\d{2}[\s\.-]?\d{2}[\s\.-]?\d{2}[\s\.-]?\d{2}[\s\.-]?\d{2})', # Format espacé
    ]
    
    for pattern in lbc_phone_patterns:
        match = re.search(pattern, cleaned_text)
        if match:
            raw_phone = match.group(1)
            
            # Validation : garder que les chiffres pour validation
            digits_only = re.sub(r'\D', '', raw_phone)
            
            if len(digits_only) >= 9 and len(digits_only) <= 11:
                # Vérifier que ce n'est pas un pattern d'horaire déguisé
                # Pour LBC, priorité aux mobiles (06/07)
                if digits_only.startswith('06') or digits_only.startswith('07') or \
                   digits_only.startswith('3366') or digits_only.startswith('3367'):
                    if debug:
                        log_info(f"Mobile LBC trouvé: {raw_phone} → {digits_only}", True)
                    return normalize_phone_lbc(digits_only)
                elif digits_only.startswith('0') and digits_only[1] in '12345':
                    if debug:
                        log_info(f"Fixe LBC trouvé: {raw_phone} → {digits_only}", True)
                    return normalize_phone_lbc(digits_only)
    
    return None

def normalize_phone_lbc(phone_digits):
    """Normalise téléphone LBC au format E.164"""
    if not phone_digits or len(phone_digits) < 9:
        return None
    
    # Normalisation française (LBC souvent mobiles)
    if phone_digits.startswith('33'):
        phone = '+' + phone_digits
    elif phone_digits.startswith('0'):
        phone = '+33' + phone_digits[1:]
    elif len(phone_digits) == 9:
        phone = '+33' + phone_digits
    elif len(phone_digits) == 10 and phone_digits.startswith('0'):
        phone = '+33' + phone_digits[1:]
    else:
        phone = '+33' + phone_digits
    
    # Validation longueur finale
    if len(phone) < 12 or len(phone) > 15:
        return None
        
    return phone

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

def normalize_data(raw_data, query, session_id=None, debug=False):
    """Normalise données LBC selon schéma unifié Naosite"""
    
    # Téléphone LBC CORRIGÉ
    phone = extract_clean_phone_lbc(raw_data.get('phone_text', '') or raw_data.get('description', ''), debug)
    
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
    activity = raw_data.get('activity') or raw_data.get('title') or query or ''
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
        
        # Métadonnées session
        "_session_id": session_id,
        "_scraper_source": "lbc",
        
        # Debug
        "raw_data": raw_data if debug else None
    }
    
    # Nettoyer les None si pas debug
    if not debug:
        result = {k: v for k, v in result.items() if v is not None}
    
    return result

def scrape_lbc(query, city="", limit=30, session_id=None, debug=False):
    """Scraper LeBonCoin Pro annonces services CORRIGÉ"""
    results = []
    
    log_info(f"Démarrage scraping LBC v2.0: query='{query}', city='{city}', limit={limit}", debug)
    log_info(f"Session: {session_id}", debug)
    
    with sync_playwright() as p:
        # Configuration navigateur
        browser_args = [
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-blink-features=AutomationControlled',
            '--disable-extensions'
        ]
        
        # Proxy Webshare en dur
        browser = p.chromium.launch(
            headless=True,
            args=browser_args,
            proxy={
                "server": "http://p.webshare.io:80",
                "username": "xftpfnvt-1",
                "password": "yulnmnbiq66j"
            }
        )
        log_info("Proxy Webshare configuré: xftpfnvt-1@p.webshare.io:80", debug)
        
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
                    '#didomi-notice-agree-button',
                    '[data-testid="accept-all"]'
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
            max_scrolls = min(8, (limit // 8) + 2)
            
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
                '.ad-item',
                '[data-testid="adCard"]'
            ]
            
            ads = []
            for selector in ad_selectors:
                try:
                    ads = page.query_selector_all(selector)
                    if ads:
                        log_info(f"Trouvé {len(ads)} annonces LBC avec sélecteur {selector}", debug)
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
                        'h3',
                        '[data-testid="adTitle"]'
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
                        '.advertiser-name',
                        '[data-testid="sellerName"]'
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
                        '.location',
                        '[data-testid="adLocation"]'
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
                        '.price',
                        '[data-testid="adPrice"]'
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
                    service_indicators = ['€', 'prix', 'tarif', 'devis', 'intervention', 'service']
                    is_service = any(indicator in (title + ' ' + price).lower() for indicator in service_indicators)
                    
                    if not is_service:
                        continue
                    
                    # Récupérer description/texte complet pour extraction téléphone
                    ad_text = ad.inner_text()
                    
                    # Construction données (téléphone extrait du texte complet)
                    raw_data = {
                        'name': seller or f"Annonceur {title[:30]}",
                        'activity': title,
                        'title': title,
                        'phone_text': ad_text,  # CRITIQUE pour extraction téléphone
                        'description': ad_text,
                        'address': location,
                        'price': price,
                        'index': idx
                    }
                    
                    # Normalisation CORRIGÉE
                    normalized = normalize_data(raw_data, query, session_id, debug)
                    
                    # Validation minimale : nom et adresse
                    if normalized['name'] and normalized['address']:
                        results.append(normalized)
                        extracted_count += 1
                        phone_status = "📞" if normalized.get('phone') else "📍"
                        log_info(f"Extrait LBC {extracted_count}/{limit}: {phone_status} {normalized['name'][:40]}", debug)
                    
                except Exception as e:
                    log_error(f"Erreur extraction annonce LBC {idx}: {e}")
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
    parser = argparse.ArgumentParser(description='LeBonCoin Pro Scraper v2.0 avec extraction téléphone corrigée')
    parser.add_argument('query', help='Service à rechercher (ex: "plombier")')
    parser.add_argument('--city', default='', help='Ville de recherche (ex: "Nantes")')
    parser.add_argument('--limit', type=int, default=30, help='Limite de résultats (défaut: 30)')
    parser.add_argument('--session-id', default=None, help='ID de session pour tracking')
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
        results = scrape_lbc(args.query, args.city, args.limit, 
                            getattr(args, 'session_id'), args.debug)
        duration = time.time() - start_time
        
        # Stats si debug
        if args.debug:
            log_info(f"Scraping LBC terminé en {duration:.2f}s: {len(results)} annonces", True)
            
            # Stats téléphones (spécificité LBC : souvent mobiles)
            phone_count = sum(1 for r in results if r.get('phone'))
            mobile_count = sum(1 for r in results if r.get('mobile_detected'))
            log_info(f"Téléphones: {phone_count} total, {mobile_count} mobiles", True)
            
            # Stats activités détectées
            activities = {}
            for r in results:
                activity = r.get('activity', 'Inconnu')
                activities[activity] = activities.get(activity, 0) + 1
            
            top_activities = sorted(activities.items(), key=lambda x: x[1], reverse=True)[:3]
            log_info(f"Top activités: {dict(top_activities)}", True)
        
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
