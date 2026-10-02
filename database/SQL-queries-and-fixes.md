# POSHOW - SQL QUERIES & QUICK FIXES

## PRACTICAL SQL QUERIES

### Players Management

```sql
-- Get player profile with stats
SELECT 
    user_id,
    username,
    level,
    experience,
    coins,
    wins,
    losses,
    ROUND((wins::FLOAT / NULLIF(wins + losses, 0)) * 100, 2) as win_rate,
    elo,
    pokemon_caught,
    created_at,
    last_login
FROM players
WHERE user_id = $1;

-- Top 10 players by ELO
SELECT 
    ROW_NUMBER() OVER (ORDER BY elo DESC) as rank,
    user_id,
    username,
    level,
    elo,
    wins,
    losses
FROM players
ORDER BY elo DESC
LIMIT 10;

-- Find inactive players (30+ days no login)
SELECT 
    user_id,
    username,
    last_login,
    NOW() - last_login as inactive_duration
FROM players
WHERE last_login < NOW() - INTERVAL '30 days'
ORDER BY last_login DESC;

-- Get player's Pokemon collection summary
SELECT 
    p.user_id,
    p.username,
    COUNT(poke.id) as total_caught,
    COUNT(CASE WHEN poke.is_shiny THEN 1 END) as shiny_count,
    COUNT(CASE WHEN poke.level >= 50 THEN 1 END) as high_level_count,
    ROUND(AVG(poke.level), 2) as avg_level,
    MAX(poke.level) as max_level
FROM players p
LEFT JOIN pokemon poke ON poke.player_id = p.user_id
WHERE p.user_id = $1
GROUP BY p.user_id, p.username;

-- Most common Pokemon species caught
SELECT 
    species_name,
    COUNT(*) as times_caught,
    ROUND(AVG(level), 2) as avg_level,
    COUNT(CASE WHEN is_shiny THEN 1 END) as shiny_catches
FROM pokemon
GROUP BY species_name
ORDER BY times_caught DESC
LIMIT 20;
```

### Pokemon Management

```sql
-- Get player's active team
SELECT 
    p.id,
    p.species_name,
    p.nickname,
    p.level,
    p.current_hp,
    p.max_hp,
    p.experience,
    p.nature,
    ARRAY_LENGTH(p.moves, 1) as move_count,
    p.is_shiny
FROM pokemon p
WHERE p.player_id = $1
AND p.id = ANY((SELECT active_team FROM players WHERE user_id = $1))
ORDER BY ARRAY_POSITION((SELECT active_team FROM players WHERE user_id = $1), p.id);

-- Update Pokemon after battle (heal/save)
UPDATE pokemon
SET 
    current_hp = $1,
    status = $2,
    experience = $3,
    updated_at = NOW()
WHERE id = $4
RETURNING *;

-- Heal all Pokemon in player's team
UPDATE pokemon
SET 
    current_hp = max_hp,
    status = NULL,
    updated_at = NOW()
WHERE player_id = $1
RETURNING id, species_name, current_hp, max_hp;

-- Find duplicate Pokemon (for trading)
SELECT 
    species_name,
    COUNT(*) as count,
    ARRAY_AGG(id) as pokemon_ids
FROM pokemon
WHERE player_id = $1
GROUP BY species_name
HAVING COUNT(*) > 1
ORDER BY count DESC;

-- Get Pokemon with specific moves
SELECT 
    id,
    species_name,
    nickname,
    level,
    moves
FROM pokemon
WHERE player_id = $1
AND $2 = ANY(moves)  -- $2 is move name
ORDER BY level DESC;

-- Shiny collection
SELECT 
    id,
    species_name,
    nickname,
    level,
    caught_at
FROM pokemon
WHERE player_id = $1
AND is_shiny = TRUE
ORDER BY level DESC;
```

### Battle Statistics

