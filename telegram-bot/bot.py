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
import accounts
from admin_panel import admin
from route_encounters import EncounterSystem
from abilities_system import AbilitySystem
from daily_boss_system import daily_boss_system
from exp_all_system import ExpAllItem
import boss_battle
import gym_system
import avatars
import onboarding
import journey

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════════
# CONSTANTS
# ════════════════════════════════════════════════════════════════

if db is None:
    raise RuntimeError("SUPABASE_URL and SUPABASE_KEY env vars are not set. Set them before running the bot.")
_web_accounts = accounts.AccountService(db.url, db.key)   # for "Continue with Telegram" on the website

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

def _web_code_from_args(ctx) -> str:
    """`/start web_ABCD1234` (the deep link the website opens) -> "ABCD1234"."""
    args = getattr(ctx, "args", None) or []
    if args and args[0].startswith("web_"):
        return args[0][4:].upper()
    return ""

async def _confirm_web_login(update, ctx, code: str) -> bool:
    """Tell the website this Telegram user is who is logging in."""
    user = update.effective_user
    try:
        done = _web_accounts.confirm_telegram_login(code, user.id, user.first_name or "TRAINER")
    except Exception as e:
        logger.error(f"web login confirm failed: {e}")
        done = False
    return done

async def weblogin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """/weblogin CODE — manual fallback when the deep link didn't open the bot"""
    parts = (update.message.text or "").split()
    if len(parts) < 2:
        await update.message.reply_text("Usage: /weblogin CODE\n\nGet the code on the website: Login → Continue with Telegram.")
        return
    uid = update.effective_user.id
    if not db.load_player(uid):
        await update.message.reply_text("Send /start first to create your trainer, then try /weblogin again.")
        return
    if await _confirm_web_login(update, ctx, parts[1].upper()):
        await update.message.reply_text("✅ Website login confirmed! Go back to the site — it will sign you in.")
    else:
        await update.message.reply_text("❌ That code is invalid or expired. Get a fresh one on the website.")

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Start command - Pokemon quotes for selection, Poshow personality for welcome"""
    uid = update.effective_user.id
    name = update.effective_user.first_name
    web_code = _web_code_from_args(ctx)
    
    # Check if player already exists (FIXED: always check DB first)
    p = db.load_player(uid)
    if p:
        ctx.user_data['player'] = p
        if web_code:
            if await _confirm_web_login(update, ctx, web_code):
                await update.message.reply_text(
                    f"✅ Website login confirmed, {name}!\n\nGo back to the site — it will sign you in. "
                    "Your team and progress are shared between the bot and the website."
                )
            else:
                await update.message.reply_text("❌ That login code is invalid or expired. Get a fresh one on the website.")
            return
        await update.message.reply_text(
            f"✨ Welcome back, {name}!\n\nUse /menu to continue your journey."
        )
        return

    if web_code:
        # new Telegram player arriving from the website: confirm the login now (the site will then
        # offer region + starter selection itself), and also let them pick a starter here
        if await _confirm_web_login(update, ctx, web_code):
            await update.message.reply_text(
                "✅ Website login confirmed! Go back to the site to pick your region and starter.\n\n"
                "(You can also choose a Kanto starter right here.)"
            )
    
    # New player: avatar -> region -> starter -> professor
    await _ask_avatar(update.message)

async def _ask_avatar(message):
    names = avatars.list_avatars()
    buttons = [[InlineKeyboardButton(f"{i + 1}. {a['name']}", callback_data=f"av_{a['id']}")
                for i, a in enumerate(names[row:row + 3], start=row)] for row in (0, 3)]
    caption = ("**Every journey begins with a choice.**\n\n"
               "*Strong Pokémon. Weak Pokémon. That is only the selfish perception of people. "
               "Truly skilled trainers should try to win with their favorites.*\n\n"
               "**First — who are you?** Choose your trainer:")
    try:
        await message.reply_photo(photo=avatars.render_sheet(), caption=caption, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception:
        await message.reply_text(caption, reply_markup=InlineKeyboardMarkup(buttons))

async def avatar_selected(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    avatar_id = query.data[len("av_"):]
    if not avatars.is_valid(avatar_id):
        await query.answer("❌ Unknown trainer!", show_alert=True)
        return
    if db.load_player(query.from_user.id):
        await query.answer("You already have a trainer — use /menu.", show_alert=True)
        return
    ctx.user_data['avatar'] = avatar_id
    await query.answer(f"✅ {avatars.AVATARS[avatar_id]['name']}")
    regions = list(onboarding.STARTERS)
    rows = [[InlineKeyboardButton(f"{onboarding.REGION_NAMES[r]}", callback_data=f"rg_{r}") for r in regions[i:i + 3]]
            for i in range(0, len(regions), 3)]
    text = "🗺️ **Where does your journey begin?**\n\nPick your home region. (Kanto has a full journey with gyms and the Elite Four; the others are still being mapped.)"
    try:
        await query.message.reply_photo(photo=avatars.render_png(avatar_id, 6), caption=text, reply_markup=InlineKeyboardMarkup(rows))
    except Exception:
        await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(rows))
    try:
        await query.delete_message()
    except Exception:
        pass

async def region_selected(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    region = query.data[len("rg_"):]
    trio = onboarding.STARTERS.get(region)
    if not trio:
        await query.answer("❌ Unknown region!", show_alert=True)
        return
    await query.answer(onboarding.REGION_NAMES[region])
    prof = onboarding.PROFESSORS.get(region, "the Professor")
    buttons = [[InlineKeyboardButton(f"{onboarding.STARTER_EMOJI[i]} {sp.title()}", callback_data=f"pk_{region}_{sp}")
                for i, (sp, _) in enumerate(trio)]]
    buttons.append([InlineKeyboardButton("⬅️ Change region", callback_data="rg_back")])
    text = (f"🔬 **Professor {prof}:**\n\"Welcome to {onboarding.REGION_NAMES[region]}! "
            f"Your journey is about to begin. Choose the Pokémon that will travel with you.\"\n\n**This choice is permanent.**")
    try:
        await query.edit_message_caption(caption=text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception:
        try:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        except Exception as e:
            logger.error(f"region_selected edit failed: {e}")

async def region_back(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    regions = list(onboarding.STARTERS)
    rows = [[InlineKeyboardButton(f"{onboarding.REGION_NAMES[r]}", callback_data=f"rg_{r}") for r in regions[i:i + 3]]
            for i in range(0, len(regions), 3)]
    text = "🗺️ **Where does your journey begin?**"
    try:
        await query.edit_message_caption(caption=text, reply_markup=InlineKeyboardMarkup(rows))
    except Exception:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(rows))

async def _finish_onboarding(query, ctx, region: str, species: str):
    uid = query.from_user.id
    name = query.from_user.first_name
    if db.load_player(uid):
        await query.answer("You already chose a starter — use /menu.", show_alert=True)
        return
    p = PlayerInstance(uid, name)
    try:
        poke = onboarding.create_player_with_starter(p, region, species, ctx.user_data.get('avatar'))
    except onboarding.OnboardingError as e:
        await query.answer(f"❌ {e}", show_alert=True)
        return
    save_player(uid, p, ctx)
    ctx.user_data['player'] = p

    emoji = dict(enumerate(onboarding.STARTER_EMOJI.values()))
    trio = [sp for sp, _ in onboarding.STARTERS[region]]
    e = emoji.get(trio.index(species), "⭐")
    moves_str = ", ".join(m.upper() for m in poke.moves)
    prof = onboarding.PROFESSORS.get(region, "the Professor")
    where = journey.state(p)
    if where["mode"] == "journey":
        goal = f"📍 You're in **{where['location']['name']}**.\n🎯 {where['objective']}"
    else:
        goal = "📍 This region's journey map is still being drawn — explore its routes with 🗺️ Routes."
    msg = f"""{POSHOW_PERSONALITY}

