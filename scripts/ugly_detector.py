#!/usr/bin/env python3
"""
Ugly Website Detector pour Naosite
Analyse automatique de la qualité des sites web
"""

import requests
import json
import sys
from urllib.parse import urlparse
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

def analyze_website_quality(url):
    """Analyse complète qualité site web"""
    score = 100
    ugly_factors = []
    
    try:
        # Test vitesse chargement
        start_time = time.time()
        response = requests.get(url, timeout=10)
        load_time = time.time() - start_time
        
        if load_time > 5:
            score -= 40
            ugly_factors.append("Très lent (>5s)")
        elif load_time > 3:
            score -= 25
            ugly_factors.append("Lent (>3s)")
        
        # Test HTTPS
        if not url.startswith('https://'):
            score -= 30
            ugly_factors.append("Pas de HTTPS")
        
        # Analyse contenu HTML
        html = response.text.lower()
        
        # Technologies obsolètes
        if 'flash' in html or '.swf' in html:
            score -= 50
            ugly_factors.append("Flash obsolète")
            
        if '<iframe' in html and 'width="100%"' not in html:
            score -= 30
            ugly_factors.append("Frames old-school")
        
        # Design indicators
        if 'comic sans' in html or 'papyrus' in html:
            score -= 35
            ugly_factors.append("Police horrible")
            
        if 'background-image' in html and 'repeat' in html:
            score -= 25
            ugly_factors.append("Background à motifs")
        
        if 'autoplay' in html or 'bgsound' in html:
            score -= 40
            ugly_factors.append("Son automatique")
        
        # Mobile responsive
        if 'viewport' not in html:
            score -= 30
            ugly_factors.append("Pas responsive")
        
        # Popup spam
        if html.count('popup') > 3 or html.count('alert(') > 0:
            score -= 20
            ugly_factors.append("Popups intrusifs")
        
        # Contenu minimal
        if len(html) < 2000:
            score -= 20
            ugly_factors.append("Contenu insuffisant")
        
        # Contact info
        if 'contact' not in html and 'telephone' not in html and '@' not in html:
            score -= 25
            ugly_factors.append("Pas d'infos contact")
            
    except Exception as e:
        score = 30
        ugly_factors = ["Site inaccessible ou cassé"]
    
    return {
        'quality_score': max(0, score),
        'ugly_factors': ugly_factors,
        'load_time': load_time if 'load_time' in locals() else 999
    }

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "URL required"}))
        sys.exit(1)
    
    url = sys.argv[1]
    result = analyze_website_quality(url)
    print(json.dumps(result, ensure_ascii=False))