```sql
-- Player's battle history
SELECT 
    log_id,
    opponent_pokemon_species,
    opponent_level,
    player_level,
    winner_id,
    CASE WHEN winner_id = $1 THEN '✅ WIN' ELSE '❌ LOSS' END as result,
    exp_gained,
    coins_gained,
    created_at
FROM battle_log
WHERE player_user_id = $1
ORDER BY created_at DESC
LIMIT 50;

-- Battle statistics by region
SELECT 
    region,
    COUNT(*) as total_battles,
    COUNT(CASE WHEN winner_id = $1 THEN 1 END) as wins,
    COUNT(CASE WHEN winner_id != $1 AND winner_id IS NOT NULL THEN 1 END) as losses,
    ROUND(
        COUNT(CASE WHEN winner_id = $1 THEN 1 END)::FLOAT / 
        NULLIF(COUNT(*), 0) * 100, 2
    ) as win_rate,
    SUM(exp_gained) as total_xp,
    SUM(coins_gained) as total_coins
FROM battle_log
WHERE player_user_id = $1
GROUP BY region
ORDER BY total_battles DESC;

-- Recent battles (last 24 hours)
SELECT 
    bl.log_id,
    bl.player_user_id,
    pl.username as player_name,
    bl.opponent_id,
    po.username as opponent_name,
    bl.player_pokemon_species,
    bl.opponent_pokemon_species,
    bl.winner_id,
    bl.created_at
FROM battle_log bl
LEFT JOIN players pl ON bl.player_user_id = pl.user_id
LEFT JOIN players po ON bl.opponent_id = po.user_id
WHERE bl.created_at > NOW() - INTERVAL '24 hours'
ORDER BY bl.created_at DESC;

-- Toughest opponents (most wins against you)
SELECT 
    opponent_id,
    COUNT(*) as battles_against_them,
    COUNT(CASE WHEN winner_id = $1 THEN 1 END) as wins_vs_them,
    ROUND(
        COUNT(CASE WHEN winner_id = $1 THEN 1 END)::FLOAT /
        COUNT(*) * 100, 2
    ) as win_percentage
FROM battle_log
WHERE (player_user_id = $1 OR opponent_id = $1)
AND opponent_id IS NOT NULL
GROUP BY opponent_id
ORDER BY battles_against_them DESC
LIMIT 10;
```

### Trade System

```sql
-- Active trades waiting for response
SELECT 
    t.trade_id,
    i.username as initiated_by,
    a.username as awaiting_response,
    ip.species_name as offering,
    ap.species_name as requesting,
    t.created_at,
    NOW() - t.created_at as time_pending
FROM trading_history t
LEFT JOIN players i ON t.initiator_id = i.user_id
LEFT JOIN players a ON t.acceptor_id = a.user_id
LEFT JOIN pokemon ip ON t.initiator_pokemon_id = ip.id
LEFT JOIN pokemon ap ON t.acceptor_pokemon_id = ap.id
WHERE t.status = 'pending'
ORDER BY t.created_at DESC;

-- Completed trades for a player
SELECT 
    t.trade_id,
    CASE 
        WHEN t.initiator_id = $1 THEN 'Sent to: ' || p.username
        ELSE 'Received from: ' || p.username
    END as trade_type,
    CASE 
        WHEN t.initiator_id = $1 THEN ap.species_name
        ELSE ip.species_name
    END as pokemon_involved,
    t.updated_at
FROM trading_history t
LEFT JOIN players p ON CASE 
    WHEN t.initiator_id = $1 THEN t.acceptor_id 
    ELSE t.initiator_id 
END = p.user_id
LEFT JOIN pokemon ip ON t.initiator_pokemon_id = ip.id
LEFT JOIN pokemon ap ON t.acceptor_pokemon_id = ap.id
WHERE (t.initiator_id = $1 OR t.acceptor_id = $1)
AND t.status = 'completed'
ORDER BY t.updated_at DESC;
```

### Analytics & Admin

```sql
-- Daily active users
SELECT 
    DATE(last_login) as date,
    COUNT(DISTINCT user_id) as active_players,
    COUNT(DISTINCT CASE WHEN level > 5 THEN user_id END) as active_level5plus
FROM players
WHERE last_login > NOW() - INTERVAL '30 days'
GROUP BY DATE(last_login)
ORDER BY date DESC;

-- Player retention (login streaks)
SELECT 
    login_streak,
    COUNT(*) as players
FROM players
GROUP BY login_streak
ORDER BY login_streak DESC;

-- Revenue proxy: Average coins by level
SELECT 
    level,
    COUNT(*) as player_count,
    ROUND(AVG(coins), 2) as avg_coins,
    MAX(coins) as richest_player,
    MIN(coins) as poorest_player
FROM players
GROUP BY level
ORDER BY level DESC;

-- Progression funnel
SELECT 
    'All Players' as stage,
    COUNT(*) as count
FROM players
UNION ALL
SELECT 
    'Level 5+',
    COUNT(*)
FROM players
WHERE level >= 5
UNION ALL
SELECT 
    'Caught 10+ Pokemon',
    COUNT(*)
FROM players
WHERE pokemon_caught >= 10
UNION ALL
SELECT 
    'Level 20+',
    COUNT(*)
FROM players
WHERE level >= 20
ORDER BY count DESC;

-- Most valuable Pokemon (by how many players have them)
SELECT 
    species_name,
    COUNT(*) as caught_by_players,
    COUNT(DISTINCT player_id) as unique_players,
    COUNT(CASE WHEN is_shiny THEN 1 END) as shiny_versions,
    ROUND(AVG(level), 2) as avg_level
FROM pokemon
GROUP BY species_name
ORDER BY unique_players DESC
LIMIT 30;

-- Database size info
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

---

## QUICK FIX CODE SNIPPETS

### FIX #1: Catch Rate - Add to pokemon_model.py

**Location: `pokemon_model.py:40` (after moves extraction)**

```python
# BEFORE (line 41):
self.moves = api_data.get("moves", ["tackle", "scratch"])[:4]