{e} **You chose {poke.nickname} (Lv5)!**
🔬 *Professor {prof}: "Take good care of each other."*

📚 Starting moves: {moves_str}

{goal}"""
    buttons = [[InlineKeyboardButton("🧭 Begin journey", callback_data="journey"),
                InlineKeyboardButton("🚀 Menu", callback_data="show_menu")]]
    try:
        await query.delete_message()
    except Exception:
        pass
    try:
        await query.message.reply_photo(photo=WELCOME_IMG, caption=msg, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception:
        await query.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(buttons))

async def pick_starter(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        _, region, species = query.data.split("_", 2)
    except ValueError:
        await query.answer("❌ Bad choice!", show_alert=True)
        return
    await _finish_onboarding(query, ctx, region, species)

async def starter_selected(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Old-style "starter_<name>" buttons from messages sent before regions existed -> Kanto."""
    query = update.callback_query
    await _finish_onboarding(query, ctx, "kanto", query.data.split("_")[1])

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
        [InlineKeyboardButton("🧭 Journey", callback_data="journey"), InlineKeyboardButton("🗺️ Routes", callback_data="routes")],
        [InlineKeyboardButton("👹 Daily Boss", callback_data="boss"), InlineKeyboardButton("🏟️ Battle Gym", callback_data="gym")],
    ]
    
    text = """⚡ **POSHOW MENU**

🎯 Hunt - Find wild Pokémon
⚔️ Battle - PvP (group only)
👤 Profile - Your stats
🎮 Team - Your team
🛒 Shop - Buy items
📚 Pokedex - Your collection
📦 Inventory - Items
💰 Coins - Your money
🧭 Journey - Travel, gyms, the League
🗺️ Routes - Pick where to hunt (regions without a map)
👹 Daily Boss - One tough fight per day
🏟️ Battle Gym - Endless floors, badges and BP"""
    
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
/journey - Your journey: travel, gyms, rival
/hunt - Find wild Pokémon
/routes - Choose a hunting route
/boss - Today's boss fight
/gym - Battle Gym (endless floors)
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
    
    route_id = ctx.user_data.get('hunt_route')
    if journey.ensure_story(p)["mode"] == "journey":
        # on a journey the LOCATION decides what you meet
        route_id = journey.current_encounter(p)
        if not route_id:
            msg = "🏘️ No wild Pokémon in town — head out to a route (🧭 Journey)."
            if query:
                await query.answer(msg, show_alert=True)
            else:
                await update.message.reply_text(msg)
            return
        wild_name, wild_level = EncounterSystem.spawn_in_route(route_id)
    elif route_id and EncounterSystem.has_route(route_id):
        wild_name, wild_level = EncounterSystem.spawn_in_route(route_id)
    else:
        # default "wild grass" mix (unchanged from before routes existed)
        wild_names = ["pikachu", "pidgeot", "rattata", "spearow", "ekans", "sandslash", "growlithe", "metang"]
        wild_name = random.choice(wild_names)
        wild_level = random.randint(3, 25)
    wild = PokemonInstance(wild_name, wild_level, 0)
    
    # SET WILD POKEMON MOVES FROM MOVE LEARNING SYSTEM
    wild_moves = get_moves_by_level(wild_name, wild.level)
    wild.moves = wild_moves[:4] if wild_moves else ["tackle"]
    
    ctx.user_data['wild'] = wild
    ctx.user_data['player'] = p
    ctx.user_data['battle'] = None  # Reset battle
    ctx.user_data.pop('gym', None)
    
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
        buttons = get_battle_buttons(moves, is_wild=True, **_battle_button_opts(p, wild, ctx))
        
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
        if (getattr(wild, "is_boss", False) or getattr(wild, "story_ref", None)) and wild.moves:
            opp_moves = list(wild.moves)
        else:
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
        
        if battle.is_finished and getattr(wild, "story_ref", None):
            await _story_finish(query, ctx, p, player_poke, wild, battle, log_text, user_id)
            return

        if battle.is_finished and getattr(wild, "gym_floor", 0):
            await _gym_finish(query, ctx, p, player_poke, wild, battle, log_text, user_id)
            return

        if battle.is_finished:
            if battle.winner == "player":
                use_exp_all = bool(ctx.user_data.get("exp_all_on"))
                if getattr(wild, "is_boss", False):
                    tpl = ctx.user_data.get("boss_tpl")
                    lost = 1 - (player_poke.current_hp / max(1, player_poke.max_hp))  # before XP (level-up heals)
                    won = boss_battle.boss_victory(p, tpl, lost)
                    xp_info = boss_battle.award_battle_xp(p, player_poke, won["xp"], use_exp_all)
                    reward = won["coins"]
                    items_txt = ", ".join(f"{q}x {n.replace('_', ' ')}" for n, q in won["items"]) or "—"
                    extra = (f"\n🎁 Drops: {items_txt}" + ("\n🌟 Flawless bonus!" if won["flawless"] else ""))
                    header = "👹 **DAILY BOSS DEFEATED!**"
                    catch_block = ""
                else:
                    reward = random.randint(10, 50)
                    p.add_coins(reward)
                    xp_info = boss_battle.award_battle_xp(p, player_poke, 20 * wild.level, use_exp_all)
                    extra = ""
                    header = "✅ **YOU WON!**"
                    catch_block = f"\n\n🔴 **Catch {wild.species_name}?**"

                xp_line = f"\n⭐ +{xp_info['per_pokemon']} XP" + (
                    f" each ({xp_info['pokemon_count']} Pokémon, EXP ALL used)" if xp_info["used"] else ""
                )
                level_txt = "".join(f"\n🆙 {line}" for line in xp_info["level_ups"])
                save_player(user_id, p, ctx)

                log_text = f"""**⚔️ BATTLE RESULT**

{log_text}

{header}
💰 +{reward}₽ earned{xp_line}{level_txt}{extra}{catch_block}"""

                if getattr(wild, "is_boss", False):
                    ctx.user_data['wild'] = None
                    ctx.user_data['battle'] = None
                    buttons = [[InlineKeyboardButton("⬅️ Menu", callback_data="show_menu")]]
                else:
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
            buttons = get_battle_buttons(moves, is_wild=True, **_battle_button_opts(p, wild, ctx))
        
        await query.edit_message_text(log_text, reply_markup=InlineKeyboardMarkup(buttons))
        
    except Exception as e:
        logger.error(f"Move error: {e}")
        await query.answer(f"❌ Error: {str(e)[:40]}", show_alert=True)

