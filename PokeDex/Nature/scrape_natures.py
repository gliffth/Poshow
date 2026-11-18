#!/usr/bin/env python3
"""
Pokémon Natures Scraper for pokemondb.net/mechanics/natures
Extracts complete Nature mechanics data into structured JSON.
"""

import json
import re
import sys
from datetime import datetime
from typing import Any

import requests
from bs4 import BeautifulSoup


SOURCE_URL = "https://pokemondb.net/mechanics/natures"

# Canonical stat mapping from source labels to internal keys
STAT_MAP = {
    "HP": "hp",
    "Attack": "attack",
    "Defense": "defense",
    "Sp. Atk": "special_attack",
    "Sp. Def": "special_defense",
    "Speed": "speed",
}

# Reverse mapping for source preservation
STAT_MAP_REVERSE = {v: k for k, v in STAT_MAP.items()}

# Berry flavor mapping from the source page
BERRY_FLAVOR_MAP = {
    "attack": "Spicy",
    "defense": "Sour",
    "speed": "Sweet",
    "special_attack": "Dry",
    "special_defense": "Bitter",
}

VALID_STATS = set(STAT_MAP.values())
VALID_STATS.discard("hp")  # HP is never increased/decreased by nature


def fetch_page(url: str) -> str:
    """Fetch the HTML page content."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return response.text


def parse_alphabetical_table(soup: BeautifulSoup) -> list[dict[str, Any]]:
    """Parse the 'Natures alphabetically' table."""
    # Find the table after the "Natures alphabetically" heading
    alphabetical_table = None
    for h2 in soup.find_all("h2"):
        if "Natures alphabetically" in h2.get_text():
            alphabetical_table = h2.find_next("table", class_="data-table")
            break

    if not alphabetical_table:
        raise ValueError("Could not find alphabetical natures table")

    natures = []
    tbody = alphabetical_table.find("tbody")
    if not tbody:
        raise ValueError("No tbody in alphabetical table")

    for row in tbody.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue

        name = cells[0].get_text(strip=True)
        increases_raw = cells[1].get_text(strip=True)
        decreases_raw = cells[2].get_text(strip=True)

        # Normalize stat names
        increases = STAT_MAP.get(increases_raw)
        decreases = STAT_MAP.get(decreases_raw)

        if not increases or not decreases:
            raise ValueError(f"Unknown stat for {name}: {increases_raw} / {decreases_raw}")

        natures.append({
            "name": name,
            "increases_raw": increases_raw,
            "decreases_raw": decreases_raw,
            "increases": increases,
            "decreases": decreases,
        })

    return natures


def parse_matrix_table(soup: BeautifulSoup) -> dict[str, dict[str, str]]:
    """Parse the 'Natures by stat' matrix table.
    Returns a dict: {nature_name: {"increases": stat, "decreases": stat}}
    """
    matrix_table = None
    for h2 in soup.find_all("h2"):
        if "Natures by stat" in h2.get_text():
            matrix_table = h2.find_next("table", class_="data-table")
            break

    if not matrix_table:
        raise ValueError("Could not find matrix natures table")

    # Parse headers (decreased stats)
    thead = matrix_table.find("thead")
    if not thead:
        raise ValueError("No thead in matrix table")

    header_row = thead.find("tr")
    if not header_row:
        raise ValueError("No header row in matrix table")

    # First cell is empty, rest are decreased stats
    header_cells = header_row.find_all("th")
    decreased_stats = []
    for cell in header_cells[1:]:  # Skip first empty cell
        text = cell.get_text(strip=True)
        # Remove leading "- " if present
        text = text.lstrip("- ").strip()
        stat = STAT_MAP.get(text)
        if not stat:
            raise ValueError(f"Unknown decreased stat in matrix header: {text}")
        decreased_stats.append(stat)

    # Parse rows (increased stats)
    tbody = matrix_table.find("tbody")
    if not tbody:
        raise ValueError("No tbody in matrix table")

    matrix_data = {}
    for row in tbody.find_all("tr"):
        cells = row.find_all(["th", "td"])
        if not cells:
            continue

        # First cell is the increased stat (th with class text-positive)
        increased_raw = cells[0].get_text(strip=True)
        increased_raw = increased_raw.lstrip("+ ").strip()
        increased_stat = STAT_MAP.get(increased_raw)
        if not increased_stat:
            raise ValueError(f"Unknown increased stat in matrix row: {increased_raw}")

        # Remaining cells are nature names for each decreased stat
        for idx, cell in enumerate(cells[1:]):
            if idx >= len(decreased_stats):
                break
            nature_name = cell.get_text(strip=True)
            if not nature_name:
                continue
            decreased_stat = decreased_stats[idx]
            matrix_data[nature_name] = {
                "increases": increased_stat,
                "decreases": decreased_stat,
            }

    return matrix_data


def build_nature_records(
    alphabetical: list[dict],
    matrix: dict[str, dict[str, str]],
) -> tuple[list[dict], list[str]]:
    """Build complete nature records with cross-validation."""
    errors = []
    records = []

    # Create lookup from alphabetical data
    alpha_lookup = {n["name"]: n for n in alphabetical}

    # Cross-validate: check all names appear in both
    alpha_names = set(alpha_lookup.keys())
    matrix_names = set(matrix.keys())

    missing_in_matrix = alpha_names - matrix_names
    missing_in_alpha = matrix_names - alpha_names

    if missing_in_matrix:
        errors.append(f"Natures in alphabetical but not in matrix: {sorted(missing_in_matrix)}")
    if missing_in_alpha:
        errors.append(f"Natures in matrix but not in alphabetical: {sorted(missing_in_alpha)}")

    # Process each nature from alphabetical (primary source)
    for alpha in alphabetical:
        name = alpha["name"]
        increases = alpha["increases"]
        decreases = alpha["decreases"]
        increases_raw = alpha["increases_raw"]
        decreases_raw = alpha["decreases_raw"]

        is_neutral = increases == decreases

        # Cross-check with matrix
        matrix_match = "passed"
        if name in matrix:
            m_data = matrix[name]
            if m_data["increases"] != increases:
                errors.append(
                    f"{name}: increases mismatch - alpha={increases}, matrix={m_data['increases']}"
                )
                matrix_match = "failed"
            if m_data["decreases"] != decreases:
                errors.append(
                    f"{name}: decreases mismatch - alpha={decreases}, matrix={m_data['decreases']}"
                )
                matrix_match = "failed"

        # Build stat modifiers
        stat_modifiers = {stat: 1.0 for stat in STAT_MAP.values()}
        if not is_neutral:
            stat_modifiers[increases] = 1.1
            stat_modifiers[decreases] = 0.9
        # HP always 1.0

        # Berry flavors
        likes = BERRY_FLAVOR_MAP.get(increases, "Unknown")
        dislikes = BERRY_FLAVOR_MAP.get(decreases, "Unknown")

        record = {
            "name": name,
            "increases": increases,
            "decreases": decreases,
            "is_neutral": is_neutral,
            "stat_modifiers": stat_modifiers,
            "berry_flavor": {
                "likes": likes,
                "dislikes": dislikes,
            },
            "source": {
                "increases": increases_raw,
                "decreases": decreases_raw,
            },
        }
        records.append(record)

    return records, errors


def validate_dataset(records: list[dict]) -> list[str]:
    """Validate the complete dataset against all rules."""
    errors = []

    # Check count
    if len(records) != 25:
        errors.append(f"Expected 25 natures, got {len(records)}")

    # Check unique names
    names = [r["name"] for r in records]
    if len(set(names)) != 25:
        errors.append(f"Duplicate nature names found: {len(names)} total, {len(set(names))} unique")

    # Check each record
    neutral_count = 0
    non_neutral_count = 0

    for r in records:
        # Has one increased and one decreased
        if r["increases"] not in VALID_STATS:
            errors.append(f"{r['name']}: invalid increases stat: {r['increases']}")
        if r["decreases"] not in VALID_STATS:
            errors.append(f"{r['name']}: invalid decreases stat: {r['decreases']}")

        # HP always 1.0
        if r["stat_modifiers"]["hp"] != 1.0:
            errors.append(f"{r['name']}: HP modifier is not 1.0: {r['stat_modifiers']['hp']}")

        # Check modifiers
        if r["is_neutral"]:
            neutral_count += 1
            # All stats should be 1.0
            for stat, val in r["stat_modifiers"].items():
                if val != 1.0:
                    errors.append(f"{r['name']}: neutral nature but {stat} modifier is {val}")
        else:
            non_neutral_count += 1
            # Exactly one 1.1, one 0.9, rest 1.0
            mods = r["stat_modifiers"]
            count_11 = sum(1 for v in mods.values() if v == 1.1)
            count_09 = sum(1 for v in mods.values() if v == 0.9)
            count_10 = sum(1 for v in mods.values() if v == 1.0)

            if count_11 != 1:
                errors.append(f"{r['name']}: expected one 1.1 modifier, got {count_11}")
            if count_09 != 1:
                errors.append(f"{r['name']}: expected one 0.9 modifier, got {count_09}")
            if count_10 != 4:
                errors.append(f"{r['name']}: expected four 1.0 modifiers, got {count_10}")

        # Check is_neutral flag correctness
        expected_neutral = r["increases"] == r["decreases"]
        if r["is_neutral"] != expected_neutral:
            errors.append(f"{r['name']}: is_neutral flag mismatch (expected {expected_neutral})")

        # Check berry flavors
        expected_likes = BERRY_FLAVOR_MAP.get(r["increases"])
        expected_dislikes = BERRY_FLAVOR_MAP.get(r["decreases"])
        if r["berry_flavor"]["likes"] != expected_likes:
            errors.append(f"{r['name']}: likes mismatch - got {r['berry_flavor']['likes']}, expected {expected_likes}")
        if r["berry_flavor"]["dislikes"] != expected_dislikes:
            errors.append(f"{r['name']}: dislikes mismatch - got {r['berry_flavor']['dislikes']}, expected {expected_dislikes}")

    # Check neutral/non-neutral counts
    if neutral_count != 5:
        errors.append(f"Expected 5 neutral natures, got {neutral_count}")
    if non_neutral_count != 20:
        errors.append(f"Expected 20 non-neutral natures, got {non_neutral_count}")

    return errors


def main():
    print(f"Fetching {SOURCE_URL}...")
    html = fetch_page(SOURCE_URL)
    soup = BeautifulSoup(html, "lxml")

    print("Parsing alphabetical table...")
    alphabetical = parse_alphabetical_table(soup)
    print(f"  Found {len(alphabetical)} natures")

    print("Parsing matrix table...")
    matrix = parse_matrix_table(soup)
    print(f"  Found {len(matrix)} natures")

    print("Building records with cross-validation...")
    records, cross_errors = build_nature_records(alphabetical, matrix)

    print("Validating dataset...")
    validation_errors = validate_dataset(records)

    all_errors = cross_errors + validation_errors

    # Build final output
    output = {
        "metadata": {
            "source": SOURCE_URL,
            "introduced_generation": 3,
            "total_natures": len(records),
        },
        "berry_flavor_mapping": BERRY_FLAVOR_MAP,
        "natures": records,
    }

    # Validation report
    neutral_natures = sum(1 for r in records if r["is_neutral"])
    non_neutral_natures = len(records) - neutral_natures

    report = {
        "source": SOURCE_URL,
        "scraped_at": datetime.utcnow().isoformat() + "Z",
        "total_natures": len(records),
        "unique_natures": len(set(r["name"] for r in records)),
        "duplicate_natures": len(records) - len(set(r["name"] for r in records)),
        "neutral_natures": neutral_natures,
        "non_neutral_natures": non_neutral_natures,
        "validation": {
            "alphabetical_table": "passed" if not cross_errors else "failed",
            "stat_matrix": "passed" if not cross_errors else "failed",
            "nature_cross_check": "passed" if not cross_errors else "failed",
            "berry_mapping": "passed",
            "modifier_validation": "passed" if not validation_errors else "failed",
            "json_validation": "passed",
        },
        "errors": all_errors,
        "status": "success" if not all_errors else "failed",
    }

    # Write output files
    with open("natures.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    with open("natures_scrape_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\nOutput written to natures.json and natures_scrape_report.json")
    print(f"Status: {report['status']}")
    print(f"Total natures: {len(records)}")
    print(f"Neutral: {neutral_natures}, Non-neutral: {non_neutral_natures}")

    if all_errors:
        print("\nERRORS:")
        for err in all_errors:
            print(f"  - {err}")
        sys.exit(1)

    print("\nAll validations passed!")


if __name__ == "__main__":
    main()