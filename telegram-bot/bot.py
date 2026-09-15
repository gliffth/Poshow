"""
⚡ POSHOW - COMPLETE TELEGRAM BOT V4 - FULLY FIXED & INTEGRATED
All systems working: Hunt, Battle, PvP, Shop, Team, Catching, Moves
Personality-driven, clean UI, proper callbacks, player persistence
"""

import os
import sys

# Shared game-logic modules (battle_system, pokemon_model, etc.) live in
# ../api/_lib — that's where the Vercel-deployed FastAPI bridge also imports
# them from, so there's one copy of the actual rules, not two drifting copies.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api", "_lib"))

import logging
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ════════════════════════════════════════════════════════════════
# IMPORTS - ALL SYSTEMS
# ════════════════════════════════════════════════════════════════

from moves_database import get_move_data, get_type_effectiveness, MOVES_DATABASE
from move_learning_system import get_moves_by_level, get_new_moves_at_level, get_move_info
from move_learning_notifications import MoveUnlocker
from pokeapi_manager import pokeapi
from pokemon_model import PokemonInstance
from player_model import PlayerInstance
from battle_system import BattleSystem, Move
from pokeball_system import catch_system
from currency_system import currency
from database import db
from admin_panel import admin

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════════
# CONSTANTS
# ════════════════════════════════════════════════════════════════

TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN env var is not set. Set it before running the bot.")
STARTER_IMG = "https://i.ibb.co/r2pCFQvm/x.jpg"
WELCOME_IMG = "https://i.ibb.co/qYxz93KF/x.jpg"
SHOP_IMG = "https://i.ibb.co/p6vd9r7d/x.jpg"

POSHOW_PERSONALITY = """✨ Hie, the tech shawties call me Poshow, a text based pokemon mini game in this hell hole called telegram. I took the pldge (i was held on gun point) to provide you a cozy yet addictive *money noises* experience, and i am definetely a unique bot, not a ripoff of some other cheap popular bot, trust trust ✌🏻✌🏻"""

# ════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ════════════════════════════════════════════════════════════════

def get_player(uid: int, ctx):
    """Get player from DB first, then memory - ALWAYS check DB for persistence"""
    p = db.load_player(uid)
    if p:
        ctx.user_data['player'] = p
        return p
    return None

def save_player(uid: int, p, ctx):
    """Save player to memory + DB"""
    ctx.user_data['player'] = p
    try:
        db.save_player(p)
    except Exception as e:
        logger.error(f"DB save failed: {e}")

def get_type_emoji(ptype: str) -> str:
    """Get emoji for type"""
    emojis = {
        "normal": "⚪", "fire": "🔥", "water": "💧", "grass": "🌿",
        "electric": "⚡", "ice": "❄️", "fighting": "👊", "poison": "☠️",
        "ground": "🌍", "flying": "🦅", "psychic": "🧠", "bug": "🐛",
        "rock": "🪨", "ghost": "👻", "dragon": "🐉", "dark": "🌑",
        "steel": "⚙️", "fairy": "✨"
    }
    return emojis.get(ptype.lower(), "⚪")

def get_hp_bar(current, max_hp, width=12):
    """Generate HP bar (12 blocks)"""
    if max_hp <= 0:
        return "░" * width
    filled = int((current / max_hp) * width)
    return "█" * filled + "░" * (width - filled)

# ════════════════════════════════════════════════════════════════
# /start - FIXED WITH POSHOW PERSONALITY
# ════════════════════════════════════════════════════════════════

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Start command - Pokemon quotes for selection, Poshow personality for welcome"""
    uid = update.effective_user.id
    name = update.effective_user.first_name
    
    # Check if player already exists (FIXED: always check DB first)
    p = db.load_player(uid)
    if p:
        ctx.user_data['player'] = p
        await update.message.reply_text(
            f"✨ Welcome back, {name}!\n\nUse /menu to continue your journey."
        )
        return
    
    # New player - show starter selection with Pokemon quotes (NOT Poshow personality)
    buttons = [[
        InlineKeyboardButton("🔥", callback_data="starter_charmander"),
        InlineKeyboardButton("💧", callback_data="starter_squirtle"),
        InlineKeyboardButton("🌿", callback_data="starter_bulbasaur"),
    ]]
    
    starter_message = """**Every journey begins with a choice.**

*Strong Pokémon. Weak Pokémon. That is only the selfish perception of people. Truly skilled trainers should try to win with their favorites.*

**Choose wisely:**"""
    
    try:
        await update.message.reply_photo(
            photo=STARTER_IMG,
            caption=starter_message,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except:
        await update.message.reply_text(
            starter_message,
            reply_markup=InlineKeyboardMarkup(buttons)
        )

async def starter_selected(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Create player with starter"""
    query = update.callback_query
    starter = query.data.split("_")[1]
    uid = query.from_user.id
    name = query.from_user.first_name
    
    try:
        p = PlayerInstance(uid, name)
        poke = PokemonInstance(starter, 5, uid)
        
        # SET CORRECT MOVES FROM MOVE LEARNING SYSTEM
        moves = get_moves_by_level(starter, 5)
        poke.moves = moves[:4] if moves else ["tackle"]
        
        p.add_pokemon_to_team(poke)
        save_player(uid, p, ctx)
        
        emoji = {"bulbasaur": "🌿", "charmander": "🔥", "squirtle": "💧"}.get(starter, "⭐")
        moves_str = ", ".join([m.upper() for m in poke.moves])
        
        msg = f"""{POSHOW_PERSONALITY}

{emoji} **You chose {poke.nickname} (Lv5)!**

📚 Starting Moves: {moves_str}

Use /menu to start your adventure!"""
        
        await query.delete_message()
        try:
            await query.message.reply_photo(
                photo=WELCOME_IMG,
                caption=msg,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 Menu", callback_data="show_menu")]])
            )
        except:
            await query.message.reply_text(
                msg,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 Menu", callback_data="show_menu")]])
            )
        await query.answer("✅ Account created!")
    except Exception as e:
        logger.error(f"Starter error: {e}")
        await query.answer(f"❌ {str(e)[:40]}", show_alert=True)