def _battle_button_opts(p, wild, ctx) -> dict:
    """EXP ALL toggle only shows while the player owns one."""
    has_exp_all = ExpAllItem.has_item(p)
    in_gym = bool(getattr(wild, "gym_floor", 0))
    in_story = bool(getattr(wild, "story_ref", None))
    return {
        "is_boss": bool(getattr(wild, "is_boss", False)) or in_gym or in_story,   # no Pokéballs vs bosses / trainers
        "exp_all": (bool(ctx.user_data.get("exp_all_on")) if has_exp_all else None) if not in_gym else None,
        "forfeit": in_gym,
        "no_flee": in_story,
    }

def _ability_tag(mon) -> str:
    name = AbilitySystem.display_name(getattr(mon, "ability", None))
    return f"  ✨ {name}" if name else ""

def format_battle_panel_clean(player_poke, wild_poke, moves):
    """Format clean battle panel - NO CLUTTER"""
    
    wild_types = " / ".join(wild_poke.types) if hasattr(wild_poke, 'types') else "Normal"
    player_types = " / ".join(player_poke.types) if hasattr(player_poke, 'types') else "Normal"
    
    gym_floor = getattr(wild_poke, "gym_floor", 0)
    sref = getattr(wild_poke, "story_ref", None)
    if sref:
        t = journey.TRAINERS[sref["t"]]
        title = f"⚔️ {t['name'].upper()} — {sref['i'] + 1}/{sref['n']}"
    else:
        title = f"🏟️ BATTLE GYM — FLOOR {gym_floor}" if gym_floor else "⚔️ WILD BATTLE"
    text = f"""**{title}**

━━━━━━━━━━━━━━━━━━━

**{"👹 BOSS — " if getattr(wild_poke, "is_boss", False) else ""}{wild_poke.species_name.upper()}** [{wild_types}]{_ability_tag(wild_poke)}
**Lv.** {wild_poke.level}  •  **HP** {wild_poke.current_hp}/{wild_poke.max_hp}
{get_hp_bar(wild_poke.current_hp, wild_poke.max_hp)}

━━━━━━━━━━━━━━━━━━━

**{player_poke.nickname.upper()}** [{player_types}]{_ability_tag(player_poke)}
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

def get_battle_buttons(moves, is_wild=True, is_boss=False, exp_all=None, forfeit=False, no_flee=False):
    """Get battle buttons - 2 per row, then pokeball/run.
    is_boss hides Pokéballs (bosses can't be caught); exp_all is None (hide), True or False (toggle state)."""
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
        if is_boss and no_flee:
            pass   # trainer battles: no Pokéballs and no running away
        elif is_boss:
            buttons.append([InlineKeyboardButton("🏳️ Forfeit run" if forfeit else "🏃 Flee", callback_data="battle_run")])
        else:
            buttons.append([
                InlineKeyboardButton("🔴 Pokéballs", callback_data="catch_pokeball"),
                InlineKeyboardButton("🏃 Flee", callback_data="battle_run"),
            ])
        if exp_all is not None:
            buttons.append([InlineKeyboardButton(f"✨ EXP ALL: {'ON' if exp_all else 'OFF'}", callback_data="toggle_exp_all")])
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

    if getattr(wild, "is_boss", False):
        await query.answer("👹 The daily boss can't be caught!", show_alert=True)
        return
    if getattr(wild, "story_ref", None):
        await query.answer("A trainer's Pokémon can't be caught!", show_alert=True)
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
    
    visible = boss_battle.public_inventory(p)
    if not visible:
        inv_text = "Empty"
    else:
        inv_text = "\n".join([f"• {k.replace('_', ' ')}: {v}x" for k, v in visible.items()])
    
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
    wild = ctx.user_data.get('wild')
    if wild is not None and getattr(wild, "story_ref", None):
        await query.answer("You can't run from a trainer battle!", show_alert=True)
        return
    if wild is not None and getattr(wild, "gym_floor", 0):
        uid = query.from_user.id
        p = get_player(uid, ctx)
        if p:
            result = gym_system.end_run(p)
            save_player(uid, p, ctx)
            ctx.user_data['wild'] = None
            ctx.user_data['battle'] = None
            ctx.user_data.pop('gym', None)
            await query.edit_message_text(
                f"🏳️ **You left the gym.**\n\nFloors cleared: **{result['floors_cleared']}** (best {result['best']})",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏟️ Gym", callback_data="gym"),
                                                    InlineKeyboardButton("⬅️ Menu", callback_data="show_menu")]]),
            )
            return
    ctx.user_data['wild'] = None
    ctx.user_data['battle'] = None
    
    text = "🏃 **You fled the battle!**\n\nThat was close..."
    buttons = [[InlineKeyboardButton("⬅️ Menu", callback_data="show_menu")]]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))


