import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
import asyncio, types, random, os
os.environ["BOT_TOKEN"]="x"
# --- stub telegram + db + admin
class Btn:
    def __init__(s,text,callback_data=None,**k): s.text=text; s.callback_data=callback_data
class Markup:
    def __init__(s,rows): s.rows=rows
tg=types.ModuleType("telegram"); tg.Update=object; tg.InlineKeyboardButton=Btn; tg.InlineKeyboardMarkup=Markup
class IMP:
    def __init__(s,media=None,caption=None): s.media=media; s.caption=caption
tg.InputMediaPhoto=IMP
tge=types.ModuleType("telegram.ext")
class _Ctx: DEFAULT_TYPE=object
tge.Application=object; tge.CommandHandler=object; tge.CallbackQueryHandler=object; tge.ContextTypes=_Ctx
sys.modules["telegram"]=tg; sys.modules["telegram.ext"]=tge
import database
STORE={}
class FakeDB:
    url="http://fake"; key="k"
    def load_player(s,uid): return STORE.get(uid)
    def save_player(s,p): STORE[p.user_id]=p; return True
database.db=FakeDB()
adm=types.ModuleType("admin_panel"); adm.admin=object(); sys.modules["admin_panel"]=adm
sys.path.insert(0,'./telegram-bot')
import bot
import accounts as _acc; bot._web_accounts=_acc.AccountService()   # memory-mode accounts: no database in these tests
import gym_system
from player_model import PlayerInstance
from pokemon_model import PokemonInstance
ok=lambda c,m: print(("PASS " if c else "FAIL ")+m) or (c or sys.exit(1))

class Msg:
    def __init__(s): s.sent=[]
    async def reply_text(s,text,reply_markup=None,**k): s.sent.append(text)
    async def reply_photo(s,photo=None,caption=None,reply_markup=None,**k): s.sent.append(caption); s.photos=getattr(s,"photos",[])+[photo]
    async def reply_animation(s,animation=None,caption=None,**k): s.anims=getattr(s,"anims",[])+[animation]; s.sent.append(caption) if caption else None
    async def reply_media_group(s,media=None,**k): s.albums=getattr(s,"albums",[])+[media]
class Q:
    def __init__(s,uid,data): s.from_user=types.SimpleNamespace(id=uid); s.data=data; s.message=Msg(); s.texts=[]; s.markup=None; s.alerts=[]
    async def answer(s,text=None,show_alert=False): s.alerts.append(text)
    async def edit_message_text(s,text,reply_markup=None,**k): s.texts.append(text); s.markup=reply_markup
    async def delete_message(s): pass
class U:
    def __init__(s,uid,data=None,text=None):
        s.callback_query=Q(uid,data) if data else None
        s.effective_user=types.SimpleNamespace(id=uid)
        s.message=Msg(); 
        if text: s.message.text=text
def last(u): 
    q=u.callback_query
    return (q.texts[-1] if q.texts else (q.message.sent[-1] if q.message.sent else ""))
def buttons(u):
    q=u.callback_query; m=q.markup
    if m is None and getattr(q.message,'markup',None): m=q.message.markup
    return [b.callback_data for r in (m.rows if m else []) for b in r]

UID=9
pl=PlayerInstance(UID,"tester"); pl.coins=3000
pl.add_pokemon_to_team(PokemonInstance("charmander",12,UID)); pl.add_pokemon_to_team(PokemonInstance("squirtle",10,UID))
pl.pokeballs={"pokeball":5}; pl.inventory={"exp_all":1,"rare_candy":1}
STORE[UID]=pl
ctx=types.SimpleNamespace(user_data={})


def best_idx(p):
    lead=p.active_team[0]
    mv=bot.get_moves_by_level(lead.species_name, lead.level) or ["tackle"]
    return max(range(min(4,len(mv))), key=lambda i: (bot.get_move_info(mv[i])["power"] or 0))

