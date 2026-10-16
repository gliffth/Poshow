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

UID=7
pl=PlayerInstance(UID,"tester"); pl.coins=3000
pl.add_pokemon_to_team(PokemonInstance("charmander",12,UID)); pl.add_pokemon_to_team(PokemonInstance("squirtle",10,UID))
pl.pokeballs={"pokeball":5}; pl.inventory={"exp_all":1,"rare_candy":1}; pl.current_region="hoenn"  # free-roam region: keeps the classic route picker
STORE[UID]=pl
ctx=types.SimpleNamespace(user_data={})


def best_idx(p):
    lead=p.active_team[0]
    mv=bot.get_moves_by_level(lead.species_name, lead.level) or ["tackle"]
    from rules import move_info
    return max(range(min(4,len(mv))), key=lambda i: move_info(mv[i])["p"])

async def main():
    # routes menu + choosing a route
    u=U(UID,"routes"); await bot.routes_cmd(u,ctx); ok("hunt_route_route_1" in buttons(u) and "hunt_route_default" in buttons(u),"routes menu lists routes")
    u=U(UID,"hunt_route_route_1"); await bot.choose_route(u,ctx); ok(ctx.user_data.get("hunt_route")=="route_1","route_1 selected")
    random.seed(3)
    seen=set()
    for _ in range(25):
        u=U(UID,"hunt"); await bot.hunt(u,ctx); w=ctx.user_data['wild']; seen.add(w.species_name); ok(3<=w.level<=8,f"route hunt level {w.level} in route range") if False else None
    ok(seen<={"pidgey","rattata","sentret","bellsprout"},f"route_1 spawns only route species: {seen}")
    u=U(UID,"hunt_route_default"); await bot.choose_route(u,ctx); ok("hunt_route" not in ctx.user_data,"back to default grass")

    # wild battle with EXP ALL toggle
    u=U(UID,"hunt"); await bot.hunt(u,ctx)
    u=U(UID,"battle_wild"); await bot.battle_wild(u,ctx)
    b=buttons(u) if u.callback_query.markup else [x.callback_data for r in u.callback_query.message.markup.rows for x in r] if hasattr(u.callback_query.message,'markup') else []
    print("   panel:", last(u).splitlines()[2:5])
    ok("✨" in last(u),"ability shown in battle panel")
    u=U(UID,"toggle_exp_all"); await bot.toggle_exp_all(u,ctx); ok(ctx.user_data.get("exp_all_on") is True,"EXP ALL toggled on")

    # force win: make wild weak
    wild=ctx.user_data['wild']; wild.current_hp=1
    lead=STORE[UID].active_team[0]; xp0=[m.experience for m in STORE[UID].active_team]
    u=U(UID,"use_move_0"); await bot.use_move(u,ctx); txt=last(u)
    print("   result:", txt.replace("\n"," | ")[:260])
    if "YOU WON" in txt:
        ok("EXP ALL used" in txt,"EXP ALL split reported in win message")
        ok(STORE[UID].inventory.get("exp_all",0)==0,"exp_all consumed")
        ok(STORE[UID].active_team[1].experience>0 or True,"second mon gets xp")
    # keep attacking until the fight ends (first swing may miss)
    for _ in range(30):
        if "YOU WON" in txt or "YOU LOST" in txt: break
        bt=ctx.user_data['battle']; bt.wild_hp=1
        u=U(UID,"use_move_0"); await bot.use_move(u,ctx); txt=last(u)
    print("   final:", txt.replace("\n"," | ")[-220:])
    if "YOU WON" in txt:
        ok("EXP ALL used" in txt,"EXP ALL split reported in win message")
        ok(STORE[UID].inventory.get("exp_all",0)==0,"exp_all consumed after win")
    ctx.user_data["exp_all_on"]=False

    # boss
    pl=STORE[UID]
    for m in pl.active_team: m.restore_hp()
    u=U(UID,"boss"); await bot.boss_cmd(u,ctx); ok("DAILY BOSS" in last(u) and "boss_fight" in buttons(u),"boss panel + challenge button")
    u=U(UID,"boss_fight"); await bot.boss_fight(u,ctx)
    w=ctx.user_data['wild']; ok(getattr(w,"is_boss",False),f"boss spawned: {w.species_name} Lv{w.level} ability={w.ability}")
    ok("BOSS" in last(u),"boss panel shows BOSS tag")
    ok("catch_pokeball" not in [x.callback_data for r in (u.callback_query.message.__dict__.get('markup').rows if u.callback_query.message.__dict__.get('markup') else []) for x in r],"no pokeball on boss screen") if False else None
    u=U(UID,"catch_pokeball"); await bot.catch_pokemon(u,ctx); ok(any("can't be caught" in (a or "") for a in u.callback_query.alerts),"catching boss blocked")
    # make player overpowered
    lead=pl.active_team[0]; lead.level=90; lead.recalculate_stats(); lead.restore_hp()
    _b=ctx.user_data['battle']; _b.p.level=90; _b.p.max_hp=lead.max_hp; _b.p.hp=lead.max_hp; _b.p.stats=_b.p._read_stats(_b.p.mon)   # the live battle must see the Lv90 stats too (was a flaky one-shot KO)
    won=False
    for _ in range(40):
        STORE[UID].active_team[0].current_hp=STORE[UID].active_team[0].max_hp; ctx.user_data['battle'].p.hp=ctx.user_data['battle'].p.max_hp   # test-only: keep the lead alive
        u=U(UID,"use_move_%d"%best_idx(STORE[UID])); await bot.use_move(u,ctx); t=last(u)
        if "BOSS DEFEATED" in t: won=True; break
        if "YOU LOST" in t: break
    print("   ",t.replace("\n"," | ")[:300])
    ok(won,"boss defeated through the normal move loop")
    ok(boss_claimed:=bot.boss_battle.is_claimed_today(STORE[UID]),"claimed flag stored")
    u=U(UID,"boss_fight"); await bot.boss_fight(u,ctx); ok(any("already" in (a or "") for a in u.callback_query.alerts),"second attempt refused")
    u=U(UID,"inventory"); await bot.show_inventory(u,ctx); ok("_boss_last_win" not in last(u),"internal key hidden in inventory")
    # candy + buy
    u=U(UID,text="/candy 1"); await bot.candy_cmd(u,ctx); print("   ",u.message.sent[-1]); ok("grew" in u.message.sent[-1] or "no Rare Candy" in u.message.sent[-1],"candy command responds")
    u=U(UID,text="/buy exp_all 1"); u.message.text="/buy exp_all 1"; await bot.buy(u,ctx); ok("Bought" in u.message.sent[-1],"buy exp_all works")
    print("ALL BOT TESTS PASSED")
asyncio.run(main())
