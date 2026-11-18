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
    def find_players_by_username(s,n): return [(p.user_id,p.username) for p in STORE.values() if (p.username or '').lower()==n.lower()]
    url="http://fake"; key="k"
    def load_player(s,uid): return STORE.get(uid)
    def save_player(s,p): STORE[p.user_id]=p; return True
database.db=FakeDB()
adm=types.ModuleType("admin_panel"); adm.admin=object(); sys.modules["admin_panel"]=adm
sys.path.insert(0,'./telegram-bot')
import bot
import accounts as _acc; bot._web_accounts=_acc.AccountService()   # memory-mode accounts: no database in these tests
import accounts
import care as carem, admin_system
os.environ['ADMIN_USER_IDS']='777'
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



class Ctx(types.SimpleNamespace): pass
def mk(): return Ctx(user_data={}, args=[])
def U2(uid,data=None,text=None):
    u=U(uid,data,text); u.effective_user=types.SimpleNamespace(id=uid,first_name="T")
    if u.callback_query: u.callback_query.from_user=types.SimpleNamespace(id=uid,first_name="T")
    return u
async def main():
    uid=61; ctx=mk()
    pl=PlayerInstance(uid,"CareUser"); pl.add_pokemon_to_team(PokemonInstance("charmander",5,uid)); pl.add_pokemon_to_team(PokemonInstance("pidgey",4,uid)); pl.coins=600; STORE[uid]=pl
    u=U2(uid,"care"); await bot.care_cmd(u,ctx); t=last(u)
    ok("CARE CENTER" in t and "Nurse Joy" in t and "▮▮▮" in t and "KO left" in t,"care screen: Joy, condition bar, KOs left")
    m=pl.active_team[0]; carem.on_faint(pl,m)
    u=U2(uid,"care"); await bot.care_cmd(u,ctx); ok("Severely injured" in last(u) and "🩹" in last(u),"fainted once -> 'Severely injured' (not dead)")
    u=U2(uid,"care_heal"); await bot.care_action(u,ctx); ok("fighting fit" in last(u) and not STORE[uid].active_team[0].is_fainted,"free heal")
    # critical
    for _ in range(3): carem.on_faint(pl,pl.active_team[0])
    u=U2(uid,"care"); await bot.care_cmd(u,ctx); ok("Critical" in last(u) and any(b.startswith("care_int_") for b in [x.callback_data for r in u.callback_query.markup.rows for x in r]),"critical Pokémon gets an intensive-care button")
    random.seed(1)
    for _ in range(30):
        pl.coins=600; mid=pl.active_team[0].id
        u=U2(uid,"care_int_"+mid); await bot.care_action(u,ctx)
        if not carem.is_critical(pl,pl.active_team[0]): break
    ok(not carem.is_critical(pl,pl.active_team[0]),"intensive care eventually revives it")
    # rest / take out
    u=U2(uid,"care_rest_"+pl.active_team[1].id); await bot.care_action(u,ctx); ok(len(pl.active_team)==1 and len(carem.resting(pl))==1 and "💤" in last(u),"rest in ball")
    u=U2(uid,"care_out_"+carem.resting(pl)[0].id); await bot.care_action(u,ctx); ok(len(pl.active_team)==2,"take out")
    # not during battle
    ctx.user_data['wild']=PokemonInstance("rattata",3,0); ctx.user_data['battle']=object()
    u=U2(uid,"care"); await bot.care_cmd(u,ctx); ok(any("battle" in (a or "") for a in u.callback_query.alerts),"no Care Center during a battle")
    ctx.user_data['wild']=None; ctx.user_data['battle']=None
    # journey: no center on a route
    pl2=PlayerInstance(62,"R"); pl2.add_pokemon_to_team(PokemonInstance("squirtle",5,62)); pl2.current_region="kanto"; STORE[62]=pl2
    import journey as J; J.init_story(pl2); J.travel(pl2,"route_1"); c2=mk()
    u=U2(62,"care_heal"); await bot.care_action(u,c2); ok(any("route" in (a or "") for a in u.callback_query.alerts),"route has no Care Center")
    # admin
    u=U2(5,text="/give CareUser coins 50"); await bot.give_cmd(u,mk()); ok("Admins only" in u.message.sent[-1],"non-admin refused")
    before=pl.coins
    u=U2(777,text="/give CareUser coins 50"); await bot.give_cmd(u,mk()); ok(pl.coins==before+50 and "+50" in u.message.sent[-1],"admin gives coins by username")
    u=U2(777,text="/give CareUser item potion 4"); await bot.give_cmd(u,mk()); ok(pl.inventory["potion"]==4,"item")
    u=U2(777,text="/give CareUser pokemon eevee 12 shiny"); await bot.give_cmd(u,mk()); ok(any(m.species_name=="eevee" and m.level==12 for m in pl.active_team+pl.pokemon_collection),"pokemon")
    u=U2(777,text="/give 61 ball ultraball 3"); await bot.give_cmd(u,mk()); ok(pl.pokeballs.get("ultraball")==3,"ball by id")
    u=U2(777,text="/give Nobody coins 5"); await bot.give_cmd(u,mk()); ok("No player" in u.message.sent[-1],"unknown player")
    u=U2(777,text="/give CareUser coins abc"); await bot.give_cmd(u,mk()); ok("❌" in u.message.sent[-1],"bad number handled")
    u=U2(777,text="/whois CareUser"); await bot.whois_cmd(u,mk()); ok("CareUser" in u.message.sent[-1],"whois")
    print("ALL BOT CARE/ADMIN TESTS PASSED")
asyncio.run(main())
