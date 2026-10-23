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
import accounts
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



svc=accounts.AccountService(); bot._web_accounts=svc
class Ctx(types.SimpleNamespace): pass
def mkctx(args=None): return Ctx(user_data={}, args=args or [])
class Q2(Q):
    async def edit_message_caption(s,caption=None,reply_markup=None,**k): s.texts.append(caption); s.markup=reply_markup
Q=Q2
def U2(uid,data=None,text=None,first="Newbie"):
    u=U(uid,data,text); u.effective_user=types.SimpleNamespace(id=uid,first_name=first)
    if u.callback_query: u.callback_query.from_user=types.SimpleNamespace(id=uid,first_name=first)
    return u
def btns(u):
    q=u.callback_query; m=q.markup
    if m is None:
        for x in getattr(q.message,'sent_markups',[]): m=x
    return [b.callback_data for r in (m.rows if m else []) for b in r]


def best_idx(p):
    lead=p.active_team[0]
    mv=bot.get_moves_by_level(lead.species_name, lead.level) or ["tackle"]
    from rules import move_info
    return max(range(min(4,len(mv))), key=lambda i: move_info(mv[i])["p"])

async def main():
    uid=51; ctx=mkctx()
    # --- onboarding: avatar -> region -> starter
    u=U2(uid,text="/start"); await bot.start(u,ctx)
    ok(any("who are you" in (m or "") for m in u.message.sent),"new player is asked to pick an avatar first")
    u=U2(uid,"av_marina"); await bot.avatar_selected(u,ctx); ok(ctx.user_data["avatar"]=="marina","avatar stored")
    alb=getattr(u.callback_query.message,"albums",[]); ok(len(alb)==1 and len(alb[0])==9 and alb[0][0].media[:8]==b"\x89PNG\r\n\x1a\n","region slideshow: an album of all 9 region pictures is sent BEFORE the question")
    ok("Kanto" in alb[0][0].caption and "Gen I" in alb[0][0].caption,"slides are captioned")
    ok(any("Where does your journey begin" in (m or "") for m in u.callback_query.message.sent),"then the region question")
    u=U2(uid,"rg_hoenn"); await bot.region_selected(u,ctx); ok("Professor Birch" in (u.callback_query.message.sent[-1]),"region step uses that region's professor")
    ok(len(getattr(u.callback_query.message,"anims",[]))==1 and u.callback_query.message.anims[0][:6]==b"GIF89a","chosen region plays an animated cutscene (GIF)")
    u=U2(uid,"pk_hoenn_mudkip"); await bot.pick_starter(u,ctx)
    p=STORE[uid]; ok(p.active_team[0].species_name=="mudkip" and p.avatar=="marina" and p.current_region=="hoenn","player created: Mudkip, Marina, Hoenn")
    ok(p.story["mode"]=="free_roam","hoenn has no journey map yet -> free roam")
    # kanto journey
    uid2=52; ctx2=mkctx(); ctx2.user_data["avatar"]="ember"
    u=U2(uid2,"pk_kanto_charmander"); await bot.pick_starter(u,ctx2)
    p=STORE[uid2]; ok(p.story["location"]=="pallet_town" and p.avatar=="ember","kanto player starts in Pallet Town")
    u=U2(uid2,"pk_kanto_bulbasaur"); await bot.pick_starter(u,ctx2); ok(any("already" in (a or "") for a in u.callback_query.alerts),"can't choose twice")
    u=U2(uid2,"starter_squirtle"); await bot.starter_selected(u,mkctx()); ok(any("already" in (a or "") for a in u.callback_query.alerts),"legacy starter button also refuses a second pick")

    # --- journey panel
    u=U2(uid2,"journey"); await bot.journey_cmd(u,ctx2)
    ok("Pallet Town" in last(u) and "Boulder Badge" in last(u) and "jt_route_1" in btns(u),"journey panel: location, objective, exits")
    u=U2(uid2,"hunt"); await bot.hunt(u,ctx2); ok(any("No wild" in (a or "") for a in u.callback_query.alerts),"hunt in town refused")
    u=U2(uid2,"jt_pewter_city"); await bot.journey_travel_cb(u,ctx2); ok(any("can't get" in (a or "") for a in u.callback_query.alerts),"can't skip ahead")
    for dest in ("route_1",):
        u=U2(uid2,"jt_"+dest); await bot.journey_travel_cb(u,ctx2)
    ok("Route 1" in last(u) and "hunt" in btns(u),"on Route 1: hunt button appears")
    random.seed(2); seen=set()
    for _ in range(20):
        u=U2(uid2,"hunt"); await bot.hunt(u,ctx2); seen.add(ctx2.user_data['wild'].species_name)
    ok(seen<={"pidgey","rattata","sentret","bellsprout"},"hunting on route_1 spawns route_1 Pokémon: "+str(seen))
    for dest in ("viridian_city","route_2","viridian_forest","pewter_city"):
        u=U2(uid2,"jt_"+dest); await bot.journey_travel_cb(u,ctx2)
    ok("jc_brock" in btns(u) and "jheal" in btns(u),"Pewter City: Brock challenge + heal buttons")
    ok(len(getattr(u.callback_query.message,"anims",[]))==1,"travelling plays a short walking cutscene")
    ctx2.user_data["scenes"]=False
    u=U2(uid2,"jt_route_3"); await bot.journey_travel_cb(u,ctx2) if False else None
    ctx2.user_data["scenes"]=True
    p=STORE[uid2]; p.active_team[0].current_hp=1
    u=U2(uid2,"jheal"); await bot.journey_heal_cb(u,ctx2); ok(STORE[uid2].active_team[0].current_hp==STORE[uid2].active_team[0].max_hp,"heal restores HP")

    # --- Brock battle through the normal battle screen
    p=STORE[uid2]; lead=p.active_team[0]; lead.level=32; lead.recalculate_stats(); lead.restore_hp(); p.inventory["exp_all"]=1
    u=U2(uid2,"jc_brock"); await bot.journey_challenge(u,ctx2)
    w=ctx2.user_data['wild']; ok(w.story_ref["t"]=="brock" and w.species_name=="geodude","Brock sends out Geodude")
    ok("BROCK — 1/2" in last(u),"battle panel titled with trainer + progress")
    ok("catch_pokeball" not in btns(u) and "battle_run" not in btns(u),"no Pokéball / flee buttons in a trainer battle")
    u=U2(uid2,"catch_pokeball"); await bot.catch_pokemon(u,ctx2); ok(any("can't be caught" in (a or "") for a in u.callback_query.alerts),"catch refused")
    u=U2(uid2,"battle_run"); await bot.battle_run(u,ctx2); ok(any("can't run" in (a or "") for a in u.callback_query.alerts),"run refused")
    u=U2(uid2,"toggle_exp_all"); await bot.toggle_exp_all(u,ctx2)
    swapped=False; won=False
    for _ in range(80):
        bt=ctx2.user_data.get('battle')
        if bt is None: break
        bt.wild_hp=1 if False else bt.wild_hp
        ctx2.user_data['battle'].wild_hp=min(ctx2.user_data['battle'].wild_hp,1)
        mv=best_idx(STORE[uid2])
        u=U2(uid2,"use_move_%d"%mv); await bot.use_move(u,ctx2); t=last(u)
        if "sent out **ONIX**" in t: swapped=True; ok("BROCK — 2/2" in t,"second Pokémon: panel shows 2/2")
        if "DEFEATED" in t: won=True; break
    ok(swapped,"Geodude down -> Onix sent out in the same battle")
    ok(won and "Boulder Badge" in t,"Brock defeated, Boulder Badge announced")
    p=STORE[uid2]; ok("Boulder Badge" in p.badges and p.coins>=700 and "brock" in p.story["defeated"],"badge + coins + story saved")
    ok(p.inventory.get("exp_all",0)==0,"EXP All used once")
    u=U2(uid2,"jt_route_3"); await bot.journey_travel_cb(u,ctx2); ok("Route 3" in last(u),"Route 3 now open")

    # --- losing
    p=STORE[uid2]
    for m in p.active_team: m.level=5; m.recalculate_stats(); m.restore_hp()
    for dest in ("route_4","cerulean_city"):
        u=U2(uid2,"jt_"+dest); await bot.journey_travel_cb(u,ctx2)
    u=U2(uid2,"jc_misty"); await bot.journey_challenge(u,ctx2)
    for _ in range(60):
        bt=ctx2.user_data.get('battle')
        if bt is None: break
        u=U2(uid2,"use_move_0"); await bot.use_move(u,ctx2); t=last(u)
        if "BLACKED OUT" in t or "FAINTED" in t: break
    ok("BLACKED OUT" in t,"single-Pokémon team loses -> blacked out: "+t.replace("\n"," ")[-110:])
    ok(STORE[uid2].story["location"]=="cerulean_city" and not STORE[uid2].active_team[0].is_fainted,"sent to last town, healed")
    print("ALL BOT JOURNEY TESTS PASSED")
asyncio.run(main())