# AFTER - Add this:
self.catch_rate = api_data.get("catch_rate", 45)  # Default 45 if missing
```

**Location: `bot.py:576-578` (in catch_pokemon handler)**

```python
# BEFORE:
catch_chance = catch_system.calculate_catch_chance(
    wild.current_hp, wild.max_hp, ball_type, wild.catch_rate
)

# AFTER - Fix argument order:
hp_percent = wild.current_hp / wild.max_hp
catch_chance = catch_system.calculate_catch_chance(
    hp_percent,      # as 0.0-1.0
    wild.level,
    wild.catch_rate, # now actually set
    ball_type
)
```

---

### FIX #2: XP Overflow - Patch pokemon_model.py

**Location: `pokemon_model.py:~170` (add_experience method)**

```python
# BEFORE:
def add_experience(self, amount: int):
    self.experience += amount
    if self.experience >= self.xp_required_for_next():
        self.level += 1
        self.experience = 0

# AFTER:
def add_experience(self, amount: int):
    self.experience += amount
    
    while self.experience >= self.xp_required_for_next():
        xp_required = self.xp_required_for_next()
        self.experience -= xp_required  # Carry remainder
        self.level += 1
        
        # Cap at level 100
        if self.level >= 100:
            self.level = 100
            self.experience = 0
            break
```

---

### FIX #3: Async HTTP - Convert requests to httpx

**Location: `database.py:1` (imports)**

```python
# BEFORE:
import requests

# AFTER:
import httpx  # pip install httpx
```

**Location: `database.py:39-42` (in load_player)**

```python
# BEFORE:
response = requests.get(
    f"{self.url}/rest/v1/players?user_id=eq.{user_id}",
    headers=self.headers
)

# AFTER - for async version:
async def load_player_async(self, user_id: int):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{self.url}/rest/v1/players?user_id=eq.{user_id}",
            headers=self.headers
        )
        return response.json()

# Then in bot.py:
p = await db.load_player_async(uid)  # Now awaitable
```

---

### FIX #4: Move Validation - Reject bad moves

**Location: `moves_database.py:get_move_info()`**

```python
# BEFORE:
def get_move_info(move_name: str):
    if move_name not in MOVES_DATABASE:
        return {
            "power": 60,
            "accuracy": 100,
            "type": "normal",
            "category": "physical"
        }
    return MOVES_DATABASE[move_name]

# AFTER:
class MoveNotFoundError(Exception):
    pass

def get_move_info(move_name: str) -> dict:
    if move_name not in MOVES_DATABASE:
        logger.error(f"Move requested but not found: {move_name}")
        raise MoveNotFoundError(f"Move '{move_name}' not in database")
    return MOVES_DATABASE[move_name]
```

**Location: `bot.py:use_move()` handler**

```python
# BEFORE:
move_data = get_move_info(move_name)

# AFTER:
try:
    move_data = get_move_info(move_name)
except MoveNotFoundError:
    logger.warning(f"Player {user_id} requested invalid move: {move_name}")
    await query.answer("❌ Move not found!", show_alert=True)
    return
```

---

### FIX #5: Damage Calculation Error Handling

**Location: `battle_system.py:calculate_damage()`**

```python
# BEFORE:
def calculate_damage(self, attacker, defender, move):
    try:
        # ... complex calc ...
    except Exception as e:
        return random.randint(1, 20)  # BAD

