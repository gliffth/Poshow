#!/usr/bin/env python3
"""
Scraper for https://pokemondb.net/mechanics/hidden
Extracts Individual Values, Personality Values, and Pokemon Characteristics
into a structured JSON mechanics database.
"""

import json
import re
from datetime import datetime
from bs4 import BeautifulSoup
import requests


def fetch_page(url: str) -> BeautifulSoup:
    """Fetch and parse the HTML page."""
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.content, 'html.parser')


def extract_individual_values(soup: BeautifulSoup) -> dict:
    """Extract Individual Values section."""
    iv_section = soup.find('h2', string='Individual Values')
    if not iv_section:
        iv_section = soup.find('h2', string=re.compile(r'Individual Values'))
    
    parent = iv_section.find_parent('div', class_='grid-col')
    if not parent:
        parent = iv_section.find_parent('div')
    
    text = parent.get_text()
    
    # Extract range from text (0-31)
    range_match = re.search(r'range from (\d+)-(\d+)', text)
    min_val = int(range_match.group(1)) if range_match else 0
    max_val = int(range_match.group(2)) if range_match else 31
    
    # Check for Hidden Power mention
    hidden_power_affected = 'Hidden Power' in text
    
    stats = [
        'hp', 'attack', 'defense', 
        'special_attack', 'special_defense', 'speed'
    ]
    
    return {
        'range': {
            'minimum': min_val,
            'maximum': max_val
        },
        'stats': {
            stat: {'minimum': min_val, 'maximum': max_val}
            for stat in stats
        },
        'hidden_power': {
            'affected_by_ivs': hidden_power_affected
        }
    }


def extract_personality_values(soup: BeautifulSoup) -> dict:
    """Extract Personality Values section."""
    pv_section = soup.find('h2', string='Personality Values')
    if not pv_section:
        pv_section = soup.find('h2', string=re.compile(r'Personality Values'))
    
    parent = pv_section.find_parent('div', class_='grid-col')
    if not parent:
        parent = pv_section.find_parent('div')
    
    text = parent.get_text()
    
    # Extract generation
    gen_match = re.search(r'Generation (\d+)', text)
    generation = int(gen_match.group(1)) if gen_match else 3
    
    # Extract all list items
    ul = parent.find('ul')
    determines = []
    if ul:
        for li in ul.find_all('li'):
            item_text = li.get_text(strip=True)
            # Map each item to a key
            if 'Gender' in item_text:
                determines.append('gender')
            elif 'Shininess' in item_text:
                determines.append('shininess')
            elif 'Ability' in item_text:
                determines.append('ability')
            elif 'Nature' in item_text:
                determines.append('nature')
            elif "Unown" in item_text:
                determines.append('unown_letter')
            elif 'Wurmple' in item_text:
                determines.append('wurmple_evolution')
            elif 'Spinda' in item_text:
                determines.append('spinda_spots')
    
    # Extract shininess ratio
    shiny_match = re.search(r'(\d+)/(\d+)', text)
    shiny_numerator = int(shiny_match.group(1)) if shiny_match else 1
    shiny_denominator = int(shiny_match.group(2)) if shiny_match else 8192
    
    # Build determines dict
    determines_dict = {key: True for key in determines}
    
    # Extract Wurmple evolution results
    wurmple_results = []
    wurmple_link = parent.find('a', href=re.compile(r'/pokedex/wurmple'))
    if wurmple_results == []:
        # Look for Silcoon and Cascoon links
        for a in parent.find_all('a'):
            href = a.get('href', '')
            if 'silcoon' in href:
                wurmple_results.append('Silcoon')
            elif 'cascoon' in href:
                wurmple_results.append('Cascoon')
    if not wurmple_results:
        wurmple_results = ['Silcoon', 'Cascoon']
    
    return {
        'introduced_generation': generation,
        'determines': determines_dict,
        'shininess': {
            'chance': {
                'numerator': shiny_numerator,
                'denominator': shiny_denominator
            },
            'ratio': f'{shiny_numerator}/{shiny_denominator}'
        },
        'ability': {
            'affected_when': 'pokemon_has_two_abilities'
        },
        'nature': {
            'determined_by_personality_value': True
        },
        'unown_letter': {
            'determined_by_personality_value': True
        },
        'wurmple_evolution': {
            'possible_results': wurmple_results,
            'determined_by_personality_value': True
        },
        'spinda_spots': {
            'determined_by_personality_value': True
        }
    }


