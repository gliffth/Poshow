import json

with open('pokemon_ev.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Verify some specific values from the attack page
checks = [
    (15, 'Beedrill', 2),
    (15, 'Mega Beedrill', 2),
    (23, 'Ekans', 1),
    (24, 'Arbok', 2),
    (32, 'Nidoran', 1),  # Nidoran♂
    (34, 'Nidoking', 3),
    (51, 'Alolan Dugtrio', 2),
    (52, 'Galarian Meowth', 1),
    (58, 'Growlithe', 1),
    (58, 'Hisuian Growlithe', 1),
    (59, 'Arcanine', 2),
    (128, 'Combat Breed', 2),
    (130, 'Gyarados', 2),
]

print('Cross-checking Attack EV values:')
for dex, name_part, expected_attack in checks:
    matches = [p for p in data if p['pokedex_number'] == dex and name_part.lower() in p['display_name'].lower()]
    if matches:
        p = matches[0]
        actual = p['ev_yield']['attack']
        status = 'OK' if actual == expected_attack else 'MISMATCH'
        name = p["display_name"].encode('ascii', 'replace').decode()
        print(f'  {status}: #{dex:04d} {name} - Attack EV: {actual} (expected {expected_attack})')
    else:
        print(f'  NOT FOUND: #{dex:04d} {name_part}')

# Count total with attack > 0
attack_count = sum(1 for p in data if p['ev_yield']['attack'] > 0)
print(f'\nTotal records with Attack EV > 0: {attack_count} (expected 362)')

# Also verify all stats match the report
for stat, expected in [('hp', 152), ('attack', 362), ('defense', 197), ('special_attack', 254), ('special_defense', 147), ('speed', 247)]:
    actual = sum(1 for p in data if p['ev_yield'][stat] > 0)
    status = 'OK' if actual == expected else 'MISMATCH'
    print(f'  {status}: {stat} - {actual} (expected {expected})')