# ════════════════════════════════════════════════════════════════
# ROUTES, DAILY BOSS, EXP ALL, RARE CANDY
# ════════════════════════════════════════════════════════════════

async def _reply(update: Update, text: str, buttons=None):
    """Send or edit, whichever the update allows (works for commands and button presses)."""
    markup = InlineKeyboardMarkup(buttons) if buttons else None
    query = update.callback_query
    if query:
        try:
            await query.edit_message_text(text, reply_markup=markup)
        except Exception:
            await query.message.reply_text(text, reply_markup=markup)
    else:
        await update.message.reply_text(text, reply_markup=markup)

async def routes_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Pick where to hunt"""
    uid = update.callback_query.from_user.id if update.callback_query else update.effective_user.id
    p = get_player(uid, ctx)
    if not p:
        await _reply(update, "❌ Use /start first!")
        return

    if journey.ensure_story(p)["mode"] == "journey":
        await _reply(update, "🧭 You're on a journey — wild Pokémon depend on where you are. Travel from the Journey screen.",
                     [[InlineKeyboardButton("🧭 Journey", callback_data="journey"), InlineKeyboardButton("⬅️ Menu", callback_data="show_menu")]])
        return
    current = ctx.user_data.get('hunt_route')
    rows = [[InlineKeyboardButton(
        f"{'✅ ' if not current else ''}🌿 Wild Grass (default)", callback_data="hunt_route_default")]]
    pair = []
    for r in EncounterSystem.list_routes():
        label = f"{'✅ ' if current == r['id'] else ''}{r['name']} Lv{r['min_level']}-{r['max_level']}"
        pair.append(InlineKeyboardButton(label[:30], callback_data=f"hunt_route_{r['id']}"))
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)
    rows.append([InlineKeyboardButton("⬅️ Menu", callback_data="show_menu")])
    await _reply(update, "🗺️ **ROUTES**\n\nWhere do you want to hunt? Harder routes have higher-level wild Pokémon.", rows)

async def choose_route(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    route_id = query.data[len("hunt_route_"):]
    if route_id == "default":
        ctx.user_data.pop('hunt_route', None)
        label = "Wild Grass"
    elif EncounterSystem.has_route(route_id):
        ctx.user_data['hunt_route'] = route_id
        label = next(r['name'] for r in EncounterSystem.list_routes() if r['id'] == route_id)
    else:
        await query.answer("❌ Unknown route!", show_alert=True)
        return
    await query.answer(f"📍 {label}")
    await _reply(update, f"📍 Hunting in **{label}**.\n\nGood luck out there!", [[
        InlineKeyboardButton("🎯 Hunt", callback_data="hunt"),
        InlineKeyboardButton("🗺️ Routes", callback_data="routes"),
    ]])

def _boss_panel(p):
    lead = next((m for m in p.active_team if not m.is_fainted), None)
    tpl = daily_boss_system.get_daily_boss()
    boss = boss_battle.scaled_boss(tpl, lead.level if lead else 5)
    claimed = boss_battle.is_claimed_today(p)
    info = daily_boss_system.get_boss_info()
    text = f"""👹 **DAILY BOSS**

