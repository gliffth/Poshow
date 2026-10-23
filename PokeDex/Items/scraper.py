#!/usr/bin/env python3
"""
Pokémon Database Item Scraper
Scrapes https://pokemondb.net/item/all and all individual item detail pages.
Produces items.json and items_scrape_report.json
"""

import json
import time
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


class PokemonDBItemScraper:
    BASE_URL = "https://pokemondb.net"
    MAIN_URL = "https://pokemondb.net/item/all"
    
    # Category mapping from sort values to display names
    CATEGORY_MAP = {
        "hold": "Hold items",
        "medicine": "Medicine",
        "berries": "Berries",
        "pokeballs": "Pokeballs",
        "general": "General items",
        "battle": "Battle items",
        "machines": "Machines",
        "unknown": "Unknown",
        "0": None,
    }
    
    def __init__(self, delay: float = 0.5, timeout: int = 30):
        self.delay = delay
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })
        self.visited_urls = set()
        self.items = []
        self.errors = []
        
        # Statistics
        self.stats = {
            "total_items": 0,
            "unique_items": 0,
            "duplicate_items": 0,
            "successful_detail_pages": 0,
            "failed_detail_pages": 0,
            "missing_fields": {
                "name": 0,
                "category": 0,
                "effect": 0,
                "image_url": 0,
                "item_url": 0,
            },
            "detail_data": {
                "game_descriptions": 0,
                "locations": 0,
                "evolution_data": 0,
            },
        }
    
    def fetch(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch a URL and return parsed BeautifulSoup object."""
        if url in self.visited_urls:
            return None
        
        self.visited_urls.add(url)
        
        try:
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
            return BeautifulSoup(resp.content, "html.parser")
        except Exception as e:
            self.errors.append({"url": url, "error": str(e)})
            return None
        finally:
            time.sleep(self.delay)
    
    def parse_main_table(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Parse the main item table from /item/all."""
        items = []
        table = soup.find("table", class_="data-table")
        
        if not table:
            self.errors.append({"url": self.MAIN_URL, "error": "Main table not found"})
            return items
        
        tbody = table.find("tbody")
        if not tbody:
            self.errors.append({"url": self.MAIN_URL, "error": "Table body not found"})
            return items
        
        rows = tbody.find_all("tr")
        
        for idx, row in enumerate(rows):
            try:
                item = self.parse_item_row(row)
                if item:
                    items.append(item)
            except Exception as e:
                self.errors.append({
                    "url": self.MAIN_URL,
                    "error": f"Row {idx} parse error: {str(e)}"
                })
        
        return items
    
    def parse_item_row(self, row) -> Optional[Dict[str, Any]]:
        """Parse a single item row from the main table."""
        cells = row.find_all("td")
        if len(cells) < 3:
            return None
        
        # Name cell (first cell)
        name_cell = cells[0]
        name_link = name_cell.find("a", class_="ent-name")
        name_img = name_cell.find("img", class_="icon-item-img")
        
        name = None
        item_url = None
        image_url = None
        image_alt = None
        
        if name_link:
            name = name_link.get_text(strip=True)
            href = name_link.get("href")
            if href:
                item_url = urljoin(self.BASE_URL, href)
        
        if name_img:
            image_url = name_img.get("src") or name_img.get("data-src")
            image_alt = name_img.get("alt")
        
        # Category cell (second cell)
        category_cell = cells[1]
        category = category_cell.get_text(strip=True)
        category_sort = category_cell.get("data-sort-value", "").strip()
        
        # Use the sort value to normalize category, fallback to displayed text
        if category_sort and category_sort in self.CATEGORY_MAP:
            category = self.CATEGORY_MAP[category_sort]
        elif category == "0" or category == "":
            category = None
        
        # Effect cell (third cell)
        effect_cell = cells[2]
        effect = effect_cell.get_text(strip=True)
        if not effect:
            effect = None
        
        # Validate required fields
        if not name:
            self.stats["missing_fields"]["name"] += 1
            return None
        
        if not category:
            self.stats["missing_fields"]["category"] += 1
        
        if not effect:
            self.stats["missing_fields"]["effect"] += 1
        
        if not image_url:
            self.stats["missing_fields"]["image_url"] += 1
        
        if not item_url:
            self.stats["missing_fields"]["item_url"] += 1
        
        return {
            "name": name,
            "category": category,
            "effect": effect,
            "image_url": image_url,
            "image_alt": image_alt,
            "item_url": item_url,
            "source_url": self.MAIN_URL,
        }
    
    def parse_detail_page(self, soup: BeautifulSoup, item_url: str) -> Dict[str, Any]:
        """Parse an individual item detail page."""
        detail_data = {
            "full_effect": None,
            "short_description": None,
            "game_descriptions": {},
            "locations": [],
            "evolution": [],
            "held_by_pokemon": [],
        }
        
        main = soup.find("main", id="main")
        if not main:
            return detail_data
        
        # Find all grid-row sections
        grid_rows = main.find_all("div", class_="grid-row")
        
        for grid_row in grid_rows:
            cols = grid_row.find_all("div", class_="grid-col")
            for col in cols:
                h2 = col.find("h2")
                if not h2:
                    continue
                
                section_title = h2.get_text(strip=True)
                
                # Effects section
                if section_title == "Effects":
                    p = col.find("p")
                    if p:
                        detail_data["full_effect"] = p.get_text(strip=True)
                
                # Game descriptions
                elif section_title == "Game descriptions" or "Game descriptions" in section_title:
                    detail_data["game_descriptions"] = self.parse_game_descriptions(col)
                
                
                
                # Game locations
                elif section_title == "Game locations":
                    detail_data["locations"] = self.parse_locations(col)
        
        # Check for evolution information in the Effects section
        # (Fire Stone has evolution data in the Effects section)
        if detail_data["full_effect"]:
            detail_data["evolution"] = self.parse_evolution_from_effects(main)
        
        # Update stats
        if detail_data["game_descriptions"]:
            self.stats["detail_data"]["game_descriptions"] += 1
        if detail_data["locations"]:
            self.stats["detail_data"]["locations"] += 1
        if detail_data["evolution"]:
            self.stats["detail_data"]["evolution_data"] += 1
        
        return detail_data
    
    def parse_game_descriptions(self, col) -> Dict[str, str]:
        """Parse game descriptions table."""
        descriptions = {}
        table = col.find("table", class_="vitals-table")
        if not table:
            return descriptions
        
        tbody = table.find("tbody")
        if not tbody:
            return descriptions
        
        for row in tbody.find_all("tr"):
            th = row.find("th")
            td = row.find("td")
            if th and td:
                # Parse game names from th - they're separated by <br> and zero-width spaces
                # Get the HTML and split by <br> tags
                th_html = str(th)
                # Split by <br> tags (including variations)
                parts = re.split(r'<br\s*/?>', th_html)
                game_names = []
                for part in parts:
                    # Extract text from each part
                    part_soup = BeautifulSoup(part, "html.parser")
                    text = part_soup.get_text(strip=True)
                    # Clean up zero-width spaces and other artifacts
                    text = text.replace("\u200b", "").replace("\u200c", "").replace("\u200d", "")
                    text = text.replace("&#8203;", "").replace("&#8204;", "")
                    if text:
                        game_names.append(text)
                
                desc = td.get_text(strip=True)
                if game_names and desc:
                    # Join multiple game names with " / " separator
                    key = " / ".join(game_names)
                    descriptions[key] = desc
        
        return descriptions
    
    def parse_locations(self, col) -> List[str]:
        """Parse game locations."""
        locations = []
        
        # Check for "Sorry, we don't have location data just yet."
        p = col.find("p")
        if p and "don't have location data" in p.get_text():
            return locations
        
        # If there's a list or table of locations, parse it
        # (Currently not implemented as most items show "no location data")
        ul = col.find("ul")
        if ul:
            for li in ul.find_all("li"):
                loc_text = li.get_text(strip=True)
                if loc_text:
                    locations.append(loc_text)
        
        return locations
    
    def parse_evolution_from_effects(self, main) -> List[Dict[str, str]]:
        """Parse evolution information from the Effects section."""
        evolution = []
        
        # Find the Effects section
        effects_h2 = None
        for h2 in main.find_all("h2"):
            if h2.get_text(strip=True) == "Effects":
                effects_h2 = h2
                break
        
        if not effects_h2:
            return evolution
        
        # Look for list items in the effects section
        # The evolution data appears as a <ul> after the first <p> in the Effects section
        effects_div = effects_h2.find_parent("div", class_="grid-col")
        if not effects_div:
            return evolution
        
        ul = effects_div.find("ul")
        if not ul:
            return evolution
        
        for li in ul.find_all("li"):
            text = li.get_text(strip=True)
            # Parse text like "Vulpix(evolves intoNinetales)" (no spaces)
            # or "Hisuian Growlithe(evolves intoHisuian Arcanine)"
            # or "Male Kirlia(evolves intoGallade)"
            match = re.match(r"^(.+?)\(evolves into(.+?)\)$", text, re.IGNORECASE)
            if match:
                pokemon = match.group(1).strip()
                evolves_into = match.group(2).strip()
                # Extract method from context (e.g., "Fire Stone")
                method = ""
                evolution.append({
                    "pokemon": pokemon,
                    "evolves_into": evolves_into,
                    "method": method,
                })
            else:
                # Some items might have different formats
                evolution.append({"raw": text})
        
        return evolution
    
    def scrape_main_page(self) -> List[Dict[str, Any]]:
        """Scrape the main /item/all page."""
        print(f"Fetching main page: {self.MAIN_URL}")
        soup = self.fetch(self.MAIN_URL)
        if not soup:
            return []
        
        print("Parsing main table...")
        items = self.parse_main_table(soup)
        self.stats["total_items"] = len(items)
        print(f"Found {len(items)} items in main table")
        return items
    
    def scrape_detail_pages(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Scrape detail pages for all items that have URLs."""
        enriched_items = []
        
        for idx, item in enumerate(items):
            item_url = item.get("item_url")
            
            if not item_url:
                enriched_items.append(item)
                continue
            
            print(f"[{idx+1}/{len(items)}] Scraping detail page: {item['name']}")
            soup = self.fetch(item_url)
            
            if not soup:
                self.stats["failed_detail_pages"] += 1
                self.errors.append({
                    "name": item["name"],
                    "url": item_url,
                    "error": "Failed to fetch detail page",
                    "status": "failed"
                })
                enriched_items.append(item)
                continue
            
            self.stats["successful_detail_pages"] += 1
            detail_data = self.parse_detail_page(soup, item_url)
            
            # Merge detail data into item
            item.update(detail_data)
            item["source_url"] = item_url
            enriched_items.append(item)
        
        return enriched_items
    
    def deduplicate_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate items based on item_url."""
        seen_urls = set()
        unique_items = []
        duplicates = 0
        
        for item in items:
            item_url = item.get("item_url")
            if item_url and item_url in seen_urls:
                duplicates += 1
                continue
            if item_url:
                seen_urls.add(item_url)
            unique_items.append(item)
        
        self.stats["duplicate_items"] = duplicates
        self.stats["unique_items"] = len(unique_items)
        return unique_items
    
    def run(self) -> Dict[str, Any]:
        """Run the complete scraping process."""
        print("=" * 60)
        print("Pokémon Database Item Scraper")
        print("=" * 60)
        
        # Step 1: Scrape main page
        items = self.scrape_main_page()
        if not items:
            print("ERROR: No items found on main page!")
            return {"items": [], "report": self.generate_report()}
        
        # Step 2: Scrape detail pages
        print("\nScraping detail pages...")
        items = self.scrape_detail_pages(items)
        
        # Step 3: Deduplicate
        print("\nDeduplicating items...")
        items = self.deduplicate_items(items)
        
        # Step 4: Save items.json
        print("\nSaving items.json...")
        self.save_items(items)
        
        # Step 5: Generate and save report
        print("Generating report...")
        report = self.generate_report()
        self.save_report(report)
        
        print("\n" + "=" * 60)
        print("SCRAPING COMPLETE")
        print("=" * 60)
        print(f"Total items: {self.stats['total_items']}")
        print(f"Unique items: {self.stats['unique_items']}")
        print(f"Duplicates removed: {self.stats['duplicate_items']}")
        print(f"Successful detail pages: {self.stats['successful_detail_pages']}")
        print(f"Failed detail pages: {self.stats['failed_detail_pages']}")
        print(f"Errors: {len(self.errors)}")
        
        return {"items": items, "report": report}
    
    def save_items(self, items: List[Dict[str, Any]]):
        """Save items to JSON file."""
        output_path = Path("items.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        print(f"Saved {len(items)} items to {output_path}")
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate the validation report."""
        return {
            "source": self.MAIN_URL,
            "scraped_at": datetime.now().isoformat(),
            "total_items": self.stats["total_items"],
            "unique_items": self.stats["unique_items"],
            "duplicate_items": self.stats["duplicate_items"],
            "successful_detail_pages": self.stats["successful_detail_pages"],
            "failed_detail_pages": self.stats["failed_detail_pages"],
            "missing_fields": self.stats["missing_fields"],
            "detail_data": self.stats["detail_data"],
            "errors": self.errors,
            "status": "success" if len(self.errors) == 0 else "completed_with_errors",
        }
    
    def save_report(self, report: Dict[str, Any]):
        """Save validation report to JSON file."""
        output_path = Path("items_scrape_report.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"Saved report to {output_path}")


def main():
    scraper = PokemonDBItemScraper(delay=0.3)  # 300ms delay between requests
    result = scraper.run()
    
    # Quick validation
    items = result["items"]
    report = result["report"]
    
    print("\n--- VALIDATION ---")
    print(f"Items in JSON: {len(items)}")
    print(f"Items with names: {sum(1 for i in items if i.get('name'))}")
    print(f"Items with categories: {sum(1 for i in items if i.get('category'))}")
    print(f"Items with effects: {sum(1 for i in items if i.get('effect'))}")
    print(f"Items with image URLs: {sum(1 for i in items if i.get('image_url'))}")
    print(f"Items with item URLs: {sum(1 for i in items if i.get('item_url'))}")
    print(f"Items with game descriptions: {sum(1 for i in items if i.get('game_descriptions'))}")
    
    print(f"Items with evolution data: {sum(1 for i in items if i.get('evolution'))}")


if __name__ == "__main__":
    main()