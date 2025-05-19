#!/usr/bin/env python3
import json

def generate_club_slug(club_name):
    """Generate a URL slug from a club name."""
    # Strip "הולמס פלייס " prefix if it exists
    if club_name.startswith("הולמס פלייס "):
        name = club_name[len("הולמס פלייס "):]
    # Or strip "גו אקטיב " prefix if it exists
    elif club_name.startswith("גו אקטיב "):
        name = club_name[len("גו אקטיב "):]
    else:
        name = club_name
        
    # Handle special cases
    if "דיזנגוף" in name:
        return "dizengof"
    elif "עזריאלי" in name:
        return "azrieli"
    elif "מיקדו" in name or "צפון תל אביב" in name:
        return "mikado"
    elif "שבעת הכוכבים" in name:
        return "7-stars"
    elif "באר שבע" in name:
        return "beer-sheva"
    elif "ראשון לציון" in name and "פרימיום" in name:
        return "rishon-premium" 
    elif "ראשון לציון" in name:
        return "rishon"
    elif "פתח תקווה" in name:
        return "petah-tikva"
    elif "קריית אונו" in name:
        return "kiryat-ono"
    elif "רמת גן" in name:
        return "ramat-gan"
    elif "הרצליה" in name:
        return "herzliya"
    elif "מבשרת ציון" in name or "מבשרת" in name:
        return "mevasseret"
    elif "גבעת שמואל" in name:
        return "givat-shmuel"
    elif "אשדוד" in name:
        return "ashdod"
    elif "ראש העין" in name:
        return "rosh-haayin"
    elif "נתניה" in name:
        return "netanya"
    elif "פמלי חדרה" in name or "חדרה" in name:
        return "hadera"
    elif "חיפה" in name and "פמילי" in name:
        return "haifa-family"
    elif "קניון חיפה" in name:
        return "haifa-mall"
    elif "קריון" in name:
        return "kryon"
    
    # For others, convert Hebrew to simple English
    slug_map = {
        "רעננה": "raanana",
        "גבעתיים": "givatayim",
        "כפר סבא": "kfar-saba",
        "רחובות": "rehovot",
        "מודיעין": "modiin",
        "קיסריה": "caesarea",
        "נס ציונה": "nes-tziona",
        "לוד": "lod"
    }
    
    for heb, eng in slug_map.items():
        if heb in name:
            return eng
            
    # Fallback - use first word converted to lowercase English
    return "club"

def main():
    # Sample club names to test
    club_names = [
        "הולמס פלייס דיזנגוף",
        "הולמס פלייס עזריאלי",
        "הולמס פלייס מיקדו צפון תל אביב",
        "הולמס פלייס שבעת הכוכבים",
        "הולמס פלייס באר שבע",
        "הולמס פלייס פרימיום ראשון לציון",
        "הולמס פלייס פתח תקווה",
        "גו אקטיב קריית אונו",
        "הולמס פלייס רמת גן",
        "הולמס פלייס הרצליה",
        "הולמס פלייס מבשרת ציון",
        "הולמס פלייס גבעת שמואל",
        "הולמס פלייס פמלי אשדוד",
        "הולמס פלייס ראש העין",
        "הולמס פלייס נתניה",
        "הולמס פלייס פמלי חדרה",
        "הולמס פלייס פמילי חיפה",
        "הולמס פלייס קניון חיפה",
        "הולמס פלייס קריון",
        "הולמס פלייס רעננה",
        "הולמס פלייס גבעתיים",
        "הולמס פלייס כפר סבא",
        "הולמס פלייס רחובות",
        "הולמס פלייס מודיעין",
        "הולמס פלייס קיסריה",
        "גו אקטיב נס ציונה",
        "הולמס פלייס לוד - אביבים"
    ]
    
    results = {}
    for club_name in club_names:
        slug = generate_club_slug(club_name)
        url = f"https://www.holmesplace.co.il/club-page-{slug}/"
        results[club_name] = {
            "slug": slug,
            "url": url
        }
    
    print(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"\nGenerated {len(results)} URLs")

if __name__ == "__main__":
    main() 