**{boss.species.upper()}** Lv.{boss.level}
✨ Ability: {AbilitySystem.display_name(boss.ability)}
⚔️ Moves: {", ".join(m.replace("_", " ") for m in info["moves"])}

🎁 Reward up to {boss.coin_reward}₽ + {boss.xp_reward} XP (+ drops)
{"✅ Already defeated today — new boss at 00:00 UTC" if claimed else "One attempt that counts per day. It can't be caught."}"""
    buttons = []
    if not claimed:
        buttons.append([InlineKeyboardButton("⚔️ Challenge", callback_data="boss_fight")])
    buttons.append([InlineKeyboardButton("⬅️ Menu", callback_data="show_menu")])
    return text, buttons

async def boss_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.callback_query.from_user.id if update.callback_query else update.effective_user.id
    p = get_player(uid, ctx)
    if not p or not p.active_team:
        await _reply(update, "❌ Use /start first!")
        return
    text, buttons = _boss_panel(p)
    await _reply(update, text, buttons)

async def boss_fight(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    p = get_player(uid, ctx)
    if not p or not p.active_team:
        await query.answer("❌ Use /start first!", show_alert=True)
        return
    if boss_battle.is_claimed_today(p):
        await query.answer("✅ You already beat today's boss!", show_alert=True)
        return
    lead = p.active_team[0]
    if lead.is_fainted or lead.current_hp <= 0:
        await query.answer("💀 Your lead Pokémon has fainted — heal or switch first.", show_alert=True)
        return

    boss_mon, tpl = boss_battle.build_boss_pokemon(lead.level)
    ctx.user_data['wild'] = boss_mon
    ctx.user_data['boss_tpl'] = tpl
    ctx.user_data['battle'] = None
    ctx.user_data.pop('gym', None)
    await query.answer("👹 The boss appears!")
    await battle_wild(update, ctx)   # same battle screen / move loop as a wild fight

async def toggle_exp_all(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    p = get_player(uid, ctx)
    wild = ctx.user_data.get('wild')
    if not p or not wild:
        await query.answer("❌ No active battle!", show_alert=True)
        return
    if not ExpAllItem.has_item(p):
        await query.answer("You don't own an EXP ALL — buy one in /shop.", show_alert=True)
        return

    ctx.user_data['exp_all_on'] = not ctx.user_data.get('exp_all_on', False)
    player_poke = p.active_team[0]
    moves = get_moves_by_level(player_poke.species_name, player_poke.level) or ["tackle"]
    text = format_battle_panel_clean(player_poke, wild, moves)
    buttons = get_battle_buttons(moves, is_wild=True, **_battle_button_opts(p, wild, ctx))
    await query.answer("✨ EXP ALL " + ("ON" if ctx.user_data['exp_all_on'] else "OFF"))
    try:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:  # "message is not modified" etc. — harmless
        logger.info(f"toggle_exp_all edit skipped: {e}")

async def candy_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """/candy [team slot] — Rare Candy: +1 level"""
    from rare_candy_system import RareCandy
    uid = update.effective_user.id
    p = get_player(uid, ctx)
    if not p or not p.active_team:
        await update.message.reply_text("❌ Use /start first!")
        return
    args = update.message.text.split()
    slot = 1
    if len(args) > 1:
        try:
            slot = int(args[1])
        except ValueError:
            await update.message.reply_text("Usage: /candy [team slot number]")
            return
    if not 1 <= slot <= len(p.active_team):
        await update.message.reply_text(f"❌ Pick a slot from 1 to {len(p.active_team)}.")
        return
    target = p.active_team[slot - 1]
    if p.inventory.get("rare_candy", 0) <= 0:
        await update.message.reply_text("❌ You have no Rare Candy — /buy rare_candy 1 (1000₽).")
        return
    if target.level >= RareCandy.MAX_LEVEL:
        await update.message.reply_text(f"❌ {target.nickname} is already max level.")
        return
    p.remove_item("rare_candy", 1)
    result = RareCandy.use(target)
    save_player(uid, p, ctx)
    await update.message.reply_text(
        f"🍬 **{target.nickname}** grew to Lv.{result.get('new_level', target.level)}!"
    )


# ════════════════════════════════════════════════════════════════
# BATTLE GYM (endless floors)
# ════════════════════════════════════════════════════════════════

def _gym_panel(p):
    st = gym_system.status(p)
    if st["next_is_leader"] and st["leader"]:
        nxt = f"{st['leader']['gym']} Gym Leader **{st['leader']['name']}** (Lv.{st['next_level']})"
    else:
        nxt = f"Floor {st['next_floor']} trainer (Lv.{st['next_level']})"
    run = f"\n🔥 Run in progress — floor **{st['floor']}**" if st["in_run"] else ""
    text = f"""🏟️ **BATTLE GYM**

Climb floor after floor. Every 5th floor is a Gym Leader with a badge.
Opponents scale with the floor, not with you. No XP here, and your team is healed after each cleared floor.

