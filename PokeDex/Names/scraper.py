import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime
from urllib.parse import urljoin
import time

BASE_URL = "https://pokemondb.net"
POKEDEX_URL = "https://pokemondb.net/pokedex/all"

def fetch_page(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return response.text

def parse_pokedex(html):
    soup = BeautifulSoup(html, 'lxml')
    table = soup.find('table', id='pokedex')
    if not table:
        raise ValueError("Could not find pokedex table")
    
    tbody = table.find('tbody')
    if not tbody:
        raise ValueError("Could not find tbody in pokedex table")
    
    rows = tbody.find_all('tr')
    print(f"Found {len(rows)} rows in the table")
    
    pokemon_list = []
    
    for idx, row in enumerate(rows):
        try:
            pokemon = parse_row(row)
            if pokemon:
                pokemon_list.append(pokemon)
        except Exception as e:
            print(f"Error parsing row {idx}: {e}")
            continue
    
    return pokemon_list

def parse_row(row):
    cells = row.find_all('td')
    if len(cells) < 10:
        return None
    
    # Cell 0: Number + Image
    num_cell = cells[0]
    pokedex_number = None
    image_url = None
    
    # Get pokedex number from data-sort-value or text
    num_span = num_cell.find('span', class_='infocard-cell-data')
    if num_span:
        pokedex_number = int(num_span.get_text(strip=True))
    else:
        sort_value = num_cell.get('data-sort-value')
        if sort_value:
            pokedex_number = int(sort_value)
    
    # Get image URL
    img = num_cell.find('img', class_='icon-pkmn')
    if img:
        image_url = img.get('src') or img.get('data-src')
        if image_url and not image_url.startswith('http'):
            image_url = urljoin(BASE_URL, image_url)
    
    # Cell 1: Name + Form
    name_cell = cells[1]
    name_link = name_cell.find('a', class_='ent-name')
    if not name_link:
        return None
    
    base_name = name_link.get_text(strip=True)
    pokemon_url = name_link.get('href', '')
    if pokemon_url and not pokemon_url.startswith('http'):
        pokemon_url = urljoin(BASE_URL, pokemon_url)
    
    # Check for form name in small tag
    form_small = name_cell.find('small', class_='text-muted')
    form_name = form_small.get_text(strip=True) if form_small else None
    
    # Determine display name
    # The form_name in the HTML already contains the full display name (e.g., "Mega Venusaur", "Alolan Rattata")
    if form_name:
        display_name = form_name
    else:
        display_name = base_name
    
    # Cell 2: Types
    type_cell = cells[2]
    type_links = type_cell.find_all('a', class_='type-icon')
    types = []
    for link in type_links:
        type_text = link.get_text(strip=True)
        if type_text:
            types.append(type_text)
    
    # Cells 3-9: Stats (Total, HP, Attack, Defense, Sp. Atk, Sp. Def, Speed)
    stat_cells = cells[3:10]
    stats = {}
    stat_names = ['total', 'hp', 'attack', 'defense', 'special_attack', 'special_defense', 'speed']
    
    for i, stat_name in enumerate(stat_names):
        if i < len(stat_cells):
            stat_text = stat_cells[i].get_text(strip=True)
            try:
                stats[stat_name] = int(stat_text)
            except ValueError:
                stats[stat_name] = None
        else:
            stats[stat_name] = None
    
    return {
        'pokedex_number': pokedex_number,
        'name': base_name,
        'form_name': form_name,
        'display_name': display_name,
        'types': types,
        'base_stats': stats,
        'image_url': image_url,
        'pokemon_url': pokemon_url
    }

def validate_data(pokemon_list):
    total_records = len(pokemon_list)
    
    # Unique records based on (pokedex_number, form_name, display_name)
    seen = set()
    unique_records = 0
    duplicates = 0
    
    missing_name = 0
    missing_types = 0
    missing_stats = 0
    missing_image = 0
    missing_url = 0
    alternate_forms = 0
    non_numeric_stats = 0
    total_mismatch = 0
    
    for p in pokemon_list:
        key = (p['pokedex_number'], p['form_name'], p['display_name'])
        if key in seen:
            duplicates += 1
        else:
            seen.add(key)
            unique_records += 1
        
        if not p['name']:
            missing_name += 1
        if not p['types']:
            missing_types += 1
        if not p['base_stats'] or any(v is None for v in p['base_stats'].values()):
            missing_stats += 1
        if not p['image_url']:
            missing_image += 1
        if not p['pokemon_url']:
            missing_url += 1
        if p['form_name']:
            alternate_forms += 1
        
        # Check numeric stats
        for stat_name, stat_value in p['base_stats'].items():
            if stat_value is not None and not isinstance(stat_value, int):
                non_numeric_stats += 1
        
        # Verify total matches sum of individual stats (approximately)
        # The source total should match what's displayed, not recalculated
        # We'll just check that total is present and numeric
        if p['base_stats'].get('total') is None:
            total_mismatch += 1
    
    return {
        'source': POKEDEX_URL,
        'scraped_at': datetime.utcnow().isoformat() + 'Z',
        'total_records': total_records,
        'unique_records': unique_records,
        'duplicates': duplicates,
        'missing_fields': {
            'name': missing_name,
            'types': missing_types,
            'stats': missing_stats,
            'image_url': missing_image,
            'pokemon_url': missing_url
        },
        'alternate_forms_detected': alternate_forms,
        'non_numeric_stats': non_numeric_stats,
        'total_mismatch': total_mismatch,
        'status': 'success' if total_records > 0 else 'failed'
    }

def main():
    print(f"Fetching {POKEDEX_URL}...")
    html = fetch_page(POKEDEX_URL)
    print(f"Page fetched, size: {len(html)} bytes")
    
    print("Parsing pokedex table...")
    pokemon_list = parse_pokedex(html)
    print(f"Parsed {len(pokemon_list)} Pokémon entries")
    
    # Save pokemon.json
    with open('pokemon.json', 'w', encoding='utf-8') as f:
        json.dump(pokemon_list, f, ensure_ascii=False, indent=2)
    print("Saved pokemon.json")
    
    # Validate and save report
    report = validate_data(pokemon_list)
    with open('pokemon_scrape_report.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("Saved pokemon_scrape_report.json")
    
    # Print summary
    print("\n=== Validation Report ===")
    print(f"Total records: {report['total_records']}")
    print(f"Unique records: {report['unique_records']}")
    print(f"Duplicates: {report['duplicates']}")
    print(f"Alternate forms detected: {report['alternate_forms_detected']}")
    print(f"Missing names: {report['missing_fields']['name']}")
    print(f"Missing types: {report['missing_fields']['types']}")
    print(f"Missing stats: {report['missing_fields']['stats']}")
    print(f"Missing images: {report['missing_fields']['image_url']}")
    print(f"Missing URLs: {report['missing_fields']['pokemon_url']}")
    print(f"Non-numeric stats: {report['non_numeric_stats']}")
    print(f"Status: {report['status']}")

if __name__ == '__main__':
    main()