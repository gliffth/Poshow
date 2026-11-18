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


svc=accounts.AccountService()
bot._web_accounts=svc
class Ctx(types.SimpleNamespace): pass
def mkctx(args=None): return Ctx(user_data={}, args=args or [])
async def main():
    # existing player + deep link
    pl=PlayerInstance(31,"Old"); pl.add_pokemon_to_team(PokemonInstance("charmander",5,31)); STORE[31]=pl
    code=svc.start_telegram_login()["code"]
    u=U(31,text="/start web_"+code); u.effective_user=types.SimpleNamespace(id=31,first_name="Old")
    await bot.start(u,mkctx(["web_"+code]))
    ok("confirmed" in u.message.sent[-1],"existing player: deep link confirms login")
    ok(svc.poll_telegram_login(code)["user_id"]==31,"website poll now returns this Telegram user")
    # bad code
    u=U(31,text="/start web_ZZZZZZZZ"); u.effective_user=types.SimpleNamespace(id=31,first_name="Old")
    await bot.start(u,mkctx(["web_ZZZZZZZZ"])); ok("invalid or expired" in u.message.sent[-1],"bad code rejected")
    # brand new player + deep link: confirmed AND starter selection still shown
    code2=svc.start_telegram_login()["code"]
    u=U(32,text="/start"); u.effective_user=types.SimpleNamespace(id=32,first_name="Newbie")
    await bot.start(u,mkctx(["web_"+code2]))
    ok(any("confirmed" in m for m in u.message.sent) and any("Every journey" in (m or "") for m in u.message.sent),"new player: login confirmed + starter choice shown")
    ok(svc.poll_telegram_login(code2)["user_id"]==32,"website can log the new player in")
    # plain /start unchanged
    u=U(31,text="/start"); u.effective_user=types.SimpleNamespace(id=31,first_name="Old"); await bot.start(u,mkctx())
    ok("Welcome back" in u.message.sent[-1],"plain /start unchanged")
    # /weblogin
    code3=svc.start_telegram_login()["code"]
    u=U(31,text="/weblogin "+code3); u.effective_user=types.SimpleNamespace(id=31,first_name="Old"); await bot.weblogin(u,mkctx())
    ok("confirmed" in u.message.sent[-1],"/weblogin CODE works")
    u=U(99,text="/weblogin "+code3); u.effective_user=types.SimpleNamespace(id=99,first_name="X"); await bot.weblogin(u,mkctx()); ok("/start first" in u.message.sent[-1],"/weblogin before registering tells you to /start")
    print("ALL BOT WEB LOGIN TESTS PASSED")
asyncio.run(main())
