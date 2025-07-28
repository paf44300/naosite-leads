#!/usr/bin/env python3
"""
Google Maps Scraper v2.0 - CORRIGÉ avec extraction téléphone anti-horaires
Usage: python maps_scraper.py "plombier" --city "Nantes" --limit 5 --offset 10 --session-id "abc123"
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
    print(f"[MAPS_SCRAPER ERROR] {message}", file=sys.stderr)

def log_info(message, debug=False):
    """Log info vers stderr si debug activé"""
    if debug:
        print(f"[MAPS_SCRAPER INFO] {message}", file=sys.stderr)

def extract_clean_phone_maps(business_text, debug=False):
    """
    CORRECTION CRITIQUE : Extraction téléphone anti-contamination horaires
    """
    if not business_text or len(business_text) > 500:
        return None
    
    # Séparer le texte en lignes pour analyse ligne par ligne
    lines = business_text.split('\n')
    
    for line in lines:
        line = line.strip()
        
        # SKIP explicite des lignes contenant des horaires
        if re.search(r'\b(?:open|closed|ouvert|fermé|hours|horaires)\b', line.lower()):
            if debug:
                log_info(f"Ligne ignorée (horaires): {line[:50]}", True)
            continue
            
        # SKIP lignes avec patterns d'heures : 21h, 22:00, etc.
        if re.search(r'\b(?:2[0-4]|1[0-9])[h:]?\d{0,2}\b', line):
            if debug:
                log_info(f"Ligne ignorée (heures): {line[:50]}", True)
            continue
            
        # SKIP lignes avec jours de la semaine
        if re.search(r'\b(?:lun|mar|mer|jeu|ven|sam|dim|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', line.lower()):
            if debug:
                log_info(f"Ligne ignorée (jours): {line[:50]}", True)
            continue
        
        # Chercher téléphone sur ligne "propre"
        phone_patterns = [
            r'(\+33[1-9](?:\d[\s\.-]?){8})',  # +33 format
            r'(0[1-9](?:\d[\s\.-]?){8})',     # 0X format français
        ]
        
        for pattern in phone_patterns:
            match = re.search(pattern, line)
            if match:
                raw_phone = match.group(1)
                
                # Validation supplémentaire : rejeter si ressemble à horaire
                digits_only = re.sub(r'\D', '', raw_phone)
                if len(digits_only) >= 9:
                    # Vérifier que les 2-3 premiers chiffres ne sont pas des heures
                    first_two = digits_only[:2]
                    if first_two.startswith('0') or int(first_two) <= 24:
                        # C'est probablement un téléphone valide
                        if debug:
                            log_info(f"Téléphone trouvé: {raw_phone} (ligne: {line[:50]})", True)
                        return normalize_phone(raw_phone)
    
    return None

def normalize_phone(phone_raw):
    """Normalise téléphone au format E.164 français"""
    if not phone_raw:
        return None
    
    # Nettoyer : garder que les chiffres
    phone = re.sub(r'\D', '', str(phone_raw))
    
    if not phone or len(phone) < 9:
        return None
    
    # Normalisation selon patterns français
    if phone.startswith('33'):
        phone = '+' + phone
    elif phone.startswith('0'):
        phone = '+33' + phone[1:]
    elif len(phone) == 9:
        phone = '+33' + phone
    
    # Validation longueur finale (téléphones français)
    if len(phone) < 12 or len(phone) > 15:
        return None
        
    return phone

def normalize_activity(activity):
    """Standardise les activités selon les règles métier"""
    if not activity:
        return "Service"
    
    activity = activity.lower().strip()
    
    # Mapping des activités
    activity_map = {
        'plomb': 'Plombier',
        'sanitaire': 'Plombier',
        'électr': 'Électricien',
        'electric': 'Électricien',
        'chauff': 'Chauffagiste',
        'climat': 'Chauffagiste',
        'maçon': 'Maçon',
        'macon': 'Maçon',
        'couvreur': 'Couvreur',
        'toiture': 'Couvreur',
        'menuisier': 'Menuisier',
        'peintre': 'Peintre',
        'carreleur': 'Carreleur',
        'serrurier': 'Serrurier'
    }
    
    for key, value in activity_map.items():
        if key in activity:
            return value
    
    return activity.title()

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
    
    # Fallback : dernier élément avant France
    parts = address.split(',')
    for i in range(len(parts) - 1, -1, -1):
        part = parts[i].strip()
        if part and part != 'France' and not part.isdigit():
            return part
    
    return address.split(',')[0].strip()

def normalize_data(raw_data, query, session_id=None, debug=False):
    """Normalise les données selon le schéma unifié Naosite"""
    
    # Extraction téléphone CORRIGÉE
    phone = extract_clean_phone_maps(raw_data.get('business_text', '') or '', debug)
    
    # Extraction ville propre
    address = raw_data.get('address', '') or ''
    city = extract_city_from_address(address)
    
    # Nom entreprise nettoyé
    name = (raw_data.get('name', '') or '').strip()
    if len(name) > 150:
        name = name[:150] + '...'
    
    # Activité standardisée
    activity = raw_data.get('activity') or query or ''
    normalized_activity = normalize_activity(activity)
    
    # Calculs dérivés
    normalized_phone_digits = phone.replace('+', '').replace('-', '').replace(' ', '') if phone else ''
    mobile_detected = bool(phone and re.match(r'^\+33[67]', phone))
    
    # Extraction code postal
    postal_match = re.search(r'\b(\d{5})\b', address)
    city_code = postal_match.group(1) if postal_match else None
    
    result = {
        "name": name,
        "activity": normalized_activity,
        "phone": phone,
        "email": None,  # Google Maps rarement emails
        "address": address,
        "city": city,
        "website": None,  # Toujours null (critère de filtrage)
        "source": "google_maps",
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        
        # Champs calculés pour le scoring
        "normalized_phone": normalized_phone_digits,
        "mobile_detected": mobile_detected,
        "city_code": city_code,
        
        # Métadonnées session/debug
        "_session_id": session_id,
        "_scraper_source": "maps",
        "raw_data": raw_data if debug else None
    }
    
    # Nettoyer les None si pas debug
    if not debug:
        result = {k: v for k, v in result.items() if v is not None}
    
    return result

def scrape_maps(query, city="", limit=50, offset=0, session_id=None, debug=False):
    """
    Scraper Google Maps avec anti-détection et offset CORRIGÉ
    """
    results = []
    
    log_info(f"=== DÉMARRAGE SCRAPING MAPS v2.0 ===", debug)
    log_info(f"Query: '{query}', City: '{city}', Limit: {limit}, Offset: {offset}", debug)
    log_info(f"Session: {session_id}", debug)
    
    with sync_playwright() as p:
        browser_args = [
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-blink-features=AutomationControlled',
            '--disable-extensions',
            '--no-first-run',
            '--disable-default-apps'
        ]

        # Configuration du proxy WEBSHARE en dur
        browser_kwargs = {
            'headless': True,
            'args': browser_args,
            'proxy': {
                "server": "http://p.webshare.io:80",
                "username": "xftpfnvt-1",
                "password": "yulnmnbiq66j"
            }
        }
        
        log_info("Proxy Webshare configuré: xftpfnvt-1@p.webshare.io:80", debug)

        browser = p.chromium.launch(**browser_kwargs)

        # Context avec user agent réaliste
        context = browser.new_context(
            viewport={'width': 1366, 'height': 768},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='fr-FR'
        )
        
        page = context.new_page()
        
        try:
            # Construction URL de recherche
            search_query = f"{query} {city}".strip()
            maps_url = f"https://www.google.com/maps/search/{quote_plus(search_query)}"
            
            log_info(f"URL Maps: {maps_url}", debug)
            
            # Navigation avec timeout
            page.goto(maps_url, wait_until='domcontentloaded', timeout=30000)
            
            # Attente chargement initial
            time.sleep(random.uniform(3, 5))
            
            # Accepter cookies si présent
            try:
                accept_buttons = page.query_selector_all('button')
                for btn in accept_buttons:
                    text = btn.inner_text().lower()
                    if 'accepter' in text or 'accept' in text or 'tout accepter' in text:
                        btn.click()
                        time.sleep(1)
                        log_info("Cookies acceptés", debug)
                        break
            except:
                pass
            
            # Attendre que les résultats soient visibles
            try:
                page.wait_for_selector('[role="main"]', timeout=10000)
                log_info("Zone de résultats trouvée", debug)
            except:
                log_error("Zone de résultats non trouvée")
            
            # Scroll pour charger plus de résultats avec offset
            total_needed = limit + offset
            scroll_count = 0
            last_count = 0
            no_change_count = 0
            max_scrolls = min(25, (total_needed // 3) + 8)
            
            log_info(f"Début scrolling pour charger {total_needed} résultats (offset: {offset})", debug)
            
            while scroll_count < max_scrolls:
                try:
                    # Compter les résultats actuels
                    current_results = page.query_selector_all('[role="article"]')
                    current_count = len(current_results)
                    
                    log_info(f"Scroll {scroll_count + 1}: {current_count} résultats visibles", debug)
                    
                    # Si on a assez de résultats, arrêter
                    if current_count >= total_needed:
                        log_info(f"Assez de résultats chargés: {current_count}", debug)
                        break
                    
                    # Si aucun changement après plusieurs scrolls, arrêter
                    if current_count == last_count:
                        no_change_count += 1
                        if no_change_count >= 3:
                            log_info(f"Plus de résultats à charger (stable à {current_count})", debug)
                            break
                    else:
                        no_change_count = 0
                    
                    last_count = current_count
                    
                    # Scroll dans la liste des résultats
                    page.evaluate("""
                        const scrollables = document.querySelectorAll('[role="main"], .m6QErb, [aria-label*="Résultats"]');
                        let scrolled = false;
                        for (const element of scrollables) {
                            if (element && element.scrollHeight > element.clientHeight) {
                                element.scrollTop += 800;
                                scrolled = true;
                                break;
                            }
                        }
                        if (!scrolled) {
                            window.scrollBy(0, 800);
                        }
                    """)
                    
                    time.sleep(random.uniform(2, 3))
                    scroll_count += 1
                    
                except Exception as e:
                    log_error(f"Erreur scroll {scroll_count}: {e}")
                    break
            
            # Attendre un peu après le dernier scroll
            time.sleep(2)
            
            # Extraction des résultats
            log_info("=== DÉBUT EXTRACTION DES DONNÉES ===", debug)
            
            # Sélecteurs Google Maps mis à jour
            business_selectors = [
                '[role="article"]',  # Sélecteur principal actuel
                'div[jsaction*="mouseover"]:has(a[aria-label])',  # Fallback
                '.Nv2PK',  # Ancien sélecteur
                'div[data-index]'  # Autre fallback
            ]
            
            businesses = []
            for selector in business_selectors:
                try:
                    businesses = page.query_selector_all(selector)
                    if businesses:
                        log_info(f"✅ Trouvé {len(businesses)} éléments avec sélecteur: {selector}", debug)
                        break
                except:
                    continue
            
            if not businesses:
                log_error("❌ Aucun élément business trouvé ! Vérifier les sélecteurs CSS")
                return []
            
            # Extraction avec gestion de l'offset
            extracted_count = 0
            skipped_count = 0
            
            log_info(f"Traitement de {len(businesses)} businesses (offset: {offset})", debug)
            
            for idx, business in enumerate(businesses):
                # Skip les premiers résultats selon l'offset
                if skipped_count < offset:
                    skipped_count += 1
                    continue
                
                if extracted_count >= limit:
                    break
                
                try:
                    # Récupérer tout le texte du business pour extraction téléphone
                    business_text = business.inner_text()
                    
                    if debug:
                        log_info(f"\n--- Business {idx} (après offset) ---", True)
                        log_info(f"Texte: {business_text[:200]}...", True)
                    
                    # Extraction nom - méthodes multiples
                    name = ""
                    
                    # Méthode 1: Via aria-label des liens
                    try:
                        link = business.query_selector('a[aria-label]')
                        if link:
                            name = link.get_attribute('aria-label') or ''
                            if debug:
                                log_info(f"Nom via aria-label: {name}", True)
                    except:
                        pass
                    
                    # Méthode 2: Texte du titre
                    if not name:
                        name_selectors = [
                            '.fontHeadlineSmall',
                            '.qBF1Pd',
                            'span.OSrXXb',
                            'h3'
                        ]
                        
                        for name_sel in name_selectors:
                            try:
                                name_el = business.query_selector(name_sel)
                                if name_el:
                                    name = name_el.inner_text().strip()
                                    if name and len(name) > 2:
                                        if debug:
                                            log_info(f"Nom via {name_sel}: {name}", True)
                                        break
                            except:
                                continue
                    
                    if not name:
                        if debug:
                            log_info(f"Pas de nom trouvé pour business {idx}", True)
                        continue
                    
                    # Vérification absence site web (critère principal)
                    website_indicators = [
                        'a[aria-label*="Site Web"]',
                        'a[aria-label*="Website"]',
                        'a[data-value*="Website"]',
                        'a[href^="http"]:not([href*="google"]):not([href*="maps"])'
                    ]
                    
                    has_website = False
                    for indicator in website_indicators:
                        try:
                            if business.query_selector(indicator):
                                has_website = True
                                if debug:
                                    log_info(f"Site web détecté avec: {indicator}", True)
                                break
                        except:
                            continue
                    
                    if has_website:
                        if debug:
                            log_info(f"❌ Ignoré {name}: site web détecté", True)
                        continue
                    
                    # Extraction adresse depuis le texte
                    lines = business_text.split('\n')
                    address = ""
                    
                    for line in lines:
                        line = line.strip()
                        
                        # Détecter adresse (contient code postal ou mots clés)
                        if (re.search(r'\d{5}', line) or 
                            any(word in line.lower() for word in ['rue', 'avenue', 'boulevard', 'place', 'allée'])):
                            if not address or len(line) > len(address):
                                address = line
                                if debug:
                                    log_info(f"Adresse trouvée: {address}", True)
                    
                    # Construction données brutes avec texte complet
                    raw_data = {
                        'name': name,
                        'activity': query,
                        'business_text': business_text,  # CRITIQUE pour extraction téléphone
                        'address': address,
                        'index': idx,
                        'offset': offset
                    }
                    
                    # Normalisation selon schéma unifié
                    normalized = normalize_data(raw_data, query, session_id, debug)
                    
                    # Validation données minimales
                    if normalized.get('name') and (normalized.get('phone') or normalized.get('address')):
                        results.append(normalized)
                        extracted_count += 1
                        if debug:
                            phone_status = "📞" if normalized.get('phone') else "📍"
                            log_info(f"✅ Extrait {extracted_count}/{limit}: {phone_status} {normalized['name'][:50]}", True)
                    else:
                        if debug:
                            log_info(f"❌ Données insuffisantes pour {name}", True)
                    
                except Exception as e:
                    log_error(f"Erreur extraction business {idx}: {e}")
                    if debug:
                        import traceback
                        log_error(traceback.format_exc())
                    continue
            
            log_info(f"\n=== EXTRACTION TERMINÉE ===", debug)
            log_info(f"Résultats: {len(results)} extraits (sur {len(businesses)} trouvés, offset: {offset})", debug)
            
        except Exception as e:
            log_error(f"Erreur fatale scraping Maps: {e}")
            if debug:
                import traceback
                log_error(traceback.format_exc())
        finally:
            try:
                browser.close()
            except:
                pass
    
    return results

def main():
    """Point d'entrée principal"""
    parser = argparse.ArgumentParser(description='Google Maps Scraper v2.0 avec extraction téléphone corrigée')
    parser.add_argument('query', help='Activité à rechercher (ex: "plombier")')
    parser.add_argument('--city', default='', help='Ville de recherche (ex: "Nantes")')
    parser.add_argument('--limit', type=int, default=50, help='Limite de résultats (défaut: 50)')
    parser.add_argument('--offset', type=int, default=0, help='Nombre de résultats à ignorer (défaut: 0)')
    parser.add_argument('--session-id', default=None, help='ID de session pour tracking')
    parser.add_argument('--debug', action='store_true', help='Mode debug avec logs détaillés')
    
    args = parser.parse_args()
    
    # Validation des arguments
    if not args.query.strip():
        log_error("Query ne peut pas être vide")
        sys.exit(1)
    
    if args.limit <= 0 or args.limit > 100:
        log_error("Limit doit être entre 1 et 100")
        sys.exit(1)
    
    if args.offset < 0 or args.offset > 100:
        log_error("Offset doit être entre 0 et 100")
        sys.exit(1)
    
    # Lancement du scraping
    try:
        start_time = time.time()
        results = scrape_maps(args.query, args.city, args.limit, args.offset, 
                             getattr(args, 'session_id'), args.debug)
        duration = time.time() - start_time
        
        # Logs de résumé
        if args.debug:
            log_info(f"\n=== RÉSUMÉ FINAL ===", True)
            log_info(f"Durée totale: {duration:.2f}s", True)
            log_info(f"Résultats obtenus: {len(results)}", True)
            
            if results:
                # Stats par type de téléphone
                mobile_count = sum(1 for r in results if r.get('mobile_detected'))
                phone_count = sum(1 for r in results if r.get('phone'))
                log_info(f"Téléphones: {phone_count} total, {mobile_count} mobiles", True)
                
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
        if args.debug:
            import traceback
            log_error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()