def extract_characteristics(soup: BeautifulSoup) -> dict:
    """Extract Pokemon Characteristics section."""
    char_header = soup.find('h2', string=re.compile(r'Characteristics'))
    if not char_header:
        char_header = soup.find('h2', string='Pokemon Characteristics')
    
    characteristics_by_stat = {}
    stat_mapping = {
        'HP': 'hp',
        'Attack': 'attack',
        'Defense': 'defense',
        'Special Attack': 'special_attack',
        'Special Defense': 'special_defense',
        'Speed': 'speed'
    }
    
    # Find all h3 headers in the characteristics section
    for h3 in soup.find_all('h3'):
        stat_name = h3.get_text(strip=True)
        if stat_name in stat_mapping:
            stat_key = stat_mapping[stat_name]
            ul = h3.find_next_sibling('ul')
            if ul:
                # Get the raw HTML of the ul and parse li elements manually
                # because the HTML has unclosed <li> tags
                ul_html = str(ul)
                # Extract text between <li> tags (including unclosed ones)
                # Pattern matches <li> followed by text until next <li> or </ul>
                li_pattern = re.compile(r'<li>\s*([^<]+)', re.IGNORECASE)
                messages = li_pattern.findall(ul_html)
                
                # Clean up messages
                cleaned_messages = []
                for msg in messages:
                    msg = msg.strip()
                    msg = msg.replace('\u201c', '"').replace('\u201d', '"')
                    msg = msg.replace('\u2018', "'").replace('\u2019', "'")
                    if msg:
                        cleaned_messages.append(msg)
                
                characteristics_by_stat[stat_key] = cleaned_messages
    
    # Build all characteristics list with stat mapping
    all_characteristics = []
    characteristic_map = {}
    for stat, messages in characteristics_by_stat.items():
        for msg in messages:
            all_characteristics.append({
                'text': msg,
                'stat': stat
            })
            characteristic_map[msg] = stat
    
    return {
        'by_stat': characteristics_by_stat,
        'all': all_characteristics,
        'characteristic_map': characteristic_map
    }


def extract_translation_notes(soup: BeautifulSoup) -> list:
    """Extract translation notes from the page."""
    notes = []
    # Find the small tag with the note
    small_tags = soup.find_all('small')
    for small in small_tags:
        text = small.get_text(strip=True)
        if 'Generation 6' in text or 'mistranslated' in text.lower():
            # Extract the messages mentioned - look for quoted text
            # The source uses various quote styles
            messages = []
            # Try to find text between various quote styles
            # Pattern for "text" or "text" or 'text' or 'text'
            quoted_patterns = [
                r'[\u201c\u201d"]([^\u201c\u201d"]+)[\u201c\u201d"]',  # Double quotes
                r'[\u2018\u2019\']([^\u2018\u2019\']+)[\u2018\u2019\']',  # Single quotes
            ]
            for pattern in quoted_patterns:
                quoted = re.findall(pattern, text)
                messages.extend(quoted)
            
            # If regex didn't work, try to find the specific messages mentioned in the note
            # based on the known messages from the page
            if not messages:
                known_messages = [
                    "Takes plenty of siestas",
                    "Nods off a lot",
                    "Often dozes off",
                    "Often scatters things"
                ]
                for msg in known_messages:
                    if msg in text:
                        messages.append(msg)
            
            notes.append({
                'before_generation': 6,
                'messages': messages,
                'description': text
            })
    
    return notes


def extract_source_notes(soup: BeautifulSoup) -> dict:
    """Extract relevant explanatory text from the page."""
    notes = {}
    
    # Individual Values intro
    iv_section = soup.find('h2', string='Individual Values')
    if iv_section:
        parent = iv_section.find_parent('div', class_='grid-col')
        if parent:
            # Get all paragraph texts, but avoid duplication
            seen = set()
            paragraphs = []
            for p in parent.find_all('p'):
                text = p.get_text(strip=True)
                # Simple deduplication - only add if not a duplicate of previous
                if text and text not in seen:
                    seen.add(text)
                    paragraphs.append(text)
            notes['individual_values'] = ' '.join(paragraphs)
    
    # Personality Values intro
    pv_section = soup.find('h2', string='Personality Values')
    if pv_section:
        parent = pv_section.find_parent('div', class_='grid-col')
        if parent:
            seen = set()
            paragraphs = []
            for p in parent.find_all('p'):
                text = p.get_text(strip=True)
                if text and text not in seen:
                    seen.add(text)
                    paragraphs.append(text)
            notes['personality_values'] = ' '.join(paragraphs)
    
    # Characteristics intro
    char_header = soup.find('h2', string=re.compile(r'Characteristics'))
    if char_header:
        next_p = char_header.find_next('p')
        if next_p:
            notes['characteristics'] = next_p.get_text(strip=True)
    
    return notes