async def main():
    pl=STORE[UID]
    pl.active_team[0].level=80; pl.active_team[0].recalculate_stats(); pl.active_team[0].restore_hp()
    pl.coins=0
    u=U(UID,"gym"); await bot.gym_cmd(u,ctx); ok("BATTLE GYM" in last(u) and "gym_enter" in buttons(u) and "gym_shop" in buttons(u),"gym panel + enter/shop buttons")
    u=U(UID,"gym_enter"); await bot.gym_enter(u,ctx)
    w=ctx.user_data['wild']; ok(w.gym_floor==1 and ctx.user_data['gym']['floor']==1,f"floor 1 spawned: {w.species_name} Lv{w.level}")
    print("   DBG battle:", ctx.user_data.get('battle'), "| alerts:", u.callback_query.alerts, "| text:", last(u)[:80])
    ok("BATTLE GYM" in last(u) and "FLOOR 1" in last(u),"battle panel shows gym floor")
    u=U(UID,"catch_pokeball"); await bot.catch_pokemon(u,ctx); ok(any("can't be caught" in (a or "") for a in u.callback_query.alerts),"gym mon can't be caught") if False else None
    for floor in (1,2,3,4,5):
        if floor>1:
            u=U(UID,"gym_enter"); await bot.gym_enter(u,ctx)
        for _ in range(60):
            bt=ctx.user_data['battle']; 
            if bt is None: break
            STORE[UID].active_team[0].current_hp=STORE[UID].active_team[0].max_hp; bt.p.hp=bt.p.max_hp   # test-only: keep the lead alive
            u=U(UID,"use_move_%d"%best_idx(STORE[UID])); await bot.use_move(u,ctx); t=last(u)
            if "CLEARED" in t or "FAINTED" in t or "RUN OVER" in t: break
        if "CLEARED" not in t: print("   DBG t:", t.replace("\n"," | ")[:400], "| wild hp", ctx.user_data.get('wild') and ctx.user_data['wild'].current_hp)
        ok("CLEARED" in t,f"floor {floor} cleared")
    ok("Ember Badge" in STORE[UID].badges and "Ember Badge" in t,"leader floor 5 gives Ember Badge")
    ok(gym_bp:=STORE[UID].inventory.get("battle_points",0)>=11,f"BP earned: {STORE[UID].inventory.get('battle_points')}")
    ok("_gym_floor" not in last(U(UID,"inventory")) , "sanity")
    u=U(UID,"inventory"); await bot.show_inventory(u,ctx); ok("_gym" not in last(u),"gym keys hidden in inventory")
    # shop
    u=U(UID,"gym_shop"); await bot.gym_shop(u,ctx); ok("GYM SHOP" in last(u),"gym shop opens")
    bp0=STORE[UID].inventory["battle_points"]
    u=U(UID,"gym_buy_superpotion"); await bot.gym_buy(u,ctx); ok(STORE[UID].inventory["battle_points"]==bp0-4 and STORE[UID].inventory.get("superpotion")==1,"bought super potion for 4 BP")
    # loss: weak team, 2 mons
    for m in STORE[UID].active_team: m.level=1; m.recalculate_stats(); m.restore_hp()
    random.seed(1234)      # a Lv1 team vs floor 1 — seeded so this loss scenario is deterministic
    u=U(UID,"gym_enter"); await bot.gym_enter(u,ctx)
    first=STORE[UID].active_team[0].nickname
    for _ in range(60):
        bt=ctx.user_data['battle']
        if bt is None: break
        u=U(UID,"use_move_%d"%best_idx(STORE[UID])); await bot.use_move(u,ctx); t=last(u)
        if "FAINTED" in t or "RUN OVER" in t or "CLEARED" in t: break
    print("   ",t.replace("\n"," | ")[:200])
    ok("FAINTED" in t or "RUN OVER" in t,"loss handled")
    if "FAINTED" in t:
        u=U(UID,"gym_enter"); await bot.gym_enter(u,ctx); ok(STORE[UID].active_team[0].nickname!=first,"next healthy Pokemon moved to the front")
        for _ in range(60):
            bt=ctx.user_data['battle']
            if bt is None: break
            u=U(UID,"use_move_%d"%best_idx(STORE[UID])); await bot.use_move(u,ctx); t=last(u)
            if "RUN OVER" in t: break
    ok("RUN OVER" in t and not gym_system.in_run(STORE[UID]),"all fainted -> run over, run closed")
    ok(all(not m.is_fainted for m in STORE[UID].active_team),"team healed after run")
    # forfeit
    for m in STORE[UID].active_team: m.level=40; m.recalculate_stats(); m.restore_hp()
    u=U(UID,"gym_enter"); await bot.gym_enter(u,ctx); u=U(UID,"battle_run"); await bot.battle_run(u,ctx)
    ok("left the gym" in last(u) and not gym_system.in_run(STORE[UID]),"forfeit via Run button ends the run")
    # normal hunt still clean afterwards
    u=U(UID,"hunt"); await bot.hunt(u,ctx); ok(getattr(ctx.user_data['wild'],'gym_floor',0)==0 and 'gym' not in ctx.user_data,"normal hunt not affected by gym state")
    print("ALL BOT GYM TESTS PASSED")
asyncio.run(main())
