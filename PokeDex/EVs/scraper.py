#!/usr/bin/env python3
"""
Pokémon EV Yield Scraper for pokemondb.net/ev/all
Extracts complete EV yield database with proper form handling.
"""

import json
import re
import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


@dataclass
class EVYield:
    hp: int = 0
    attack: int = 0
    defense: int = 0
    special_attack: int = 0
    special_defense: int = 0
    speed: int = 0

    def total(self) -> int:
        return self.hp + self.attack + self.defense + self.special_attack + self.special_defense + self.speed

    def to_dict(self) -> dict:
        return {
            "hp": self.hp,
            "attack": self.attack,
            "defense": self.defense,
            "special_attack": self.special_attack,
            "special_defense": self.special_defense,
            "speed": self.speed
        }


@dataclass
class PokemonEVRecord:
    pokedex_number: int
    pokedex_number_display: str
    name: str
    display_name: str
    form_name: Optional[str]
    pokemon_url: Optional[str]
    image_url: Optional[str]
    ev_yield: EVYield
    total_ev_yield: int
    record_id: str


@dataclass
class ScrapeReport:
    source: str = "https://pokemondb.net/ev/all"
    scraped_at: str = field(default_factory=lambda: datetime.now().isoformat())
    total_records: int = 0
    unique_records: int = 0
    duplicate_records: int = 0
    forms: dict = field(default_factory=lambda: {"normal": 0, "alternate": 0})
    missing_fields: dict = field(default_factory=lambda: {"name": 0, "pokedex_number": 0, "pokemon_url": 0, "image_url": 0})
    invalid_values: dict = field(default_factory=lambda: {"negative_ev_values": 0, "non_integer_ev_values": 0, "incorrect_totals": 0, "invalid_urls": 0})
    ev_distribution: dict = field(default_factory=lambda: {"hp": 0, "attack": 0, "defense": 0, "special_attack": 0, "special_defense": 0, "speed": 0})
    errors: list = field(default_factory=list)
    status: str = "success"

    def to_dict(self) -> dict:
        return asdict(self)