# AFTER:
def calculate_damage(self, attacker, defender, move) -> int:
    """Calculate damage, don't hide errors"""
    
    # Validate first
    if not hasattr(attacker, 'actual_stats'):
        logger.error(f"Attacker {attacker} has no actual_stats")
        raise ValueError("Invalid attacker")
    
    if not hasattr(defender, 'actual_stats'):
        logger.error(f"Defender {defender} has no actual_stats")
        raise ValueError("Invalid defender")
    
    try:
        # Safe stat access
        attack = attacker.actual_stats.get('atk', 1)
        defense = defender.actual_stats.get('def', 1)
        power = move.power if hasattr(move, 'power') else 50
        
        # Calculation
        base = (2 * power / 5 + 2) * attack / defense / 50 + 2
        
        # Randomness is intentional
        variance = random.randint(85, 100) / 100
        final = int(base * variance)
        
        return max(1, final)
    
    except (AttributeError, TypeError, ZeroDivisionError) as e:
        logger.error(f"Damage calc failed: {e}", exc_info=True)
        raise DamageCalculationError(f"Could not calculate damage: {e}")
```

---

### FIX #6: Add Missing Pagination Handler

**Location: `bot.py` (add after other handlers)**

```python
async def handle_poke_page(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handle collection pagination"""
    query = update.callback_query
    page = int(query.data.split("_")[2])
    
    user_id = query.from_user.id
    p = get_player(user_id, ctx)
    
    if not p or not p.pokemon_collection:
        await query.answer("No Pokemon!", show_alert=True)
        return
    
    # Paginate
    per_page = 10
    pages = (len(p.pokemon_collection) + per_page - 1) // per_page
    page = min(max(page, 1), pages)  # Clamp to valid range
    
    start = (page - 1) * per_page
    end = start + per_page
    page_pokemon = p.pokemon_collection[start:end]
    
    # Format
    text = f"📚 **COLLECTION** (Page {page}/{pages})\n\n"
    for i, poke in enumerate(page_pokemon, start + 1):
        emoji = "✨" if poke.is_shiny else ""
        text += f"{i}. **{poke.nickname}** Lv{poke.level} {emoji}\n"
    
    # Pagination buttons
    buttons = []
    if page > 1:
        buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"poke_page_{page-1}"))
    if page < pages:
        buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"poke_page_{page+1}"))
    
    if buttons:
        kb = InlineKeyboardMarkup([buttons])
    else:
        kb = None
    
    await query.edit_message_text(text, reply_markup=kb)

# Register it
app.add_handler(CallbackQueryHandler(handle_poke_page, pattern=r"^poke_page_\d+$"))
```

---

### FIX #7: Update Help Menu to Match Commands

**Location: `bot.py:224` (help_cmd function)**

```python
# BEFORE - Lists commands that don't exist:
async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    help_text = """⚡ **POSHOW COMMANDS**

/hunt - Find wild Pokemon
/stats <name> - View stats
/profile - Your profile
/team - Your team
...
```

# AFTER - Only lists working commands:
async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    help_text = """⚡ **POSHOW COMMANDS**

🎮 **CORE GAMEPLAY**
/hunt - Find and battle wild Pokémon
/myteam - View your active team
/mypokemon - View your collection
/stats <name> - Check Pokémon stats

🛒 **SHOP & ITEMS**
/shop - Buy Pokéballs and items
/inventory - Your items

⚔️ **PVP BATTLES** (Group Only)
/pvp - Challenge another trainer

👤 **PROFILE**
/profile - Your stats

🆘 **HELP**
/help - This menu
/menu - Main menu"""
    
    await update.message.reply_text(help_text)
```

---

## DEPLOYMENT CHECKLIST

Before deploying to production:

```
[ ] All 6 critical fixes applied
[ ] Database schema run (database/schema.sql), then /api/diagnose says ok
[ ] Environment variables set:
    - BOT_TOKEN
    - SUPABASE_URL
    - SUPABASE_KEY
[ ] Async HTTP client installed (httpx)
[ ] Tests pass:
    - Catch rate uses actual values
    - XP carries over on level-up
    - No blocking calls during hunts
    - Authentication verified
[ ] Logging configured for errors
[ ] Rate limiting enabled (avoid abuse)
[ ] Backup strategy documented
```

---

## MONITORING & ALERTS

### Key Metrics to Track

```sql
-- Slow queries (>1s)
SELECT query, mean_time FROM pg_stat_statements 
WHERE mean_time > 1000
ORDER BY mean_time DESC;

-- Failed bot commands (logs)
SELECT COUNT(*) FROM application_logs 
WHERE level = 'ERROR' 
AND timestamp > NOW() - INTERVAL '1 hour';

-- Active players right now
SELECT COUNT(DISTINCT user_id) FROM players 
WHERE last_login > NOW() - INTERVAL '5 minutes';
```

---

*Generated for Terminal Battler Project*  
*Version 4 - Telegram Bot Quick Fixes*
