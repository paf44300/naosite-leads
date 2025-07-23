#!/usr/bin/env python3
"""
PagesJaunes Scraper v1.5 - Focus emails + harmonisation
Usage: python pj_scraper.py "plombier" --city "Nantes" --limit 50
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
PROXY_HOST = os.getenv("proxy.webshare.io")
PROXY_PORT = os.getenv("80")
PROXY_USER = os.getenv("xftpfnvt")
PROXY_PASS = os.getenv("yulnmnbiq66j")

def log_error(message):
    """Log erreur vers stderr pour n8n monitoring"""
    print(f"[PJ_SCRAPER ERROR] {message}", file=sys.stderr)

def log_info(message, debug=False):
    """Log info vers stderr si debug activé"""
    if debug:
        print(f"[PJ_SCRAPER INFO] {message}", file=sys.stderr)

def normalize_activity(activity):
    """Standardise les activités (fonction identique maps_scraper)"""
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
        
    # Autres métiers
    if any(word in activity for word in ['couvreur', 'toiture']):
        return 'Couvreur'
    if any(word in activity for word in ['menuisier', 'menuiserie', 'bois']):
        return 'Menuisier'
    if any(word in activity for word in ['peintre', 'peinture']):
        return 'Peintre'
    if any(word in activity for word in ['carreleur', 'carrelage']):
        return 'Carreleur'
    if any(word in activity for word in ['serrurier', 'serrurerie']):
        return 'Serrurier'
    
    return activity.title()

def normalize_phone(phone_raw):
    """Normalise téléphone PJ (format: 02.40.12.34.56 → +33240123456)"""
    if not phone_raw:
        return None
    
    # PJ utilise souvent des points : 02.40.12.34.56
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

def validate_email(email_raw):
    """Valide et nettoie un email"""
    if not email_raw:
        return None
    
    email = str(email_raw).strip().lower()
    
    # Remove mailto: prefix si présent
    if email.startswith('mailto:'):
        email = email[7:]
    
    # Validation regex basique
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if re.match(email_pattern, email):
        return email
    
    return None

def extract_city_pj(address):
    """Extraction ville format PagesJaunes"""
    if not address:
        return ""
    
    # Patterns PJ spécifiques
    patterns = [
        r'(\d{5})\s+([A-Z][a-zÀ-ÿ\s\-\']+)',      # 44000 Nantes
        r'([A-Z][a-zÀ-ÿ\s\-\']+)\s+\((\d{5})\)',  # Nantes (44000)
        r'([A-Z][a-zÀ-ÿ\s\-\']+),?\s+\d{5}',      # Nantes, 44000
        r'^([A-Z][a-zÀ-ÿ\s\-\']+)',               # Première ville mentionnée
    ]
    
    for pattern in patterns:
        match = re.search(pattern, address)
        if match:
            if len(match.groups()) >= 2:
                # Si pattern avec code postal, prendre le nom de ville
                return match.group(2).strip() if match.group(1).isdigit() else match.group(1).strip()
            else:
                return match.group(1).strip()
    
    # Fallback : premier mot capitalisé
    words = address.split(',')
    for word in words:
        word = word.strip()
        if word and len(word) > 2 and word[0].isupper():
            return word
    
    return address.split(',')[0].strip() if ',' in address else address.strip()

def normalize_data(raw_data, query, debug=False):
    """Normalise données PJ selon schéma unifié Naosite"""
    
    # Téléphone PJ
    phone = normalize_phone(raw_data.get('phone', ''))
    
    # Email PJ (spécificité importante)
    email = validate_email(raw_data.get('email', ''))
    
    # Extraction ville PJ
    address = raw_data.get('address', '') or ''
    city = extract_city_pj(address)
    
    # Nom entreprise
    name = (raw_data.get('name', '') or '').strip()
    if len(name) > 150:
        name = name[:150] + '...'
    
    # Activité standardisée
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
        "email": email,  # Spécificité PJ : emails souvent disponibles
        "address": address,
        "city": city,
        "website": None,  # Toujours null (critère filtrage)
        "source": "pages_jaunes",
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

def scrape_pj(query, city="", limit=50, debug=False):
    """Scraper PagesJaunes avec focus emails"""
    results = []
    
    log_info(f"Démarrage scraping PJ: query='{query}', city='{city}', limit={limit}", debug)
    
    with sync_playwright() as p:
        # Configuration navigateur (identique maps_scraper)
        browser_args = [
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-blink-features=AutomationControlled',
            '--disable-extensions'
        ]
        
        browser_kwargs = {'headless': True, 'args': browser_args}
        
        # Proxy si disponible
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
        
        context = browser.new_context(
            viewport={'width': 1366, 'height': 768},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        page = context.new_page()
        
        try:
            # URL PagesJaunes
            search_query = f"{query} {city}".strip()
            pj_url = f"https://www.pagesjaunes.fr/pagesblanches/recherche?quoi={quote_plus(query)}&ou={quote_plus(city)}"
            
            log_info(f"Accès URL PJ: {pj_url}", debug)
            
            page.goto(pj_url, wait_until='networkidle', timeout=30000)
            time.sleep(random.uniform(3, 5))
            
            # Gestion des cookies/RGPD si présent
            try:
                cookie_accept = page.query_selector('button[id*="accept"], button[id*="consent"], .didomi-continue-without-agreeing')
                if cookie_accept:
                    cookie_accept.click()
                    time.sleep(1)
                    log_info("Cookies acceptés", debug)
            except:
                pass
            
            # Navigation pages (PJ pagine souvent)
            page_count = 0
            max_pages = min(3, (limit // 20) + 1)  # ~20 résultats par page PJ
            
            while page_count < max_pages and len(results) < limit:
                log_info(f"Traitement page {page_count + 1}/{max_pages}", debug)
                
                # Attente chargement page
                time.sleep(random.uniform(2, 4))
                
                # Sélecteurs PJ (adaptatifs selon évolution site)
                business_selectors = [
                    '.bi-bloc',
                    '.item-entreprise',
                    '[data-pj-localise]',
                    '.bi'
                ]
                
                businesses = []
                for selector in business_selectors:
                    try:
                        businesses = page.query_selector_all(selector)
                        if businesses:
                            log_info(f"Trouvé {len(businesses)} entreprises avec sélecteur {selector}", debug)
                            break
                    except:
                        continue
                
                if not businesses:
                    log_info("Aucune entreprise trouvée sur cette page", debug)
                    break
                
                # Extraction données de la page courante
                for idx, business in enumerate(businesses):
                    if len(results) >= limit:
                        break
                    
                    try:
                        # Vérifier absence site web EN PREMIER (critère principal)
                        website_selectors = [
                            'a[href^="http"]:not([href*="pagesjaunes"]):not([href*="mappy"])',
                            '.bi-website a',
                            '[data-bi="website"]',
                            '.teaser-website'
                        ]
                        
                        has_website = False
                        for ws_sel in website_selectors:
                            try:
                                website_el = business.query_selector(ws_sel)
                                if website_el:
                                    href = website_el.get_attribute('href') or ''
                                    # Ignorer les liens internes PJ
                                    if href and not any(internal in href for internal in ['pagesjaunes', 'mappy', 'javascript:']):
                                        has_website = True
                                        break
                            except:
                                continue
                        
                        if has_website:
                            continue  # Skip si site web détecté
                        
                        # Extraction nom
                        name_selectors = [
                            '.bi-denomination a',
                            '.raison-sociale',
                            '.bi-nom',
                            'h3 a',
                            '.denomination'
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
                        
                        # Extraction EMAIL (priorité PJ)
                        email_selectors = [
                            'a[href^="mailto:"]',
                            '.bi-email a',
                            '[data-bi="email"]',
                            '.contact-email'
                        ]
                        
                        email = ""
                        for email_sel in email_selectors:
                            try:
                                email_el = business.query_selector(email_sel)
                                if email_el:
                                    href = email_el.get_attribute('href') or ''
                                    if href.startswith('mailto:'):
                                        email = href[7:]  # Remove mailto:
                                    else:
                                        email = email_el.inner_text().strip()
                                    
                                    if email and '@' in email:
                                        break
                            except:
                                continue
                        
                        # Extraction téléphone
                        phone_selectors = [
                            '.bi-tel .number',
                            '.numero-telephone',
                            '[data-bi="tel"]',
                            '.phone-number'
                        ]
                        
                        phone = ""
                        for phone_sel in phone_selectors:
                            try:
                                phone_el = business.query_selector(phone_sel)
                                if phone_el:
                                    phone = phone_el.inner_text().strip()
                                    if phone and any(c.isdigit() for c in phone):
                                        break
                            except:
                                continue
                        
                        # Extraction adresse
                        address_selectors = [
                            '.bi-adresse',
                            '.adresse',
                            '.localite',
                            '[data-bi="address"]'
                        ]
                        
                        address = ""
                        for addr_sel in address_selectors:
                            try:
                                addr_el = business.query_selector(addr_sel)
                                if addr_el:
                                    address = addr_el.inner_text().strip()
                                    if address and len(address) > 5:
                                        break
                            except:
                                continue
                        
                        # Données brutes
                        raw_data = {
                            'name': name,
                            'activity': query,
                            'phone': phone,
                            'email': email,
                            'address': address,
                            'page': page_count + 1,
                            'index': idx
                        }
                        
                        # Normalisation
                        normalized = normalize_data(raw_data, query, debug)
                        
                        # Validation : au moins nom + (phone OU email)
                        if normalized['name'] and (normalized['phone'] or normalized['email']):
                            results.append(normalized)
                            log_info(f"Extrait {len(results)}/{limit}: {normalized['name']} (email: {'✓' if normalized['email'] else '✗'})", debug)
                        
                    except Exception as e:
                        log_error(f"Erreur extraction business page {page_count + 1}, item {idx}: {e}")
                        continue
                
                # Passage page suivante
                if len(results) < limit and page_count + 1 < max_pages:
                    try:
                        next_selectors = [
                            '.pagination-next:not(.disabled)',
                            '.suivant:not(.disabled)',
                            'a[aria-label="Page suivante"]',
                            '.pager-next a'
                        ]
                        
                        next_clicked = False
                        for next_sel in next_selectors:
                            try:
                                next_btn = page.query_selector(next_sel)
                                if next_btn:
                                    next_btn.click()
                                    time.sleep(random.uniform(2, 4))
                                    next_clicked = True
                                    log_info(f"Page suivante cliquée ({next_sel})", debug)
                                    break
                            except:
                                continue
                        
                        if not next_clicked:
                            log_info("Pas de page suivante trouvée", debug)
                            break
                            
                    except Exception as e:
                        log_error(f"Erreur navigation page suivante: {e}")
                        break
                
                page_count += 1
            
            log_info(f"Scraping PJ terminé: {len(results)} résultats sur {page_count} pages", debug)
            
        except Exception as e:
            log_error(f"Erreur scraping PJ: {e}")
        finally:
            try:
                browser.close()
            except:
                pass
    
    return results

def main():
    """Point d'entrée principal"""
    parser = argparse.ArgumentParser(description='PagesJaunes Scraper v1.5 avec focus emails')
    parser.add_argument('query', help='Activité à rechercher (ex: "plombier")')
    parser.add_argument('--city', default='', help='Ville de recherche (ex: "Nantes")')
    parser.add_argument('--limit', type=int, default=50, help='Limite de résultats (défaut: 50)')
    parser.add_argument('--debug', action='store_true', help='Mode debug avec logs détaillés')
    
    args = parser.parse_args()
    
    # Validation
    if not args.query.strip():
        log_error("Query ne peut pas être vide")
        sys.exit(1)
    
    if args.limit <= 0 or args.limit > 1000:
        log_error("Limit doit être entre 1 et 1000")
        sys.exit(1)
    
    # Scraping
    try:
        start_time = time.time()
        results = scrape_pj(args.query, args.city, args.limit, args.debug)
        duration = time.time() - start_time
        
        # Stats si debug
        if args.debug:
            log_info(f"Scraping PJ terminé en {duration:.2f}s: {len(results)} résultats", True)
            
            # Stat emails (spécificité PJ)
            email_count = sum(1 for r in results if r.get('email'))
            log_info(f"Emails récupérés: {email_count}/{len(results)} ({email_count/len(results)*100:.1f}%)" if results else "Aucun résultat", True)
            
            # Stats mobiles
            mobile_count = sum(1 for r in results if r.get('mobile_detected'))
            log_info(f"Téléphones mobiles: {mobile_count}/{len(results)}", True)
        
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