🏆 Best floor: **{st['best']}**   🎫 BP: **{st['bp']}**{run}
➡️ Next: {nxt}"""
    buttons = [
        [InlineKeyboardButton("▶️ Resume run" if st["in_run"] else "🚪 Enter gym", callback_data="gym_enter")],
        [InlineKeyboardButton("🛒 Gym shop", callback_data="gym_shop"), InlineKeyboardButton("⬅️ Menu", callback_data="show_menu")],
    ]
    return text, buttons

async def gym_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.callback_query.from_user.id if update.callback_query else update.effective_user.id
    p = get_player(uid, ctx)
    if not p or not p.active_team:
        await _reply(update, "❌ Use /start first!")
        return
    text, buttons = _gym_panel(p)
    await _reply(update, text, buttons)

async def gym_enter(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Start a run / fight the current floor. Also 'next floor' and 'send in the next Pokémon'."""
    query = update.callback_query
    uid = query.from_user.id
    p = get_player(uid, ctx)
    if not p or not p.active_team:
        await query.answer("❌ Use /start first!", show_alert=True)
        return

    idx = next((i for i, m in enumerate(p.active_team) if not m.is_fainted and m.current_hp > 0), None)
    if idx is None:
        await query.answer("💀 Your whole team has fainted — heal up first.", show_alert=True)
        return
    if idx != 0:  # same as using Switch: bring the healthy Pokémon to the front
        p.active_team[0], p.active_team[idx] = p.active_team[idx], p.active_team[0]

    gym_system.start_or_resume(p)
    opp, meta = gym_system.build_opponent(p)
    save_player(uid, p, ctx)

    ctx.user_data['wild'] = opp
    ctx.user_data['battle'] = None
    ctx.user_data['gym'] = meta
    ctx.user_data['exp_all_on'] = False

    if meta["leader"]:
        await query.answer(f"🏟️ {meta['gym']} Gym — Leader {meta['trainer']}!")
    else:
        await query.answer(f"🏟️ Floor {meta['floor']}: {meta['trainer']}")
    await battle_wild(update, ctx)

