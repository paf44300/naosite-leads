#!/usr/bin/env python3
"""
PagesJaunes Scraper v2.0 - CORRIGÉ avec extraction téléphone anti-horaires
Usage: python pj_scraper.py "plombier" --city "Nantes" --limit 50 --session-id "abc123"
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
    print(f"[PJ_SCRAPER ERROR] {message}", file=sys.stderr)

def log_info(message, debug=False):
    """Log info vers stderr si debug activé"""
    if debug:
        print(f"[PJ_SCRAPER INFO] {message}", file=sys.stderr)

def extract_clean_phone_pj(phone_text, debug=False):
    """
    CORRECTION CRITIQUE : Extraction téléphone PJ anti-contamination horaires
    PJ format typique : 02.40.12.34.56 → +33240123456
    """
    if not phone_text:
        return None
    
    # Nettoyer d'abord les patterns d'horaires courants
    cleaned_text = phone_text.lower()
    
    # Supprimer les patterns d'horaires
    business_hours_patterns = [
        r'\b(?:open|closed|ouvert|fermé|hours|horaires)\b',
        r'\b(?:lun|mar|mer|jeu|ven|sam|dim)\w*',
        r'\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
        r'\b(?:2[0-4]|1[0-9])[h:]?\d{0,2}\b',  # 20h, 21:00, etc.
        r'\b(?:de|à|from|to|until|jusqu)\b',   # Connecteurs temporels
    ]
    
    for pattern in business_hours_patterns:
        cleaned_text = re.sub(pattern, ' ', cleaned_text, flags=re.IGNORECASE)
    
    # PJ utilise souvent des points : 02.40.12.34.56
    # Patterns PJ spécifiques
    pj_phone_patterns = [
        r'(\+33[1-9](?:[\.\s\-]?\d){8})',      # +33 avec points/espaces
        r'(0[1-9](?:[\.\s\-]?\d){8})',         # 0X avec points/espaces
        r'(\d{2}\.?\d{2}\.?\d{2}\.?\d{2}\.?\d{2})', # Format PJ avec points
    ]
    
    for pattern in pj_phone_patterns:
        match = re.search(pattern, cleaned_text)
        if match:
            raw_phone = match.group(1)
            
            # Validation : garder que les chiffres pour validation
            digits_only = re.sub(r'\D', '', raw_phone)
            
            if len(digits_only) >= 9 and len(digits_only) <= 11:
                # Vérifier que ce n'est pas un pattern d'horaire déguisé
                if not re.match(r'^[0-2]\d{8,10}$', digits_only) or digits_only.startswith('0'):
                    if debug:
                        log_info(f"Téléphone PJ trouvé: {raw_phone} → {digits_only}", True)
                    return normalize_phone_pj(digits_only)
    
    return None

def normalize_phone_pj(phone_digits):
    """Normalise téléphone PJ au format E.164"""
    if not phone_digits or len(phone_digits) < 9:
        return None
    
    # Normalisation française
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

def normalize_data(raw_data, query, session_id=None, debug=False):
    """Normalise données PJ selon schéma unifié Naosite"""
    
    # Téléphone PJ CORRIGÉ
    phone = extract_clean_phone_pj(raw_data.get('phone', ''), debug)
    
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
        
        # Métadonnées session
        "_session_id": session_id,
        "_scraper_source": "pj",
        
        # Debug
        "raw_data": raw_data if debug else None
    }
    
    # Nettoyer les None si pas debug
    if not debug:
        result = {k: v for k, v in result.items() if v is not None}
    
    return result

def scrape_pj(query, city="", limit=50, session_id=None, debug=False):
    """Scraper PagesJaunes avec focus emails CORRIGÉ"""
    results = []
    
    log_info(f"Démarrage scraping PJ v2.0: query='{query}', city='{city}', limit={limit}", debug)
    log_info(f"Session: {session_id}", debug)
    
    with sync_playwright() as p:
        # Configuration navigateur (identique maps_scraper)
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
            # URL PagesJaunes
            search_query = f"{query} {city}".strip()
            pj_url = f"https://www.pagesjaunes.fr/pagesblanches/recherche?quoi={quote_plus(query)}&ou={quote_plus(city)}"
            
            log_info(f"Accès URL PJ: {pj_url}", debug)
            
            page.goto(pj_url, wait_until='networkidle', timeout=30000)
            time.sleep(random.uniform(3, 5))
            
            # Gestion des cookies/RGPD si présent
            try:
                cookie_selectors = [
                    'button[id*="accept"]',
                    'button[id*="consent"]', 
                    '.didomi-continue-without-agreeing',
                    '#didomi-notice-agree-button'
                ]
                
                for cookie_sel in cookie_selectors:
                    try:
                        cookie_btn = page.query_selector(cookie_sel)
                        if cookie_btn:
                            cookie_btn.click()
                            time.sleep(1)
                            log_info("Cookies PJ acceptés", debug)
                            break
                    except:
                        continue
            except:
                pass
            
            # Navigation pages (PJ pagine souvent)
            page_count = 0
            max_pages = min(3, (limit // 15) + 1)  # ~15 résultats par page PJ
            
            while page_count < max_pages and len(results) < limit:
                log_info(f"Traitement page PJ {page_count + 1}/{max_pages}", debug)
                
                # Attente chargement page
                time.sleep(random.uniform(2, 4))
                
                # Sélecteurs PJ (adaptatifs selon évolution site)
                business_selectors = [
                    '.bi-bloc',
                    '.item-entreprise',
                    '[data-pj-localise]',
                    '.bi',
                    '.search-item'
                ]
                
                businesses = []
                for selector in business_selectors:
                    try:
                        businesses = page.query_selector_all(selector)
                        if businesses:
                            log_info(f"Trouvé {len(businesses)} entreprises PJ avec sélecteur {selector}", debug)
                            break
                    except:
                        continue
                
                if not businesses:
                    log_info("Aucune entreprise trouvée sur cette page PJ", debug)
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
                            '.teaser-website',
                            'a[title*="site"]'
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
                                        if debug:
                                            log_info(f"Site web détecté: {href}", True)
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
                            '.denomination',
                            '.bi-titre a'
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
                            '.contact-email',
                            '.email-link'
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
                        
                        # Extraction téléphone - RÉCUPÉRER LE TEXTE COMPLET
                        phone_selectors = [
                            '.bi-tel .number',
                            '.numero-telephone',
                            '[data-bi="tel"]',
                            '.phone-number',
                            '.bi-tel'
                        ]
                        
                        phone_text = ""
                        for phone_sel in phone_selectors:
                            try:
                                phone_el = business.query_selector(phone_sel)
                                if phone_el:
                                    phone_text = phone_el.inner_text().strip()
                                    if phone_text and any(c.isdigit() for c in phone_text):
                                        break
                            except:
                                continue
                        
                        # Extraction adresse
                        address_selectors = [
                            '.bi-adresse',
                            '.adresse',
                            '.localite',
                            '[data-bi="address"]',
                            '.bi-lieu'
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
                            'phone': phone_text,  # Texte complet pour extraction corrigée
                            'email': email,
                            'address': address,
                            'page': page_count + 1,
                            'index': idx
                        }
                        
                        # Normalisation CORRIGÉE
                        normalized = normalize_data(raw_data, query, session_id, debug)
                        
                        # Validation : au moins nom + (phone OU email)
                        if normalized['name'] and (normalized['phone'] or normalized['email']):
                            results.append(normalized)
                            phone_status = "📞" if normalized.get('phone') else ""
                            email_status = "📧" if normalized.get('email') else ""
                            name_short = normalized['name'][:40] + ('...' if len(normalized['name']) > 40 else '')
                            log_info(f"Extrait PJ {len(results)}/{limit}: {phone_status}{email_status} {name_short}", debug)
                        
                    except Exception as e:
                        log_error(f"Erreur extraction business PJ page {page_count + 1}, item {idx}: {e}")
                        continue
                
                # Passage page suivante
                if len(results) < limit and page_count + 1 < max_pages:
                    try:
                        next_selectors = [
                            '.pagination-next:not(.disabled)',
                            '.suivant:not(.disabled)',
                            'a[aria-label="Page suivante"]',
                            '.pager-next a',
                            '.pagination .next'
                        ]
                        
                        next_clicked = False
                        for next_sel in next_selectors:
                            try:
                                next_btn = page.query_selector(next_sel)
                                if next_btn:
                                    next_btn.click()
                                    time.sleep(random.uniform(2, 4))
                                    next_clicked = True
                                    log_info(f"Page suivante PJ cliquée ({next_sel})", debug)
                                    break
                            except:
                                continue
                        
                        if not next_clicked:
                            log_info("Pas de page suivante PJ trouvée", debug)
                            break
                            
                    except Exception as e:
                        log_error(f"Erreur navigation page suivante PJ: {e}")
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
    parser = argparse.ArgumentParser(description='PagesJaunes Scraper v2.0 avec extraction téléphone corrigée')
    parser.add_argument('query', help='Activité à rechercher (ex: "plombier")')
    parser.add_argument('--city', default='', help='Ville de recherche (ex: "Nantes")')
    parser.add_argument('--limit', type=int, default=50, help='Limite de résultats (défaut: 50)')
    parser.add_argument('--session-id', default=None, help='ID de session pour tracking')
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
        results = scrape_pj(args.query, args.city, args.limit, 
                           getattr(args, 'session_id'), args.debug)
        duration = time.time() - start_time
        
        # Stats si debug
        if args.debug:
            log_info(f"Scraping PJ terminé en {duration:.2f}s: {len(results)} résultats", True)
            
            # Stat emails (spécificité PJ)
            email_count = sum(1 for r in results if r.get('email'))
            phone_count = sum(1 for r in results if r.get('phone'))
            log_info(f"Emails récupérés: {email_count}/{len(results)} ({email_count/len(results)*100:.1f}%)" if results else "Aucun résultat", True)
            log_info(f"Téléphones récupérés: {phone_count}/{len(results)}", True)
            
            # Stats mobiles
            mobile_count = sum(1 for r in results if r.get('mobile_detected'))
            log_info(f"Téléphones mobiles: {mobile_count}/{phone_count}" if phone_count else "Pas de téléphones", True)
        
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