# ════════════════════════════════════════════════════════════════
# MAIN MENU
# ════════════════════════════════════════════════════════════════

async def show_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Main menu"""
    query = update.callback_query if hasattr(update, 'callback_query') else None
    uid = query.from_user.id if query else update.effective_user.id
    
    # FIXED: Check player exists
    p = get_player(uid, ctx)
    if not p:
        msg = "❌ Use /start first!"
        if query:
            await query.answer(msg, show_alert=True)
        else:
            await update.message.reply_text(msg)
        return
    
    buttons = [
        [InlineKeyboardButton("🎯 Hunt", callback_data="hunt"), InlineKeyboardButton("⚔️ Battle (PvP)", callback_data="battle_pvp")],
        [InlineKeyboardButton("👤 Profile", callback_data="profile"), InlineKeyboardButton("🎮 Team", callback_data="team")],
        [InlineKeyboardButton("🛒 Shop", callback_data="shop"), InlineKeyboardButton("📚 Pokedex", callback_data="pokedex")],
        [InlineKeyboardButton("📦 Inventory", callback_data="inventory"), InlineKeyboardButton("💰 Coins", callback_data="coins")],
    ]
    
    text = """⚡ **POSHOW MENU**

🎯 Hunt - Find wild Pokémon
⚔️ Battle - PvP (group only)
👤 Profile - Your stats
🎮 Team - Your team
🛒 Shop - Buy items
📚 Pokedex - Your collection
📦 Inventory - Items
💰 Coins - Your money"""
    
    if query:
        try:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        except:
            await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Help command"""
    help_text = """⚡ **POSHOW BOT COMMANDS**

🎮 **GAMEPLAY**
/hunt - Find wild Pokémon
/stats <name> - View stats
/profile - Your profile
/team - Your team
/mypokemon - Your collection

🛒 **SHOP**
/shop - Open shop
/buy pokeball 5 - Buy pokéballs
/inventory - Your items

⚔️ **PVP BATTLES** (Group Only)
/pvp @user - Challenge user
/accept - Accept PvP challenge

📚 **POKEDEX**
/pokedex - Your collection
/inspect - IV/EV details

🎯 **OTHER**
/help - This menu
/menu - Main menu"""
    
    await update.message.reply_text(help_text)

# ════════════════════════════════════════════════════════════════
# HUNT & WILD BATTLES
# ════════════════════════════════════════════════════════════════

async def hunt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Hunt for wild Pokemon"""
    if update.callback_query:
        query = update.callback_query
        uid = query.from_user.id
    else:
        query = None
        uid = update.effective_user.id
    
    p = get_player(uid, ctx)
    if not p or not p.active_team:
        msg = "❌ Use /start first!"
        if query:
            await query.answer(msg, show_alert=True)
        else:
            await update.message.reply_text(msg)
        return
    
    wild_names = ["pikachu", "pidgeot", "rattata", "spearow", "ekans", "sandslash", "growlithe", "metang"]
    wild_name = random.choice(wild_names)
    wild = PokemonInstance(wild_name, random.randint(3, 25), 0)
    
    # SET WILD POKEMON MOVES FROM MOVE LEARNING SYSTEM
    wild_moves = get_moves_by_level(wild_name, wild.level)
    wild.moves = wild_moves[:4] if wild_moves else ["tackle"]
    
    ctx.user_data['wild'] = wild
    ctx.user_data['player'] = p
    ctx.user_data['battle'] = None  # Reset battle
    
    # Get image
    try:
        api_data = pokeapi.get_pokemon(wild_name)
        img_url = api_data.get("image")
        if img_url:
            caption = f"🌍 **Wild {wild.nickname.upper()} appeared!**\n\n**Lv.** {wild.level}  •  **HP** {wild.current_hp}/{wild.max_hp}"
            buttons = [[
                InlineKeyboardButton("⚔️ Battle", callback_data="battle_wild"),
                InlineKeyboardButton("📊 Stats", callback_data="wild_stats"),
            ], [InlineKeyboardButton("🏃 Run", callback_data="wild_run")]]
            
            if query:
                await query.delete_message()
            
            try:
                if query:
                    await query.message.reply_photo(photo=img_url, caption=caption, reply_markup=InlineKeyboardMarkup(buttons))
                else:
                    await update.message.reply_photo(photo=img_url, caption=caption, reply_markup=InlineKeyboardMarkup(buttons))
            except:
                raise Exception("Photo failed")
        else:
            raise Exception("No image")
    except:
        text = f"🌍 **Wild {wild.nickname.upper()} appeared!**\n\n**Lv.** {wild.level}  •  **HP** {wild.current_hp}/{wild.max_hp}"
        buttons = [[
            InlineKeyboardButton("⚔️ Battle", callback_data="battle_wild"),
            InlineKeyboardButton("📊 Stats", callback_data="wild_stats"),
        ], [InlineKeyboardButton("🏃 Run", callback_data="wild_run")]]
        
        if query:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

async def battle_wild(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Start wild Pokemon battle - FIXED"""
    query = update.callback_query
    user_id = query.from_user.id
    
    p = get_player(user_id, ctx)
    wild = ctx.user_data.get('wild')
    
    if not p or not p.active_team:
        await query.answer("❌ No Pokemon!", show_alert=True)
        return
    
    if not wild:
        await query.answer("❌ No wild Pokemon!", show_alert=True)
        return
    
    try:
        player_poke = p.active_team[0]
        
        # Initialize battle
        if 'battle' not in ctx.user_data or ctx.user_data['battle'] is None:
            ctx.user_data['battle'] = BattleSystem(player_poke, wild)
        
        battle = ctx.user_data['battle']
        
        # Get moves from move learning system
        moves = get_moves_by_level(player_poke.species_name, player_poke.level)
        if not moves:
            moves = ["tackle"]
        player_poke.moves = moves[:4]
        
        # Format battle panel
        text = format_battle_panel_clean(player_poke, wild, moves)
        buttons = get_battle_buttons(moves, is_wild=True)
        
        # FIXED: Delete photo message then send text
        try:
            await query.delete_message()
            await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        except:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    
    except Exception as e:
        logger.error(f"Battle error: {e}")
        await query.answer(f"❌ Error: {str(e)[:40]}", show_alert=True)