async def _gym_finish(query, ctx, p, player_poke, wild, battle, log_text, user_id):
    ctx.user_data['wild'] = None
    ctx.user_data['battle'] = None
    if battle.winner == "player":
        won = gym_system.floor_won(p)        # heals the whole team (player_poke is a team member)
        save_player(user_id, p, ctx)
        badge = f"\n🏅 **{won['badge']}** earned!" if won["badge"] else ""
        text = f"""**🏟️ FLOOR {won['floor_cleared']} CLEARED!**

{log_text}

🎫 +{won['bp']} BP   💰 +{won['coins']}₽{badge}
💚 Team fully healed.
🏆 Best: {won['best']}"""
        buttons = [[InlineKeyboardButton(f"⏭️ Next floor ({won['next_floor']})", callback_data="gym_enter")],
                   [InlineKeyboardButton("🏟️ Gym", callback_data="gym"), InlineKeyboardButton("⬅️ Menu", callback_data="show_menu")]]
    else:
        player_poke.is_fainted = True
        player_poke.current_hp = 0
        lost = gym_system.floor_lost(p)
        save_player(user_id, p, ctx)
        if lost["run_over"]:
            text = f"""**🏟️ RUN OVER**

{log_text}

💀 Your last Pokémon fainted.
Floors cleared: **{lost['floors_cleared']}**   🏆 Best: {lost['best']}
💚 The gym patched up your team."""
            buttons = [[InlineKeyboardButton("🏟️ Gym", callback_data="gym"), InlineKeyboardButton("⬅️ Menu", callback_data="show_menu")]]
        else:
            text = f"""**🏟️ {player_poke.nickname.upper()} FAINTED**

{log_text}

{lost['remaining']} Pokémon left — send in the next one to retry floor {lost['floor']}."""
            buttons = [[InlineKeyboardButton("🔁 Send next Pokémon", callback_data="gym_enter")],
                       [InlineKeyboardButton("⬅️ Menu", callback_data="show_menu")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

async def gym_shop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    p = get_player(uid, ctx)
    if not p:
        await query.answer("❌ Use /start first!", show_alert=True)
        return
    lines = "\n".join(f"• **{label}** — {price} BP" for _id, (price, label, _k) in gym_system.SHOP.items())
    text = f"🛒 **GYM SHOP**\n\n🎫 Your BP: **{gym_system.get_bp(p)}**\n\n{lines}"
    rows, pair = [], []
    for item_id, (price, label, _kind) in gym_system.SHOP.items():
        pair.append(InlineKeyboardButton(f"{label} ({price})", callback_data=f"gym_buy_{item_id}"))
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)
    rows.append([InlineKeyboardButton("⬅️ Gym", callback_data="gym")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(rows))

async def gym_buy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    p = get_player(uid, ctx)
    if not p:
        await query.answer("❌ Use /start first!", show_alert=True)
        return
    item_id = query.data[len("gym_buy_"):]
    err = gym_system.buy(p, item_id, 1)
    if err:
        await query.answer(f"❌ {err}", show_alert=True)
        return
    save_player(uid, p, ctx)
    await query.answer(f"✅ Bought {gym_system.SHOP[item_id][1]}!")
    await gym_shop(update, ctx)


# ════════════════════════════════════════════════════════════════
# JOURNEY (towns, routes, gyms, rival, Elite Four)
# ════════════════════════════════════════════════════════════════

def _journey_panel(p):
    st = journey.state(p)
    if st["mode"] != "journey":
        text = ("🧭 **JOURNEY**\n\nThis region's journey map is still being drawn. "
                "Explore its routes with 🗺️ Routes and test yourself in the 🏟️ Battle Gym.")
        buttons = [[InlineKeyboardButton("🗺️ Routes", callback_data="routes"), InlineKeyboardButton("🎯 Hunt", callback_data="hunt")],
                   [InlineKeyboardButton("⬅️ Menu", callback_data="show_menu")]]
        return text, buttons

    loc = st["location"]
    kind = "🏘️ Town" if loc["kind"] == "town" else "🌿 Route"
    badges = " ".join("🏅" for _ in range(st["badge_count"])) or "—"
    text = f"""🧭 **{loc['name']}**  ({kind})

{loc['desc']}

🎯 {st['objective']}
🏅 Badges: {st['badge_count']}/8 {badges}"""
    if st["pending"]:
        text += "\n⚠️ A trainer battle is in progress — challenge again to continue it."

    buttons = []
    for c in st["challenges"]:
        if c["cleared"]:
            continue
        icon = {"gym": "🏟️", "rival": "😤", "e4": "👑", "champion": "🏆"}.get(c["kind"], "⚔️")
        label = f"{icon} {c['name']} (Lv.{c['top_level']})" + ("" if c["available"] else " 🔒")
        buttons.append([InlineKeyboardButton(label, callback_data=f"jc_{c['id']}")])
    action_row = []
    if st["can_scan"]:
        action_row.append(InlineKeyboardButton("🎯 Hunt here", callback_data="hunt"))
    if loc["heal"]:
        action_row.append(InlineKeyboardButton("💚 Heal", callback_data="jheal"))
    if action_row:
        buttons.append(action_row)
    row = []
    for e in st["exits"]:
        label = f"{'🔒' if e['locked'] else '➡️'} {e['name']}"
        row.append(InlineKeyboardButton(label, callback_data=f"jt_{e['id']}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("⬅️ Menu", callback_data="show_menu")])
    return text, buttons

async def journey_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.callback_query.from_user.id if update.callback_query else update.effective_user.id
    p = get_player(uid, ctx)
    if not p or not p.active_team:
        await _reply(update, "❌ Use /start first!")
        return
    text, buttons = _journey_panel(p)
    save_player(uid, p, ctx)      # persists the story if it was just created for an older player
    await _reply(update, text, buttons)

async def journey_travel_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    p = get_player(uid, ctx)
    if not p:
        await query.answer("❌ Use /start first!", show_alert=True)
        return
    try:
        journey.travel(p, query.data[len("jt_"):])
    except journey.JourneyError as e:
        await query.answer(f"🔒 {e}", show_alert=True)
        return
    save_player(uid, p, ctx)
    await query.answer()
    text, buttons = _journey_panel(p)
    await _reply(update, text, buttons)

async def journey_heal_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    p = get_player(uid, ctx)
    if not p:
        await query.answer("❌ Use /start first!", show_alert=True)
        return
    try:
        journey.heal(p)
    except journey.JourneyError as e:
        await query.answer(f"❌ {e}", show_alert=True)
        return
    save_player(uid, p, ctx)
    await query.answer("💚 Your team is fully healed!", show_alert=True)
    text, buttons = _journey_panel(p)
    await _reply(update, text, buttons)

async def journey_challenge(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Start (or continue) a story trainer battle — then it runs through the normal battle screen."""
    query = update.callback_query
    uid = query.from_user.id
    p = get_player(uid, ctx)
    if not p or not p.active_team:
        await query.answer("❌ Use /start first!", show_alert=True)
        return
    idx = next((i for i, m in enumerate(p.active_team) if not m.is_fainted and m.current_hp > 0), None)
    if idx is None:
        await query.answer("💀 Your whole team has fainted — heal at a Pokémon Center first.", show_alert=True)
        return
    try:
        opp, meta = journey.start_trainer(p, query.data[len("jc_"):])
    except journey.JourneyError as e:
        await query.answer(f"🔒 {e}", show_alert=True)
        return
    if idx != 0:
        p.active_team[0], p.active_team[idx] = p.active_team[idx], p.active_team[0]
    save_player(uid, p, ctx)

    ctx.user_data['wild'] = opp
    ctx.user_data['battle'] = None
    ctx.user_data.pop('gym', None)
    ctx.user_data['exp_all_on'] = False
    await query.answer(f"{meta['name']} wants to battle!")
    await query.message.reply_text(f"**{meta['name']}** — {meta['title']}\n\n\"{meta['intro']}\"")
    await battle_wild(update, ctx)

async def _story_finish(query, ctx, p, player_poke, wild, battle, log_text, user_id):
    """One of a story trainer's Pokémon went down — or yours did."""
    sref = wild.story_ref
    if battle.winner == "player":
        use_exp_all = bool(ctx.user_data.get("exp_all_on"))
        xp = 25 * wild.level
        xp_info = boss_battle.award_battle_xp(p, player_poke, xp, use_exp_all, flag=p.story.get("progress"))
        xp_line = f"\n⭐ +{xp_info['per_pokemon']} XP" + (
            f" each ({xp_info['pokemon_count']} Pokémon, EXP ALL)" if xp_info["used"] else "")
        level_txt = "".join(f"\n🆙 {line}" for line in xp_info["level_ups"])
        nxt = journey.next_opponent(p, sref["t"], sref["i"])
        save_player(user_id, p, ctx)
        if nxt:
            opp, meta = nxt
            ctx.user_data['wild'] = opp
            ctx.user_data['battle'] = BattleSystem(player_poke, opp)
            moves = get_moves_by_level(player_poke.species_name, player_poke.level) or ["tackle"]
            text = (f"**⚔️ BATTLE RESULT**\n\n{log_text}\n{xp_line}{level_txt}\n\n"
                    f"➡️ **{meta['name']}** sent out **{opp.species_name.upper()}**!\n\n"
                    + format_battle_panel_clean(player_poke, opp, moves))
            buttons = get_battle_buttons(moves, is_wild=True, **_battle_button_opts(p, opp, ctx))
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))
            return

        won = journey.trainer_won(p, sref["t"])
        save_player(user_id, p, ctx)
        ctx.user_data['wild'] = None
        ctx.user_data['battle'] = None
        items = ", ".join(f"{q}x {n.replace('_', ' ')}" for n, q in won["items"].items())
        extras = ""
        if won["badge"]:
            extras += f"\n🏅 **{won['badge']}** earned! ({won['badge_count']}/8)"
        if items:
            extras += f"\n🎁 {items}"
        if won["complete"]:
            extras += "\n\n🏆 **You are the Champion!** Welcome to the Hall of Fame."
            if won["unlocked_region"]:
                extras += f"\n🗺️ {won['unlocked_region'].title()} is now unlocked."
        text = f"""**🏟️ {won['name'].upper()} DEFEATED!**

{log_text}

💬 *"{won['win']}"*
💰 +{won['coins']}₽{xp_line}{level_txt}{extras}"""
        buttons = [[InlineKeyboardButton("🧭 Journey", callback_data="journey"), InlineKeyboardButton("⬅️ Menu", callback_data="show_menu")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        return

    # your Pokémon fainted
    player_poke.is_fainted = True
    player_poke.current_hp = 0
    lost = journey.trainer_lost(p)
    save_player(user_id, p, ctx)
    ctx.user_data['wild'] = None
    ctx.user_data['battle'] = None
    if lost["blackout"]:
        text = f"""**💀 BLACKED OUT**

{log_text}

Your whole team has fainted. You were rushed to **{lost['location']}** and your team was healed."""
        buttons = [[InlineKeyboardButton("🧭 Journey", callback_data="journey"), InlineKeyboardButton("⬅️ Menu", callback_data="show_menu")]]
    else:
        text = f"""**⚔️ {player_poke.nickname.upper()} FAINTED**

{log_text}

{lost['remaining']} Pokémon left. Send the next one to keep fighting {journey.TRAINERS[sref['t']]['name']}."""
        buttons = [[InlineKeyboardButton("🔁 Send next Pokémon", callback_data=f"jc_{sref['t']}")],
                   [InlineKeyboardButton("🧭 Journey", callback_data="journey")]]
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
**EXP All** - 500₽ (splits battle XP across your team)
**Rare Candy** - 1000₽ (+1 level, use with /candy)

Use: `/buy potion 3` or `/buy exp_all 1`"""
    
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
        "potion": 200, "restore": 500, "revive": 1000,
        "exp_all": 500, "rare_candy": 1000,
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
    app.add_handler(CommandHandler("routes", routes_cmd))
    app.add_handler(CommandHandler("boss", boss_cmd))
    app.add_handler(CommandHandler("candy", candy_cmd))
    app.add_handler(CommandHandler("gym", gym_cmd))
    app.add_handler(CommandHandler("weblogin", weblogin))
    app.add_handler(CommandHandler("journey", journey_cmd))
    
    # Callbacks - Start & Menu
    app.add_handler(CallbackQueryHandler(starter_selected, pattern="starter_"))
    app.add_handler(CallbackQueryHandler(show_menu, pattern="^show_menu$"))
    
    # Callbacks - Hunt & Battle (Wild)
    app.add_handler(CallbackQueryHandler(hunt, pattern="^hunt$"))
    app.add_handler(CallbackQueryHandler(routes_cmd, pattern="^routes$"))
    app.add_handler(CallbackQueryHandler(choose_route, pattern="^hunt_route_"))
    app.add_handler(CallbackQueryHandler(boss_cmd, pattern="^boss$"))
    app.add_handler(CallbackQueryHandler(boss_fight, pattern="^boss_fight$"))
    app.add_handler(CallbackQueryHandler(toggle_exp_all, pattern="^toggle_exp_all$"))
    app.add_handler(CallbackQueryHandler(avatar_selected, pattern="^av_"))
    app.add_handler(CallbackQueryHandler(region_back, pattern="^rg_back$"))
    app.add_handler(CallbackQueryHandler(region_selected, pattern="^rg_"))
    app.add_handler(CallbackQueryHandler(pick_starter, pattern="^pk_"))
    app.add_handler(CallbackQueryHandler(journey_cmd, pattern="^journey$"))
    app.add_handler(CallbackQueryHandler(journey_travel_cb, pattern="^jt_"))
    app.add_handler(CallbackQueryHandler(journey_heal_cb, pattern="^jheal$"))
    app.add_handler(CallbackQueryHandler(journey_challenge, pattern="^jc_"))
    app.add_handler(CallbackQueryHandler(gym_cmd, pattern="^gym$"))
    app.add_handler(CallbackQueryHandler(gym_enter, pattern="^gym_enter$"))
    app.add_handler(CallbackQueryHandler(gym_shop, pattern="^gym_shop$"))
    app.add_handler(CallbackQueryHandler(gym_buy, pattern="^gym_buy_"))
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
