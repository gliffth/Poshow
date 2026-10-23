import json

with open('pokemon_ev.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Check forms for key Pokemon
for p in data:
    if p['pokedex_number'] in [3, 6, 19, 20, 25, 26] and p['form_name']:
        img = p['image_url'] or 'None'
        print(f"#{p['pokedex_number']:04d} | {p['display_name']} | form={p['form_name']} | EVs={p['ev_yield']} | img={img[:80]}...")

# Check Nidoran
for p in data:
    if 'Nidoran' in p['display_name']:
        print(f"#{p['pokedex_number']:04d} | {p['display_name'].encode('ascii', 'replace').decode()} | form={p['form_name']}")

# Count unique display names per dex number
from collections import defaultdict
dex_counts = defaultdict(list)
for p in data:
    dex_counts[p['pokedex_number']].append(p['display_name'])

print("\nDex numbers with multiple forms:")
for dex, names in sorted(dex_counts.items()):
    if len(names) > 1:
        print(f"  #{dex:04d}: {names}")

# Validate all EVs are integers and non-negative
for p in data:
    for stat, val in p['ev_yield'].items():
        if not isinstance(val, int):
            print(f"ERROR: {p['display_name']} {stat} = {val} (type: {type(val)})")
        if val < 0:
            print(f"ERROR: {p['display_name']} {stat} = {val} (negative)")

# Verify totals
for p in data:
    calc = sum(p['ev_yield'].values())
    if calc != p['total_ev_yield']:
        print(f"TOTAL MISMATCH: {p['display_name']} calc={calc} stored={p['total_ev_yield']}")

print("\nValidation complete!")