class EVScraper:
    BASE_URL = "https://pokemondb.net"
    TARGET_URL = "https://pokemondb.net/ev/all"
    PLACEHOLDER_IMG = "https://img.pokemondb.net/s.png"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        self.records: list[PokemonEVRecord] = []
        self.report = ScrapeReport()
        self.seen_keys = set()

    def fetch_page(self, url: str) -> BeautifulSoup:
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")

    def extract_image_url(self, cell) -> Optional[str]:
        img = cell.find("img", class_="icon-pkmn")
        if not img:
            return None

        src = img.get("src")
        if src and src != self.PLACEHOLDER_IMG:
            return src

        source = cell.find("source")
        if source and source.get("srcset"):
            srcset = source["srcset"]
            first_url = srcset.split()[0]
            if first_url and first_url != self.PLACEHOLDER_IMG:
                return first_url

        return None

    def parse_ev_value(self, cell) -> int:
        text = cell.get_text(strip=True)
        if not text:
            return 0
        try:
            return int(text)
        except ValueError:
            self.report.invalid_values["non_integer_ev_values"] += 1
            return 0

    def generate_record_id(self, dex_num: int, display_name: str) -> str:
        clean_name = re.sub(r"[^a-z0-9]+", "-", display_name.lower()).strip("-")
        return f"{dex_num:04d}-{clean_name}"

    def process_row(self, row) -> Optional[PokemonEVRecord]:
        cells = row.find_all("td")
        if len(cells) < 8:
            return None

        try:
            dex_cell = cells[0]
            dex_num = int(dex_cell.get("data-sort-value", "0"))
            dex_display = dex_cell.find("span", class_="infocard-cell-data")
            dex_display_text = dex_display.get_text(strip=True) if dex_display else f"{dex_num:04d}"

            name_cell = cells[1]
            name_link = name_cell.find("a", class_="ent-name")
            if not name_link:
                self.report.missing_fields["name"] += 1
                return None

            base_name = name_link.get_text(strip=True)
            pokemon_url = urljoin(self.BASE_URL, name_link.get("href", ""))

            form_elem = name_cell.find("small", class_="text-muted")
            form_name = form_elem.get_text(strip=True) if form_elem else None
            display_name = f"{base_name} {form_name}" if form_name else base_name

            image_url = self.extract_image_url(dex_cell)

            ev_yield = EVYield(
                hp=self.parse_ev_value(cells[2]),
                attack=self.parse_ev_value(cells[3]),
                defense=self.parse_ev_value(cells[4]),
                special_attack=self.parse_ev_value(cells[5]),
                special_defense=self.parse_ev_value(cells[6]),
                speed=self.parse_ev_value(cells[7]),
            )

            total_ev = ev_yield.total()

            record_id = self.generate_record_id(dex_num, display_name)

            if record_id in self.seen_keys:
                self.report.duplicate_records += 1
                return None
            self.seen_keys.add(record_id)

            if not form_name:
                self.report.forms["normal"] += 1
            else:
                self.report.forms["alternate"] += 1

            if not image_url:
                self.report.missing_fields["image_url"] += 1

            if not pokemon_url:
                self.report.missing_fields["pokemon_url"] += 1

            for stat_name, value in ev_yield.to_dict().items():
                if value > 0:
                    self.report.ev_distribution[stat_name] += 1
                if value < 0:
                    self.report.invalid_values["negative_ev_values"] += 1

            return PokemonEVRecord(
                pokedex_number=dex_num,
                pokedex_number_display=dex_display_text,
                name=base_name,
                display_name=display_name,
                form_name=form_name,
                pokemon_url=pokemon_url,
                image_url=image_url,
                ev_yield=ev_yield,
                total_ev_yield=total_ev,
                record_id=record_id
            )

        except Exception as e:
            self.report.errors.append({
                "pokedex_number": dex_num if "dex_num" in locals() else None,
                "display_name": display_name if "display_name" in locals() else "Unknown",
                "reason": str(e)
            })
            return None

    def validate_records(self):
        for record in self.records:
            calc_total = record.ev_yield.total()
            if calc_total != record.total_ev_yield:
                self.report.invalid_values["incorrect_totals"] += 1
                self.report.errors.append({
                    "pokedex_number": record.pokedex_number,
                    "display_name": record.display_name,
                    "reason": f"Total EV mismatch: calculated={calc_total}, stored={record.total_ev_yield}"
                })

    def scrape(self) -> tuple[list[PokemonEVRecord], ScrapeReport]:
        print(f"Fetching {self.TARGET_URL}...")
        soup = self.fetch_page(self.TARGET_URL)

        tbody = soup.find("tbody")
        if not tbody:
            self.report.errors.append({"reason": "No tbody found in table"})
            self.report.status = "error"
            return self.records, self.report

        rows = tbody.find_all("tr")
        print(f"Found {len(rows)} rows in table")

        for row in rows:
            record = self.process_row(row)
            if record:
                self.records.append(record)

        self.report.total_records = len(self.records)
        self.report.unique_records = len(self.records)

        self.validate_records()

        print(f"Extracted {len(self.records)} records")
        print(f"Normal forms: {self.report.forms['normal']}, Alternate forms: {self.report.forms['alternate']}")
        print(f"Duplicate records skipped: {self.report.duplicate_records}")

        return self.records, self.report

    def save_json(self, records: list[PokemonEVRecord], report: ScrapeReport):
        output_data = []
        for r in records:
            d = asdict(r)
            d["ev_yield"] = r.ev_yield.to_dict()
            output_data.append(d)

        with open("pokemon_ev.json", "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        with open("pokemon_ev_scrape_report.json", "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)

        print("Saved pokemon_ev.json and pokemon_ev_scrape_report.json")


def main():
    scraper = EVScraper()
    records, report = scraper.scrape()
    scraper.save_json(records, report)

    if report.errors:
        print(f"\nErrors encountered: {len(report.errors)}")
        for err in report.errors[:10]:
            print(f"  - {err}")

    return 0 if report.status == "success" else 1


if __name__ == "__main__":
    sys.exit(main())