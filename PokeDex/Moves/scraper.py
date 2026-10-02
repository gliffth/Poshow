import json
import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def scrape_moves():
    url = "https://pokemondb.net/move/all"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    response.encoding = 'utf-8'
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    table = soup.find('table', id='moves')
    if not table:
        raise ValueError("Could not find moves table")
    
    tbody = table.find('tbody')
    if not tbody:
        raise ValueError("Could not find tbody in moves table")
    
    rows = tbody.find_all('tr')
    
    moves = []
    seen_names = set()
    
    for row in rows:
        cells = row.find_all('td')
        if len(cells) < 8:
            continue
        
        # Cell 0: Name + URL
        name_cell = cells[0]
        name_link = name_cell.find('a', class_='ent-name')
        if not name_link:
            continue
        
        name = name_link.get_text(strip=True)
        move_url = urljoin(url, name_link.get('href', ''))
        
        # Skip duplicates
        if name in seen_names:
            continue
        seen_names.add(name)
        
        # Cell 1: Type
        type_cell = cells[1]
        type_link = type_cell.find('a', class_='type-icon')
        move_type = type_link.get_text(strip=True) if type_link else None
        
        # Cell 2: Category
        category_cell = cells[2]
        category_img = category_cell.find('img')
        category = None
        if category_img:
            alt = category_img.get('alt', '')
            if alt in ['Physical', 'Special', 'Status']:
                category = alt
            # Also check data attributes as backup
            if not category:
                sort_val = category_cell.get('data-sort-value', '')
                if sort_val in ['physical', 'special', 'status']:
                    category = sort_val.capitalize()
        
        # Cell 3: Power
        power_cell = cells[3]
        power_text = power_cell.get_text(strip=True)
        power = parse_numeric_or_special(power_text)
        
        # Cell 4: Accuracy
        accuracy_cell = cells[4]
        accuracy_text = accuracy_cell.get_text(strip=True)
        accuracy = parse_accuracy(accuracy_text, accuracy_cell)
        
        # Cell 5: PP
        pp_cell = cells[5]
        pp_text = pp_cell.get_text(strip=True)
        pp = parse_numeric_or_special(pp_text)
        
        # Cell 6: Effect
        effect_cell = cells[6]
        effect_text = effect_cell.get_text(strip=True)
        effect = effect_text if effect_text else None
        
        # Cell 7: Effect Probability
        prob_cell = cells[7]
        prob_text = prob_cell.get_text(strip=True)
        effect_probability = parse_numeric_or_special(prob_text)
        
        move = {
            "name": name,
            "type": move_type,
            "category": category,
            "power": power,
            "accuracy": accuracy,
            "pp": pp,
            "effect": effect,
            "effect_probability": effect_probability,
            "move_url": move_url
        }
        moves.append(move)
    
    return moves


def parse_numeric_or_special(text):
    """Parse numeric values, handling — and ∞"""
    text = text.strip()
    if text in ['—', '-', '']:
        return None
    if text == '∞' or text == '&infin;':
        return '∞'
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            return None


def parse_accuracy(text, cell):
    """Parse accuracy, handling ∞ specially"""
    text = text.strip()
    if text in ['—', '-', '']:
        return None
    if text == '∞' or text == '&infin;' or cell.get('class') == ['cell-num', 'num-infinity']:
        return '∞'
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            return None


def validate_moves(moves):
    """Generate validation report"""
    report = {
        "source": "https://pokemondb.net/move/all",
        "scraped_at": datetime.utcnow().isoformat() + "Z",
        "total_records": len(moves),
        "unique_moves": len(set(m['name'] for m in moves)),
        "duplicates": 0,
        "missing_fields": {
            "name": 0,
            "type": 0,
            "category": 0,
            "power": 0,
            "accuracy": 0,
            "pp": 0,
            "effect": 0,
            "effect_probability": 0,
            "move_url": 0
        },
        "categories": {
            "physical": 0,
            "special": 0,
            "status": 0,
            "other_or_null": 0
        },
        "status": "success"
    }
    
    seen_names = set()
    for move in moves:
        # Check duplicates
        if move['name'] in seen_names:
            report['duplicates'] += 1
        seen_names.add(move['name'])
        
        # Missing fields
        for field in report['missing_fields']:
            if not move.get(field):
                report['missing_fields'][field] += 1
        
        # Category counts
        cat = move.get('category')
        if cat == 'Physical':
            report['categories']['physical'] += 1
        elif cat == 'Special':
            report['categories']['special'] += 1
        elif cat == 'Status':
            report['categories']['status'] += 1
        else:
            report['categories']['other_or_null'] += 1
        
        # Validate URLs
        url = move.get('move_url', '')
        if url and not url.startswith('https://pokemondb.net/move/'):
            report['status'] = 'warning'
    
    return report


def main():
    print("Scraping moves from https://pokemondb.net/move/all...")
    moves = scrape_moves()
    print(f"Extracted {len(moves)} moves")
    
    # Save moves.json
    with open('moves.json', 'w', encoding='utf-8') as f:
        json.dump(moves, f, ensure_ascii=False, indent=2)
    print("Saved moves.json")
    
    # Generate and save report
    report = validate_moves(moves)
    with open('moves_scrape_report.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("Saved moves_scrape_report.json")
    
    # Print summary
    print(f"\nTotal records: {report['total_records']}")
    print(f"Unique moves: {report['unique_moves']}")
    print(f"Duplicates: {report['duplicates']}")
    print(f"\nMissing fields:")
    for field, count in report['missing_fields'].items():
        print(f"  {field}: {count}")
    print(f"\nCategories:")
    for cat, count in report['categories'].items():
        print(f"  {cat}: {count}")
    print(f"\nStatus: {report['status']}")


if __name__ == '__main__':
    main()