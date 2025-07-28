#!/usr/bin/env python3
"""
Google Maps Scraper v3.0 - Extraction multiple corrigée
Usage: python maps_scraper.py "plombier" --city "Nantes" --limit 5 --offset 10
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
    
    # Fallback : dernier élément avant France
    parts = address.split(',')
    for i in range(len(parts) - 1, -1, -1):
        part = parts[i].strip()
        if part and part != 'France' and not part.isdigit():
            return part
    
    return address.split(',')[0].strip()

def normalize_data(raw_data, query, debug=False):
    """Normalise les données selon le schéma unifié Naosite"""
    
    # Normalisation téléphone
    phone = normalize_phone(raw_data.get('phone', ''))
    
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
        
        # Métadonnées pour debug
        "raw_data": raw_data if debug else None
    }
    
    # Nettoyer les None si pas debug
    if not debug:
        result = {k: v for k, v in result.items() if v is not None}
    
    return result

def scrape_maps(query, city="", limit=50, offset=0, debug=False):
    """
    Scraper Google Maps avec anti-détection et offset
    
    Args:
        offset: Nombre de résultats à ignorer au début (pour éviter de prendre toujours les mêmes)
    """
    results = []
    
    log_info(f"=== DÉMARRAGE SCRAPING MAPS ===", debug)
    log_info(f"Query: '{query}', City: '{city}', Limit: {limit}, Offset: {offset}", debug)
    
    with sync_playwright() as p:
        browser_args = [
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-blink-features=AutomationControlled',
            '--disable-extensions',
            '--no-first-run',
            '--disable-default-apps'
        ]

        # Configuration du proxy
        browser_kwargs = {
            'headless': True,
            'args': browser_args
        }
        
        if PROXY_USER and PROXY_PASS:
            browser_kwargs['proxy'] = {
                "server": PROXY_SERVER,
                "username": PROXY_USER,
                "password": PROXY_PASS
            }
            log_info(f"Proxy configuré: {PROXY_USER}@{PROXY_SERVER}", debug)
        else:
            log_info("Pas de proxy configuré", debug)

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
            page.goto(maps_url, wait_until='networkidle', timeout=30000)
            
            # Attente chargement initial
            time.sleep(random.uniform(3, 5))
            
            # Accepter cookies si présent
            try:
                accept_buttons = page.query_selector_all('button')
                for btn in accept_buttons:
                    text = btn.inner_text().lower()
                    if 'accepter' in text or 'accept' in text:
                        btn.click()
                        time.sleep(1)
                        log_info("Cookies acceptés", debug)
                        break
            except:
                pass
            
            # Attendre que les résultats soient visibles
            try:
                page.wait_for_selector('[role="main"]', timeout=5000)
                log_info("Zone de résultats trouvée", debug)
            except:
                log_error("Zone de résultats non trouvée")
            
            # Prendre une capture d'écran pour debug si nécessaire
            if debug:
                page.screenshot(path="maps_debug.png")
                log_info("Screenshot sauvegardé: maps_debug.png", debug)
            
            # Scroll pour charger plus de résultats
            total_needed = limit + offset
            scroll_count = 0
            last_count = 0
            no_change_count = 0
            max_scrolls = min(20, (total_needed // 3) + 5)
            
            log_info(f"Début scrolling pour charger {total_needed} résultats", debug)
            
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
                # Essayer de récupérer le HTML pour debug
                if debug:
                    html_snippet = page.evaluate('document.querySelector("[role=\\"main\\"]")?.innerHTML?.substring(0, 500)')
                    log_error(f"HTML snippet: {html_snippet}")
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
                    # Récupérer tout le texte du business pour debug
                    business_text = business.inner_text()
                    log_info(f"\n--- Business {idx} ---", debug)
                    log_info(f"Texte complet: {business_text[:200]}...", debug)
                    
                    # Extraction nom - méthode améliorée
                    name = ""
                    
                    # Méthode 1: Via aria-label des liens
                    try:
                        link = business.query_selector('a[aria-label]')
                        if link:
                            name = link.get_attribute('aria-label') or ''
                            log_info(f"Nom via aria-label: {name}", debug)
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
                                        log_info(f"Nom via {name_sel}: {name}", debug)
                                        break
                            except:
                                continue
                    
                    if not name:
                        log_info(f"Pas de nom trouvé pour business {idx}", debug)
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
                                log_info(f"Site web détecté avec: {indicator}", debug)
                                break
                        except:
                            continue
                    
                    if has_website:
                        log_info(f"❌ Ignoré {name}: site web détecté", debug)
                        continue
                    
                    # Extraction des infos depuis le texte complet
                    lines = business_text.split('\n')
                    phone = ""
                    address = ""
                    
                    for line in lines:
                        line = line.strip()
                        
                        # Détecter téléphone
                        if re.search(r'(?:\+33|0)\s?[1-9](?:[\s\-\.]?\d{2}){4}', line):
                            phone = line
                            log_info(f"Téléphone trouvé: {phone}", debug)
                        
                        # Détecter adresse (contient code postal ou mots clés)
                        elif (re.search(r'\d{5}', line) or 
                              any(word in line.lower() for word in ['rue', 'avenue', 'boulevard', 'place'])):
                            if not address or len(line) > len(address):
                                address = line
                                log_info(f"Adresse trouvée: {address}", debug)
                    
                    # Construction données brutes
                    raw_data = {
                        'name': name,
                        'activity': query,
                        'phone': phone,
                        'address': address,
                        'index': idx,
                        'offset': offset
                    }
                    
                    # Normalisation selon schéma unifié
                    normalized = normalize_data(raw_data, query, debug)
                    
                    # Validation données minimales
                    if normalized.get('name') and (normalized.get('phone') or normalized.get('address')):
                        results.append(normalized)
                        extracted_count += 1
                        log_info(f"✅ Extrait {extracted_count}/{limit}: {normalized['name'][:50]}", debug)
                    else:
                        log_info(f"❌ Données insuffisantes pour {name}", debug)
                    
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
    parser = argparse.ArgumentParser(description='Google Maps Scraper v3.0 avec extraction multiple')
    parser.add_argument('query', help='Activité à rechercher (ex: "plombier")')
    parser.add_argument('--city', default='', help='Ville de recherche (ex: "Nantes")')
    parser.add_argument('--limit', type=int, default=50, help='Limite de résultats (défaut: 50)')
    parser.add_argument('--offset', type=int, default=0, help='Nombre de résultats à ignorer (défaut: 0)')
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
        results = scrape_maps(args.query, args.city, args.limit, args.offset, args.debug)
        duration = time.time() - start_time
        
        # Logs de résumé
        if args.debug:
            log_info(f"\n=== RÉSUMÉ FINAL ===", True)
            log_info(f"Durée totale: {duration:.2f}s", True)
            log_info(f"Résultats obtenus: {len(results)}", True)
            
            if results:
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
        if args.debug:
            import traceback
            log_error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()