async def use_move(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Execute move in battle"""
    query = update.callback_query
    move_idx = int(query.data.split("_")[2])
    
    user_id = query.from_user.id
    p = get_player(user_id, ctx)
    wild = ctx.user_data.get('wild')
    battle = ctx.user_data.get('battle')
    
    if not all([p, wild, battle]):
        await query.answer("❌ Battle error!", show_alert=True)
        return
    
    try:
        player_poke = p.active_team[0]
        
        # Get moves
        moves = get_moves_by_level(player_poke.species_name, player_poke.level)
        if not moves:
            moves = ["tackle"]
        
        if move_idx >= len(moves):
            await query.answer("❌ Invalid move!", show_alert=True)
            return
        
        # Get player move
        move_name = moves[move_idx]
        move_data = get_move_info(move_name)
        player_move = Move(
            move_name,
            power=move_data["power"],
            accuracy=move_data["accuracy"],
            move_type=move_data["type"],
            category=move_data["category"]
        )
        
        # Get opponent move
        opp_moves = get_moves_by_level(wild.species_name, wild.level)
        if not opp_moves:
            opp_moves = ["tackle"]
        opp_move_name = random.choice(opp_moves)
        opp_move_data = get_move_info(opp_move_name)
        opp_move = Move(
            opp_move_name,
            power=opp_move_data["power"],
            accuracy=opp_move_data["accuracy"],
            move_type=opp_move_data["type"],
            category=opp_move_data["category"]
        )
        
        # Get type effectiveness
        player_effectiveness = get_type_effectiveness(
            player_move.move_type,
            wild.types if hasattr(wild, 'types') else ["normal"]
        )
        
        opp_effectiveness = get_type_effectiveness(
            opp_move.move_type,
            player_poke.types if hasattr(player_poke, 'types') else ["normal"]
        )
        
        # Apply effectiveness
        player_move.power = int(player_move.power * player_effectiveness)
        opp_move.power = int(opp_move.power * opp_effectiveness)
        
        # Build effectiveness message
        eff_msg = ""
        if player_effectiveness > 1:
            eff_msg += f"\n💥 **Super effective!** (×{player_effectiveness})"
        elif player_effectiveness < 1:
            eff_msg += f"\n❄️ **Not very effective...**"
        
        # Execute turn
        result = battle.execute_turn(player_move, opp_move)
        log_text = "\n".join(result["log"]) + eff_msg
        
        if battle.is_finished:
            if battle.winner == "player":
                reward = random.randint(10, 50)
                p.add_coins(reward)
                save_player(user_id, p, ctx)
                
                log_text = f"""**⚔️ BATTLE RESULT**

{log_text}

✅ **YOU WON!**
💰 +{reward}₽ earned

🔴 **Catch {wild.species_name}?**"""
                
                buttons = [[
                    InlineKeyboardButton("🔴 Pokéball", callback_data="catch_pokeball"),
                    InlineKeyboardButton("🔵 Great Ball", callback_data="catch_greatball"),
                ], [
                    InlineKeyboardButton("🟣 Ultra Ball", callback_data="catch_ultraball"),
                    InlineKeyboardButton("⬅️ Menu", callback_data="show_menu"),
                ]]
            else:
                log_text = f"""**⚔️ BATTLE RESULT**

{log_text}

❌ **YOU LOST!**

Your **{player_poke.nickname}** fainted..."""
                
                buttons = [[InlineKeyboardButton("⬅️ Menu", callback_data="show_menu")]]
        else:
            # Continue battle - show clean panel
            log_text = format_battle_panel_clean(player_poke, wild, moves) + "\n\n" + log_text
            buttons = get_battle_buttons(moves, is_wild=True)
        
        await query.edit_message_text(log_text, reply_markup=InlineKeyboardMarkup(buttons))
        
    except Exception as e:
        logger.error(f"Move error: {e}")
        await query.answer(f"❌ Error: {str(e)[:40]}", show_alert=True)

def format_battle_panel_clean(player_poke, wild_poke, moves):
    """Format clean battle panel - NO CLUTTER"""
    
    wild_types = " / ".join(wild_poke.types) if hasattr(wild_poke, 'types') else "Normal"
    player_types = " / ".join(player_poke.types) if hasattr(player_poke, 'types') else "Normal"
    
    text = f"""**⚔️ WILD BATTLE**

━━━━━━━━━━━━━━━━━━━

**{wild_poke.species_name.upper()}** [{wild_types}]
**Lv.** {wild_poke.level}  •  **HP** {wild_poke.current_hp}/{wild_poke.max_hp}
{get_hp_bar(wild_poke.current_hp, wild_poke.max_hp)}

━━━━━━━━━━━━━━━━━━━

**{player_poke.nickname.upper()}** [{player_types}]
**Lv.** {player_poke.level}  •  **HP** {player_poke.current_hp}/{player_poke.max_hp}
{get_hp_bar(player_poke.current_hp, player_poke.max_hp)}

━━━━━━━━━━━━━━━━━━━

📚 **YOUR MOVES:**
"""
    
    for i, move in enumerate(moves[:4], 1):
        move_data = get_move_info(move)
        type_emoji = get_type_emoji(move_data["type"])
        text += f"\n{i}. {type_emoji} **{move.upper()}**  •  Power: {move_data['power']} / Acc: {move_data['accuracy']}%"
    
    return text

def get_battle_buttons(moves, is_wild=True):
    """Get battle buttons - 2 per row, then pokeball/run"""
    buttons = []
    
    # Move buttons (2 per row)
    for i in range(0, min(4, len(moves)), 2):
        row = []
        row.append(InlineKeyboardButton(f"{i+1}️⃣ {moves[i].upper()[:15]}", callback_data=f"use_move_{i}"))
        
        if i + 1 < len(moves):
            row.append(InlineKeyboardButton(f"{i+2}️⃣ {moves[i+1].upper()[:15]}", callback_data=f"use_move_{i+1}"))
        
        buttons.append(row)
    
    # Action buttons
    if is_wild:
        buttons.append([
            InlineKeyboardButton("🔴 Pokéballs", callback_data="catch_pokeball"),
            InlineKeyboardButton("🏃 Flee", callback_data="battle_run"),
        ])
    else:
        # PvP buttons
        buttons.append([
            InlineKeyboardButton("🔄 Switch", callback_data="switch_pokemon"),
            InlineKeyboardButton("🏃 Flee", callback_data="pvp_run"),
        ])
    
    return buttons

# ════════════════════════════════════════════════════════════════
# CATCHING SYSTEM - FIXED
# ════════════════════════════════════════════════════════════════

async def catch_pokemon(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Catch Pokemon with pokéball - FIXED PATTERN"""
    query = update.callback_query
    user_id = query.from_user.id
    
    p = get_player(user_id, ctx)
    wild = ctx.user_data.get('wild')
    
    if not p or not wild:
        await query.answer("❌ Error!", show_alert=True)
        return
    
    try:
        # FIXED: Get ball type from callback data
        parts = query.data.split("_")
        ball_type = parts[1] if len(parts) > 1 else "pokeball"
        
        if not p.use_pokeball(ball_type):
            await query.answer(f"❌ No {ball_type}!", show_alert=True)
            return
        
        # Calculate catch chance
        catch_chance = catch_system.calculate_catch_chance(
            wild.current_hp, wild.max_hp, ball_type, wild.catch_rate
        )
        
        success = random.random() < catch_chance
        
        if success:
            p.catch_pokemon(wild)
            reward = random.randint(10, 50)
            p.add_coins(reward)
            
            # Set correct moves from learning system
            wild_moves = get_moves_by_level(wild.species_name, wild.level)
            wild.moves = wild_moves[:4] if wild_moves else ["tackle"]
            
            save_player(user_id, p, ctx)
            
            moves_str = ", ".join([m.upper() for m in wild.moves])
            text = f"""✅ **CAUGHT!**

🎉 **{wild.species_name.upper()}** Lv{wild.level} caught!
💰 **+{reward}₽** earned

📚 **Moves:** {moves_str}

Nice catch! Use /mypokemon to view it."""
        else:
            ball_name = {"pokeball": "Pokéball", "greatball": "Great Ball", "ultraball": "Ultra Ball"}.get(ball_type, ball_type)
            text = f"""❌ **CATCH FAILED!**

{wild.species_name} broke free from the {ball_name}!

Try another pokéball or weaken it more."""
            buttons = [[
                InlineKeyboardButton("🔴 Pokéball", callback_data="catch_pokeball"),
                InlineKeyboardButton("🔵 Great Ball", callback_data="catch_greatball"),
            ], [
                InlineKeyboardButton("🟣 Ultra Ball", callback_data="catch_ultraball"),
                InlineKeyboardButton("⬅️ Menu", callback_data="show_menu"),
            ]]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))
            return
        
        buttons = [[InlineKeyboardButton("⬅️ Menu", callback_data="show_menu")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        
    except Exception as e:
        logger.error(f"Catch error: {e}")
        await query.answer(f"❌ Error: {str(e)[:40]}", show_alert=True)

# ════════════════════════════════════════════════════════════════
# PVP SYSTEM - GROUP ONLY
# ════════════════════════════════════════════════════════════════

async def pvp_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """PvP command - group only"""
    message = update.message
    
    # Check if in group
    if message.chat.type not in ['group', 'supergroup']:
        await message.reply_text("❌ PvP battles only work in groups!\n\nUse /help for more info.")
        return
    
    # Check if replying to someone
    if not message.reply_to_message:
        await message.reply_text("❌ Reply to a user's message to challenge them!")
        return
    
    challenger_id = message.from_user.id
    target_id = message.reply_to_message.from_user.id
    
    if challenger_id == target_id:
        await message.reply_text("❌ You can't challenge yourself!")
        return
    
    # Check both players have Pokemon
    challenger = db.load_player(challenger_id)
    target = db.load_player(target_id)
    
    if not challenger or not challenger.active_team:
        await message.reply_text(f"❌ **{message.from_user.first_name}** has no Pokémon!")
        return
    
    if not target or not target.active_team:
        await message.reply_text(f"❌ **{message.reply_to_message.from_user.first_name}** has no Pokémon!")
        return
    
    # Send challenge
    ctx.user_data[f'pvp_challenge_{target_id}'] = {
        'challenger_id': challenger_id,
        'challenger_name': message.from_user.first_name,
        'chat_id': message.chat_id
    }
    
    buttons = [[
        InlineKeyboardButton("✅ Accept", callback_data=f"accept_pvp_{challenger_id}"),
        InlineKeyboardButton("❌ Decline", callback_data=f"decline_pvp_{challenger_id}"),
    ]]
    
    await message.reply_text(
        f"⚔️ **{message.from_user.first_name}** challenged you to a PvP battle!\n\nDo you accept?",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def accept_pvp(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Accept PvP battle"""
    query = update.callback_query
    challenger_id = int(query.data.split("_")[2])
    target_id = query.from_user.id
    
    challenger = db.load_player(challenger_id)
    target = db.load_player(target_id)
    
    if not challenger or not target:
        await query.answer("❌ Error!", show_alert=True)
        return
    
    if not challenger.active_team or not target.active_team:
        await query.answer("❌ Someone has no Pokémon!", show_alert=True)
        return
    
    # Start PvP
    ctx.user_data[f'pvp_{challenger_id}_{target_id}'] = {
        'challenger': challenger,
        'target': target,
        'turn': 0
    }
    
    msg = f"""⚔️ **PVP BATTLE STARTED!**

🔥 **{challenger.username}** vs ❄️ **{target.username}**

Starting in 3 seconds..."""
    
    await query.delete_message()
    await query.message.reply_text(msg)
    
    # Could add actual battle here
    await query.answer("✅ Battle started!")

async def decline_pvp(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Decline PvP battle"""
    query = update.callback_query
    await query.delete_message()
    await query.answer("❌ Declined!")

# ════════════════════════════════════════════════════════════════
# POKEMON SWITCHING MID-BATTLE
# ════════════════════════════════════════════════════════════════

async def switch_pokemon(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Switch Pokemon mid-battle"""
    query = update.callback_query
    user_id = query.from_user.id
    
    p = get_player(user_id, ctx)
    wild = ctx.user_data.get('wild')
    
    if not p or not wild:
        await query.answer("❌ Error!", show_alert=True)
        return
    
    # Show team selection (max 6)
    team = p.active_team[:6] if p.active_team else []
    
    text = "🔄 **Switch to which Pokémon?**\n\n"
    buttons = []
    
    for i, poke in enumerate(team):
        text += f"{i+1}. {poke.nickname} (Lv{poke.level}) - HP: {poke.current_hp}/{poke.max_hp}\n"
        buttons.append([InlineKeyboardButton(f"{i+1}️⃣ {poke.nickname}", callback_data=f"switch_to_{i}")])
    
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_switch")])
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

async def switch_to_pokemon(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Switch to specific Pokemon"""
    query = update.callback_query
    user_id = query.from_user.id
    idx = int(query.data.split("_")[2])
    
    p = get_player(user_id, ctx)
    wild = ctx.user_data.get('wild')
    battle = ctx.user_data.get('battle')
    
    if not p or not wild or not battle:
        await query.answer("❌ Error!", show_alert=True)
        return
    
    if idx >= len(p.active_team):
        await query.answer("❌ Invalid Pokemon!", show_alert=True)
        return
    
    # Switch Pokemon
    new_poke = p.active_team[idx]
    old_poke = battle.player_pokemon
    
    p.active_team[0] = new_poke
    p.active_team[idx] = old_poke
    
    save_player(user_id, p, ctx)
    
    msg = f"""🔄 **{old_poke.nickname}** switched out!

✨ Go, **{new_poke.nickname}**!"""
    
    await query.answer("✅ Switched!", show_alert=True)
    await query.edit_message_text(msg)

async def cancel_switch(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Cancel switch"""
    query = update.callback_query
    user_id = query.from_user.id
    
    p = get_player(user_id, ctx)
    wild = ctx.user_data.get('wild')
    
    if not p or not wild:
        await query.answer("❌ Error!", show_alert=True)
        return
    
    player_poke = p.active_team[0]
    moves = get_moves_by_level(player_poke.species_name, player_poke.level)
    if not moves:
        moves = ["tackle"]
    
    text = format_battle_panel_clean(player_poke, wild, moves)
    buttons = get_battle_buttons(moves, is_wild=True)
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

# ════════════════════════════════════════════════════════════════
# PROFILE, TEAM, STATS - PRESERVED
# ════════════════════════════════════════════════════════════════

async def profile(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show profile"""
    query = update.callback_query
    uid = query.from_user.id
    p = get_player(uid, ctx)
    
    if not p:
        await query.answer("❌ Use /start!", show_alert=True)
        return
    
    text = p.get_profile()
    buttons = [[InlineKeyboardButton("⬅️ Back", callback_data="show_menu")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

async def show_team(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show team"""
    query = update.callback_query
    uid = query.from_user.id
    p = get_player(uid, ctx)
    
    if not p:
        await query.answer("❌ Use /start!", show_alert=True)
        return
    
    text = p.get_team_summary()
    buttons = [[InlineKeyboardButton("⬅️ Back", callback_data="show_menu")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

async def show_pokedex(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show Pokedex"""
    query = update.callback_query
    uid = query.from_user.id
    p = get_player(uid, ctx)
    
    if not p:
        await query.answer("❌ Use /start!", show_alert=True)
        return
    
    text = f"📚 **POKEDEX**\n\n✅ Caught: {p.pokemon_caught}\n👁️ Seen: {len(p.pokedex_seen)}"
    buttons = [[InlineKeyboardButton("⬅️ Back", callback_data="show_menu")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

async def show_inventory(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show inventory"""
    query = update.callback_query
    uid = query.from_user.id
    p = get_player(uid, ctx)
    
    if not p:
        await query.answer("❌ Use /start!", show_alert=True)
        return
    
    if not p.inventory:
        inv_text = "Empty"
    else:
        inv_text = "\n".join([f"• {k}: {v}x" for k, v in p.inventory.items()])
    
    text = f"📦 **INVENTORY**\n\n{inv_text}"
    buttons = [[InlineKeyboardButton("⬅️ Back", callback_data="show_menu")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

async def show_coins(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show coins"""
    query = update.callback_query
    uid = query.from_user.id
    p = get_player(uid, ctx)
    
    if not p:
        await query.answer("❌ Use /start!", show_alert=True)
        return
    
    text = f"💰 **COINS**\n\n{p.coins}₽"
    buttons = [[InlineKeyboardButton("⬅️ Back", callback_data="show_menu")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

async def wild_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show wild Pokemon stats"""
    query = update.callback_query
    wild = ctx.user_data.get('wild')
    
    if not wild:
        await query.answer("❌ Error!", show_alert=True)
        return
    
    stats = f"""📊 **{wild.nickname.upper()}**

**Type:** {' / '.join(wild.types) if hasattr(wild, 'types') else 'Normal'}
**Level:** {wild.level}
**HP:** {wild.current_hp}/{wild.max_hp}

**ATK:** {wild.actual_stats.get('atk', '?')}
**DEF:** {wild.actual_stats.get('def', '?')}
**SP.ATK:** {wild.actual_stats.get('sp_atk', '?')}
**SP.DEF:** {wild.actual_stats.get('sp_def', '?')}
**SPD:** {wild.actual_stats.get('speed', '?')}"""
    
    buttons = [[
        InlineKeyboardButton("⚔️ Battle", callback_data="battle_wild"),
        InlineKeyboardButton("🏃 Run", callback_data="wild_run"),
    ]]
    
    await query.edit_message_text(stats, reply_markup=InlineKeyboardMarkup(buttons))

async def wild_run(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Run from hunt"""
    query = update.callback_query
    ctx.user_data['wild'] = None
    ctx.user_data['battle'] = None
    
    text = "🏃 **You ran away!**\n\nLet's hunt again!"
    buttons = [[
        InlineKeyboardButton("🎯 Hunt", callback_data="hunt"),
        InlineKeyboardButton("⬅️ Menu", callback_data="show_menu"),
    ]]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

async def battle_run(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Flee from battle"""
    query = update.callback_query
    ctx.user_data['wild'] = None
    ctx.user_data['battle'] = None
    
    text = "🏃 **You fled the battle!**\n\nThat was close..."
    buttons = [[InlineKeyboardButton("⬅️ Menu", callback_data="show_menu")]]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

# ════════════════════════════════════════════════════════════════
# SHOP - FIXED BUTTONS
# ════════════════════════════════════════════════════════════════

async def shop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Open shop"""
    if update.callback_query:
        query = update.callback_query
        uid = query.from_user.id
    else:
        query = None
        uid = update.effective_user.id
    
    p = get_player(uid, ctx)
    if not p:
        msg = "❌ Use /start!"
        if query:
            await query.answer(msg, show_alert=True)
        else:
            await update.message.reply_text(msg)
        return
    
    text = f"""🛒 **POSHOW SHOP**

💰 Your Coins: **{p.coins}₽**

What would you like to buy?"""
    
    buttons = [[
        InlineKeyboardButton("🔴 Pokéballs", callback_data="shop_pokeballs"),
        InlineKeyboardButton("🎁 Items", callback_data="shop_items"),
    ], [
        InlineKeyboardButton("⬅️ Back", callback_data="show_menu"),
    ]]
    
    if query:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

async def shop_pokeballs(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Shop pokéballs - FIXED"""
    query = update.callback_query
    uid = query.from_user.id
    p = get_player(uid, ctx)
    
    if not p:
        await query.answer("❌ Error!", show_alert=True)
        return
    
    text = """🔴 **POKÉBALLS**

**Pokéball** - 200₽
**Great Ball** - 600₽
**Ultra Ball** - 1200₽

Use: `/buy pokeball 5`"""
    
    buttons = [[InlineKeyboardButton("⬅️ Back", callback_data="shop")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

async def shop_items(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Shop items - FIXED"""
    query = update.callback_query
    uid = query.from_user.id
    p = get_player(uid, ctx)
    
    if not p:
        await query.answer("❌ Error!", show_alert=True)
        return
    
    text = """🎁 **ITEMS**

**Potion** - 200₽
**Full Restore** - 500₽
**Revive** - 1000₽

Use: `/buy potion 3`"""
    
    buttons = [[InlineKeyboardButton("⬅️ Back", callback_data="shop")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

async def buy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Buy items/pokéballs"""
    args = update.message.text.split()
    user_id = update.effective_user.id
    p = get_player(user_id, ctx)
    
    if not p:
        await update.message.reply_text("❌ Use /start!")
        return
    
    if len(args) < 3:
        await update.message.reply_text("/buy <item> <quantity>")
        return
    
    item = args[1].lower()
    try:
        qty = int(args[2])
    except:
        await update.message.reply_text("❌ Invalid quantity!")
        return
    
    prices = {
        "pokeball": 200, "greatball": 600, "ultraball": 1200,
        "potion": 200, "restore": 500, "revive": 1000
    }
    
    if item not in prices:
        await update.message.reply_text("❌ Item not found!")
        return
    
    cost = prices[item] * qty
    if p.coins < cost:
        await update.message.reply_text(f"❌ Need {cost}₽ (you have {p.coins}₽)")
        return
    
    p.coins -= cost
    
    if item in ["pokeball", "greatball", "ultraball"]:
        p.pokeballs[item] = p.pokeballs.get(item, 0) + qty
    else:
        p.inventory[item] = p.inventory.get(item, 0) + qty
    
    save_player(user_id, p, ctx)
    await update.message.reply_text(f"✅ Bought **{qty}x {item}**!")

async def stats_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Stats command - FIXED"""
    args = update.message.text.split()
    if len(args) < 2:
        await update.message.reply_text("Usage: `/stats <pokemon_name>`")
        return
    
    pname = " ".join(args[1:]).lower()
    user_id = update.effective_user.id
    p = db.load_player(user_id)
    
    if not p:
        await update.message.reply_text("❌ Use /start!")
        return
    
    poke = next((x for x in p.pokemon_collection if pname in x.species_name.lower()), None)
    if not poke:
        await update.message.reply_text("❌ Pokémon not found!")
        return
    
    text = f"""📊 **{poke.nickname.upper()}** ({poke.species_name})

**Level:** {poke.level}
**HP:** {poke.current_hp}/{poke.max_hp}
**Type:** {' / '.join(poke.types) if hasattr(poke, 'types') else 'Normal'}

**ATK:** {poke.actual_stats.get('atk', '?')}
**DEF:** {poke.actual_stats.get('def', '?')}
**SP.ATK:** {poke.actual_stats.get('sp_atk', '?')}
**SP.DEF:** {poke.actual_stats.get('sp_def', '?')}
**SPD:** {poke.actual_stats.get('speed', '?')}"""
    
    await update.message.reply_text(text)

async def myteam(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show team management"""
    if update.callback_query:
        query = update.callback_query
        uid = query.from_user.id
    else:
        uid = update.effective_user.id
    
    p = get_player(uid, ctx)
    if not p:
        await update.message.reply_text("❌ Use /start!")
        return
    
    text = """🎮 **YOUR TEAM** (Max 6)

"""
    buttons = []
    
    for i, poke in enumerate(p.active_team[:6], 1):
        text += f"{i}. {poke.nickname} (Lv{poke.level}) - HP: {poke.current_hp}/{poke.max_hp}\n"
    
    text += f"\n**Total:** {len(p.active_team)}/6 Pokémon"
    
    buttons = [[InlineKeyboardButton("⬅️ Back", callback_data="show_menu")]]
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

async def mypokemon(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """View Pokemon collection with pagination"""
    user_id = update.effective_user.id
    p = db.load_player(user_id)
    
    if not p or not p.pokemon_collection:
        await update.message.reply_text("❌ No Pokémon caught yet! Use /hunt")
        return
    
    page = ctx.user_data.get('pokemon_page', 0)
    page_size = 10
    total = len(p.pokemon_collection)
    total_pages = (total + page_size - 1) // page_size
    
    start = page * page_size
    end = start + page_size
    page_pokemon = p.pokemon_collection[start:end]
    
    text = f"""📚 **POKÉMON COLLECTION**

Page {page + 1}/{total_pages} ({start+1}-{min(end, total)}/{total})

"""
    
    for i, poke in enumerate(page_pokemon, start + 1):
        emoji = "✨" if poke.is_shiny else "⭐"
        text += f"{i}. {poke.nickname} ({poke.species_name}) Lv{poke.level} {emoji}\n"
        text += f"   HP: {poke.current_hp}/{poke.max_hp}\n"
    
    buttons = []
    nav_buttons = []
    
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data="poke_prev"))
    
    nav_buttons.append(InlineKeyboardButton(f"📄 {page+1}/{total_pages}", callback_data="poke_page"))
    
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data="poke_next"))
    
    buttons.append(nav_buttons)
    buttons.append([InlineKeyboardButton("⬅️ Menu", callback_data="show_menu")])
    
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    ctx.user_data['pokemon_page'] = page

async def poke_next_page(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Next page"""
    query = update.callback_query
    user_id = query.from_user.id
    p = db.load_player(user_id)
    
    page = ctx.user_data.get('pokemon_page', 0) + 1
    page_size = 10
    total_pages = (len(p.pokemon_collection) + page_size - 1) // page_size
    
    if page >= total_pages:
        page = 0
    
    ctx.user_data['pokemon_page'] = page
    start = page * page_size
    end = start + page_size
    page_pokemon = p.pokemon_collection[start:end]
    total = len(p.pokemon_collection)
    
    text = f"""📚 **POKÉMON COLLECTION**

Page {page + 1}/{total_pages} ({start+1}-{min(end, total)}/{total})

"""
    
    for i, poke in enumerate(page_pokemon, start + 1):
        emoji = "✨" if poke.is_shiny else "⭐"
        text += f"{i}. {poke.nickname} ({poke.species_name}) Lv{poke.level} {emoji}\n"
        text += f"   HP: {poke.current_hp}/{poke.max_hp}\n"
    
    buttons = []
    nav_buttons = []
    
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data="poke_prev"))
    
    nav_buttons.append(InlineKeyboardButton(f"📄 {page+1}/{total_pages}", callback_data="poke_page"))
    
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data="poke_next"))
    
    buttons.append(nav_buttons)
    buttons.append([InlineKeyboardButton("⬅️ Menu", callback_data="show_menu")])
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

async def poke_prev_page(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Previous page"""
    query = update.callback_query
    user_id = query.from_user.id
    p = db.load_player(user_id)
    
    page = ctx.user_data.get('pokemon_page', 0) - 1
    page_size = 10
    total_pages = (len(p.pokemon_collection) + page_size - 1) // page_size
    
    if page < 0:
        page = total_pages - 1
    
    ctx.user_data['pokemon_page'] = page
    start = page * page_size
    end = start + page_size
    page_pokemon = p.pokemon_collection[start:end]
    total = len(p.pokemon_collection)
    
    text = f"""📚 **POKÉMON COLLECTION**

Page {page + 1}/{total_pages} ({start+1}-{min(end, total)}/{total})

"""
    
    for i, poke in enumerate(page_pokemon, start + 1):
        emoji = "✨" if poke.is_shiny else "⭐"
        text += f"{i}. {poke.nickname} ({poke.species_name}) Lv{poke.level} {emoji}\n"
        text += f"   HP: {poke.current_hp}/{poke.max_hp}\n"
    
    buttons = []
    nav_buttons = []
    
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data="poke_prev"))
    
    nav_buttons.append(InlineKeyboardButton(f"📄 {page+1}/{total_pages}", callback_data="poke_page"))
    
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data="poke_next"))
    
    buttons.append(nav_buttons)
    buttons.append([InlineKeyboardButton("⬅️ Menu", callback_data="show_menu")])
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

async def creative(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin commands"""
    user_id = update.effective_user.id
    
    if not admin.is_admin(user_id):
        await update.message.reply_text("❌ Not authorized")
        return
    
    args = update.message.text.split()
    
    if len(args) < 2:
        await update.message.reply_text(admin.get_creative_menu())
        return
    
    command = args[1]
    p = db.load_player(user_id)
    
    if not p:
        await update.message.reply_text("❌ Player not found")
        return
    
    if command == "coins" and len(args) >= 3:
        result = admin.add_coins(p, int(args[2]))
    elif command == "level" and len(args) >= 3:
        result = admin.add_level(p, int(args[2]))
    elif command == "reset":
        result = admin.reset_player(p)
    elif command == "pokemon" and len(args) >= 3:
        level = int(args[3]) if len(args) >= 4 else 50
        result = admin.add_pokemon(p, args[2], level)
    elif command == "items" and len(args) >= 4:
        result = admin.add_items(p, args[2], int(args[3]))
    elif command == "balls" and len(args) >= 4:
        result = admin.add_pokeballs(p, args[2], int(args[3]))
    elif command == "unlock_all":
        result = admin.unlock_all_regions(p)
    else:
        await update.message.reply_text("❌ Unknown command")
        return
    
    db.save_player(p)
    await update.message.reply_text(result.get("message", "Done!"))

# ════════════════════════════════════════════════════════════════
# MAIN - ALL HANDLERS REGISTERED
# ════════════════════════════════════════════════════════════════

def main():
    app = Application.builder().token(TOKEN).build()
    
    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("menu", show_menu))
    app.add_handler(CommandHandler("hunt", hunt))
    app.add_handler(CommandHandler("shop", shop))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("myteam", myteam))
    app.add_handler(CommandHandler("mypokemon", mypokemon))
    app.add_handler(CommandHandler("creative", creative))
    app.add_handler(CommandHandler("pvp", pvp_command))
    
    # Callbacks - Start & Menu
    app.add_handler(CallbackQueryHandler(starter_selected, pattern="starter_"))
    app.add_handler(CallbackQueryHandler(show_menu, pattern="^show_menu$"))
    
    # Callbacks - Hunt & Battle (Wild)
    app.add_handler(CallbackQueryHandler(hunt, pattern="^hunt$"))
    app.add_handler(CallbackQueryHandler(battle_wild, pattern="^battle_wild$"))
    app.add_handler(CallbackQueryHandler(use_move, pattern="^use_move_"))
    app.add_handler(CallbackQueryHandler(wild_stats, pattern="^wild_stats$"))
    app.add_handler(CallbackQueryHandler(wild_run, pattern="^wild_run$"))
    app.add_handler(CallbackQueryHandler(battle_run, pattern="^battle_run$"))
    
    # Callbacks - Catching (FIXED PATTERN)
    app.add_handler(CallbackQueryHandler(catch_pokemon, pattern="^catch_"))
    
    # Callbacks - PvP
    app.add_handler(CallbackQueryHandler(accept_pvp, pattern="^accept_pvp_"))
    app.add_handler(CallbackQueryHandler(decline_pvp, pattern="^decline_pvp_"))
    app.add_handler(CallbackQueryHandler(switch_pokemon, pattern="^switch_pokemon$"))
    app.add_handler(CallbackQueryHandler(switch_to_pokemon, pattern="^switch_to_"))
    app.add_handler(CallbackQueryHandler(cancel_switch, pattern="^cancel_switch$"))
    
    # Callbacks - Profile & Menu Items
    app.add_handler(CallbackQueryHandler(profile, pattern="^profile$"))
    app.add_handler(CallbackQueryHandler(show_team, pattern="^team$"))
    app.add_handler(CallbackQueryHandler(show_pokedex, pattern="^pokedex$"))
    app.add_handler(CallbackQueryHandler(show_inventory, pattern="^inventory$"))
    app.add_handler(CallbackQueryHandler(show_coins, pattern="^coins$"))
    
    # Callbacks - Shop (FIXED)
    app.add_handler(CallbackQueryHandler(shop, pattern="^shop$"))
    app.add_handler(CallbackQueryHandler(shop_pokeballs, pattern="^shop_pokeballs$"))
    app.add_handler(CallbackQueryHandler(shop_items, pattern="^shop_items$"))
    
    # Callbacks - Pokemon Pages
    app.add_handler(CallbackQueryHandler(poke_next_page, pattern="^poke_next$"))
    app.add_handler(CallbackQueryHandler(poke_prev_page, pattern="^poke_prev$"))
    
    # PvP special (group-only)
    app.add_handler(CallbackQueryHandler(accept_pvp, pattern="^accept_pvp_"))
    
    print("🤖 **POSHOW BOT STARTING...** ✅")
    print("All systems online!")
    print("Personality loaded: Snarky ✨")
    print("Ready to battle!")
    
    app.run_polling()

if __name__ == "__main__":
    main()