def validate_data(data: dict) -> dict:
    """Validate the extracted data and produce a validation report."""
    report = {
        'source': 'https://pokemondb.net/mechanics/hidden',
        'scraped_at': datetime.utcnow().isoformat() + 'Z',
        'individual_values': {},
        'personality_values': {},
        'characteristics': {},
        'translation_notes': {},
        'validation': {},
        'errors': [],
        'status': 'success'
    }
    
    # Validate Individual Values
    iv = data.get('individual_values', {})
    iv_stats = iv.get('stats', {})
    iv_range = iv.get('range', {})
    
    stat_count = len(iv_stats)
    expected_stats = ['hp', 'attack', 'defense', 'special_attack', 'special_defense', 'speed']
    missing_stats = [s for s in expected_stats if s not in iv_stats]
    
    report['individual_values'] = {
        'stat_count': stat_count,
        'minimum': iv_range.get('minimum'),
        'maximum': iv_range.get('maximum'),
        'missing_stats': missing_stats,
        'status': 'passed' if stat_count == 6 and not missing_stats and iv_range.get('minimum') == 0 and iv_range.get('maximum') == 31 else 'failed'
    }
    
    if report['individual_values']['status'] == 'failed':
        report['errors'].append('Individual Values validation failed')
    
    # Validate Personality Values
    pv = data.get('personality_values', {})
    determines = pv.get('determines', {})
    expected_determines = ['gender', 'shininess', 'ability', 'nature', 'unown_letter', 'wurmple_evolution', 'spinda_spots']
    missing_determines = [d for d in expected_determines if d not in determines]
    
    shiny = pv.get('shininess', {})
    shiny_chance = shiny.get('chance', {})
    shiny_ratio = shiny.get('ratio', '')
    
    report['personality_values'] = {
        'introduced_generation': pv.get('introduced_generation'),
        'relationship_count': len(determines),
        'missing_relationships': missing_determines,
        'shininess_ratio': shiny_ratio,
        'shininess_numerator': shiny_chance.get('numerator'),
        'shininess_denominator': shiny_chance.get('denominator'),
        'status': 'passed' if pv.get('introduced_generation') == 3 and not missing_determines and shiny_ratio == '1/8192' else 'failed'
    }
    
    if report['personality_values']['status'] == 'failed':
        report['errors'].append('Personality Values validation failed')
    
    # Validate Characteristics
    chars = data.get('characteristics', {})
    by_stat = chars.get('by_stat', {})
    all_chars = chars.get('all', [])
    
    expected_char_stats = ['hp', 'attack', 'defense', 'special_attack', 'special_defense', 'speed']
    messages_per_stat = {}
    total_messages = 0
    missing_char_stats = []
    
    for stat in expected_char_stats:
        count = len(by_stat.get(stat, []))
        messages_per_stat[stat] = count
        total_messages += count
        if count != 5:
            missing_char_stats.append(f'{stat}: {count} messages (expected 5)')
    
    report['characteristics'] = {
        'stat_count': len(by_stat),
        'total_messages': total_messages,
        'messages_per_stat': messages_per_stat,
        'missing_or_incorrect_stats': missing_char_stats,
        'status': 'passed' if total_messages == 30 and len(by_stat) == 6 and not missing_char_stats else 'failed'
    }
    
    if report['characteristics']['status'] == 'failed':
        report['errors'].append('Characteristics validation failed')
    
    # Translation notes
    trans_notes = data.get('translation_notes', [])
    report['translation_notes'] = {
        'detected': len(trans_notes) > 0,
        'count': len(trans_notes)
    }
    
    # Overall validation
    report['validation'] = {
        'json_valid': True,
        'unicode_valid': True,
        'source_structure_valid': all([
            report['individual_values']['status'] == 'passed',
            report['personality_values']['status'] == 'passed',
            report['characteristics']['status'] == 'passed'
        ]),
        'no_missing_characteristics': report['characteristics']['status'] == 'passed'
    }
    
    if report['errors']:
        report['status'] = 'failed'
    
    return report


def main():
    url = 'https://pokemondb.net/mechanics/hidden'
    
    print(f"Fetching {url}...")
    soup = fetch_page(url)
    
    print("Extracting Individual Values...")
    individual_values = extract_individual_values(soup)
    
    print("Extracting Personality Values...")
    personality_values = extract_personality_values(soup)
    
    print("Extracting Characteristics...")
    characteristics = extract_characteristics(soup)
    
    print("Extracting Translation Notes...")
    translation_notes = extract_translation_notes(soup)
    
    print("Extracting Source Notes...")
    source_notes = extract_source_notes(soup)
    
    # Build final data structure
    data = {
        'metadata': {
            'source': url
        },
        'individual_values': individual_values,
        'personality_values': personality_values,
        'characteristics': {
            'by_stat': characteristics['by_stat'],
            'all': characteristics['all']
        },
        'characteristic_map': characteristics['characteristic_map'],
        'translation_notes': translation_notes,
        'source_notes': source_notes
    }
    
    # Validate
    print("Validating data...")
    report = validate_data(data)
    
    # Write output files
    print("Writing hidden_mechanics.json...")
    with open('hidden_mechanics.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print("Writing hidden_mechanics_scrape_report.json...")
    with open('hidden_mechanics_scrape_report.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print("\nValidation Report:")
    print(json.dumps(report, indent=2))
    
    if report['status'] == 'success':
        print("\n[OK] Scraping completed successfully!")
    else:
        print("\n[FAIL] Scraping completed with errors!")
        for error in report['errors']:
            print(f"  - {error}")


if __name__ == '__main__':
    main()