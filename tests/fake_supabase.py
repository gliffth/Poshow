"""Minimal PostgREST imitation: upserts, eq filters, select, unknown-column errors."""
import json, re, types, urllib.parse

class RequestException(Exception): pass

class Resp:
    def __init__(s, code, body=None): s.status_code=code; s._b=body; s.text=json.dumps(body) if body is not None else ""
    def json(s): return s._b

GOOD = {
 "players":["user_id","username","created_date","level","experience","coins","wins","losses","elo","current_streak","current_region","regions_unlocked","pokemon_caught","pokedex_seen","inventory","pokeballs","login_streak","badges","achievements","referral_code","successful_referrals","active_team","avatar","story","version"],
 "pokemon":["id","player_id","species_name","nickname","level","trainer_id","current_hp","max_hp","experience","iv","ev","nature","moves","status","is_fainted","is_shiny","pending_moves"],
 "battle_sessions":["battle_id","user_id","player_pokemon","wild_pokemon","updated_at","completed_at","completion_result"],
 "accounts":["username","username_lower","password_hash","user_id","created_at"],
 "login_codes":["code","user_id","username","expires_at","link_user_id"],
 "site_assets":["key","url","updated_at"],
 "pvp_matches":["id","user_a","user_b","status","state","ts"],
 "trades":["id","user_a","user_b","status","state","ts"],
 "identity_links":["alias_id","user_id","kind","created_at"],
 "feedback":["id","user_id","username","category","message","context","status","created_at"],
}
PK={"players":"user_id","pokemon":"id","battle_sessions":"battle_id","accounts":"username_lower","login_codes":"code","site_assets":"key","pvp_matches":"id","trades":"id","feedback":"id","identity_links":"alias_id"}
# what the user actually ran: poshow-schema.sql (no created_date / trainer_id, different battle_sessions)
BAD = {**GOOD,
 "players":[c for c in GOOD["players"] if c!="created_date"],
 "pokemon":[c for c in GOOD["pokemon"] if c!="trainer_id"],
 "battle_sessions":["battle_id","player_user_id","player_pokemon_id","is_wild_battle"]}

class FakeSupabase:
    def __init__(s, schema, rpc=True):
        s.schema=schema; s.rows={t:[] for t in schema}
        s.has_rpc=rpc            # does save_player_atomic() exist (schema.sql applied)?
        s.fail_pokemon_write=False   # test hook: make the pokemon half of the transaction blow up
        s.rpc_calls=0
    def _err(s,t,col): return Resp(400,{"code":"PGRST204","details":None,"hint":None,"message":f"Could not find the '{col}' column of '{t}' in the schema cache"})
    def _parse(s,url):
        u=urllib.parse.urlparse(url); t=u.path.split("/rest/v1/")[1]; q=urllib.parse.parse_qs(u.query); return t,q
    def _match(s,row,q):
        for k,v in q.items():
            if k in("select","limit","on_conflict","order"): continue
            x=v[0]
            if k=="or":                                   # or=(user_a.eq.1,user_b.eq.1)
                alts=[a.split(".",2) for a in x.strip("()").split(",")]
                if not any(op=="eq" and str(row.get(col))==val for col,op,val in alts): return False
            elif x=="is.null" and row.get(k) is not None: return False
            elif x=="not.is.null" and row.get(k) is None: return False
            elif x.startswith("eq.") and str(row.get(k))!=x[3:]: return False
            elif x.startswith("gte.") and not (row.get(k) is not None and float(row[k])>=float(x[4:])): return False
            elif x.startswith("gt.") and not (row.get(k) is not None and str(row[k])>x[3:]): return False
            elif x.startswith("in.") and str(row.get(k)) not in x[4:-1].split(","): return False
        return True
    def get(s,url,headers=None,timeout=None,**k):
        t,q=s._parse(url)
        for key,val in (k.get("params") or {}).items(): q[key]=[str(val)]     # requests' params= argument
        if t not in s.schema: return Resp(404,{"code":"42P01","message":f"relation \"public.{t}\" does not exist"})
        for c in (q.get("select",[""])[0].split(",") if "select" in q else []):
            if c and c!="*" and c not in s.schema[t]: return Resp(400,{"code":"42703","message":f"column {t}.{c} does not exist"})
        for c in q:
            if c not in("select","limit","order","or") and c not in s.schema[t]: return Resp(400,{"code":"42703","message":f"column {t}.{c} does not exist"})
        return Resp(200,[json.loads(json.dumps(r)) for r in s.rows[t] if s._match(r,q)])
    def _rpc_save_player_atomic(s,body):
        """Emulates database/schema.sql save_player_atomic(): ONE transaction (all-or-nothing) + version check."""
        import copy
        s.rpc_calls+=1
        if not s.has_rpc:
            return Resp(404,{"code":"PGRST202","message":"Could not find the function public.save_player_atomic in the schema cache"})
        P=body["p_player"]; mons=body.get("p_pokemon") or []; exp=body.get("p_expected_version")
        if "user_id" not in P: return Resp(400,{"code":"P0001","message":"missing_user_id"})
        snapshot=copy.deepcopy(s.rows)                      # BEGIN
        try:
            ex=next((r for r in s.rows["players"] if r["user_id"]==P["user_id"]),None)
            if ex is None:
                if exp is not None: raise ValueError("version_conflict: player no longer exists")
                for c in P:
                    if c not in s.schema["players"]: raise KeyError(f"column {c}")
                row=copy.deepcopy(P); row["version"]=1; s.rows["players"].append(row); new=1
            else:
                cur=ex.get("version",0)
                if exp is None or exp!=cur: raise ValueError(f"version_conflict: expected {exp}, database has {cur}")
                for c in P:
                    if c not in s.schema["players"]: raise KeyError(f"column {c}")
                ex.update(copy.deepcopy(P)); ex["version"]=cur+1; new=cur+1
            keep={m["id"] for m in mons}                        # reconcile: drop this player's rows no longer owned
            s.rows["pokemon"]=[r for r in s.rows["pokemon"] if not (r["player_id"]==P["user_id"] and r["id"] not in keep)]
            for m in mons:
                if s.fail_pokemon_write: raise RuntimeError("simulated pokemon write failure")
                for c in m:
                    if c not in s.schema["pokemon"]: raise KeyError(f"column {c}")
                m=copy.deepcopy(m); old=next((r for r in s.rows["pokemon"] if r["id"]==m["id"]),None)
                if old is None: s.rows["pokemon"].append(m)
                else: old.update(m)
            return Resp(200,new)                               # COMMIT
        except ValueError as e: s.rows=snapshot; return Resp(400,{"code":"P0001","message":str(e)})
        except KeyError as e: s.rows=snapshot; return Resp(400,{"code":"42703","message":f"{e} does not exist"})
        except Exception as e: s.rows=snapshot; return Resp(500,{"message":str(e)})   # ROLLBACK

    def _rpc_save_players_atomic(s,body):
        """Emulates save_players_atomic(): several players (+ optional trade row) in ONE transaction."""
        import copy
        if not s.has_rpc: return Resp(404,{"code":"PGRST202","message":"Could not find the function public.save_players_atomic"})
        snap=copy.deepcopy(s.rows); out={}; saved_snapshot=s.rows
        try:
            for item in sorted(body["p_batch"],key=lambda i:i["player"]["user_id"]):
                r=s._rpc_save_player_atomic({"p_player":item["player"],"p_pokemon":item["pokemon"],"p_expected_version":item.get("expected_version")})
                if r.status_code!=200: raise RuntimeError(r)
                out[str(item["player"]["user_id"])]=r.json()
            t=body.get("p_trade")
            if t:
                old=next((x for x in s.rows["trades"] if x["id"]==t["id"]),None)
                if old is None: s.rows["trades"].append(copy.deepcopy(t))
                else: old.update(copy.deepcopy(t))
            return Resp(200,out)
        except RuntimeError as e:
            s.rows=snap; r=e.args[0]; return r

    def _rpc_link_identity(s,b):
        """Mirrors link_identity() in database/schema.sql (one transaction; rolled back on error)."""
        import copy, time as _t
        snap=copy.deepcopy(s.rows)
        code=(b.get("p_code") or "").upper(); t=b["p_telegram_id"]; keep=b.get("p_keep"); name=b.get("p_tg_name")
        c=next((r for r in s.rows["login_codes"] if r["code"]==code),None)
        if c is None or c["expires_at"]<_t.time(): return Resp(200,{"status":"expired"})
        w=c.get("link_user_id")
        if w is None: return Resp(200,{"status":"not_a_link_code"})
        if c.get("user_id") is not None: return Resp(200,{"status":"already_used"})
        acct=lambda uid: next((a["username"] for a in s.rows["accounts"] if a["user_id"]==uid),None)
        ex=next((l for l in s.rows["identity_links"] if l["alias_id"]==t),None)
        if ex:
            if ex["user_id"]!=w: return Resp(200,{"status":"linked_elsewhere"})
            c["user_id"]=w; c["username"]=acct(w) or name or "TRAINER"
            return Resp(200,{"status":"already_linked","canonical":w})
        if any(l["alias_id"]==w for l in s.rows["identity_links"]): return Resp(200,{"status":"web_account_retired"})
        w_prog=any(p["player_id"]==w for p in s.rows["pokemon"]); t_prog=any(p["player_id"]==t for p in s.rows["pokemon"])
        if w_prog and t_prog and keep is None: return Resp(200,{"status":"conflict"})
        web_wins = True if keep=="web" else False if keep=="telegram" else (not t_prog)
        s.rows["battle_sessions"]=[r for r in s.rows["battle_sessions"] if r["user_id"] not in (w,t)]
        def archive(uid):
            for p in s.rows["pokemon"]:
                if p["player_id"]==uid: p["player_id"]=-uid
            for p in s.rows["players"]:
                if p["user_id"]==uid: p["user_id"]=-uid
        if web_wins:
            archive(t); s.rows["identity_links"].append({"alias_id":t,"user_id":w,"kind":"telegram"}); canonical=w
        else:
            archive(w)
            for a in s.rows["accounts"]:
                if a["user_id"]==w: a["user_id"]=t
            s.rows["identity_links"].append({"alias_id":w,"user_id":t,"kind":"web"}); canonical=t
        c["user_id"]=canonical; c["username"]=acct(canonical) or name or "TRAINER"
        return Resp(200,{"status":"linked","canonical":canonical,"kept":"web" if web_wins else "telegram","username":c["username"]})

    def post(s,url,headers=None,json=None,timeout=None,**k):
        if "/rest/v1/rpc/link_identity" in url: return s._rpc_link_identity(json)
        if "/rest/v1/rpc/save_players_atomic" in url: return s._rpc_save_players_atomic(json)
        if "/rest/v1/rpc/save_player_atomic" in url: return s._rpc_save_player_atomic(json)
        t,q=s._parse(url)
        if t not in s.schema: return Resp(404,{"message":"no table"})
        items=json if isinstance(json,list) else [json]
        for it in items:
            for c in it:
                if c not in s.schema[t]: return s._err(t,c)
        merge="merge-duplicates" in (headers or {}).get("Prefer","")
        import copy
        for it in items:
            it=copy.deepcopy(it); pk=PK[t]
            if t=="feedback" and pk not in it:                       # bigserial
                it[pk]=max([r[pk] for r in s.rows[t]]+[0])+1
            ex=next((r for r in s.rows[t] if r.get(pk)==it.get(pk)),None)
            if ex is not None:
                if not merge: return Resp(409,{"code":"23505","message":"duplicate key"})
                ex.update(it)
            else: s.rows[t].append(it)
        if "representation" in (headers or {}).get("Prefer",""): return Resp(201,[copy.deepcopy(r) for r in s.rows[t][-len(items):]])
        return Resp(201,None)
    def patch(s,url,headers=None,json=None,timeout=None,**k):
        t,q=s._parse(url)
        for c in json:
            if c not in s.schema[t]: return s._err(t,c)
        hit=[]
        for r in s.rows[t]:
            if s._match(r,q): r.update(json); hit.append(dict(r))
        if "representation" in ((headers or {}).get("Prefer","")): return Resp(200,hit)
        return Resp(204,None)
    def delete(s,url,headers=None,timeout=None,**k):
        t,q=s._parse(url)
        gone=[r for r in s.rows[t] if s._match(r,q)]
        s.rows[t]=[r for r in s.rows[t] if not s._match(r,q)]
        if "representation" in ((headers or {}).get("Prefer","")): return Resp(200,[dict(r) for r in gone])
        return Resp(204,None)

def install(schema, rpc=True):
    import sys
    fake=FakeSupabase(schema, rpc=rpc)
    mod=types.ModuleType("requests"); mod.RequestException=RequestException
    mod.get=fake.get; mod.post=fake.post; mod.patch=fake.patch; mod.delete=fake.delete
    sys.modules["requests"]=mod
    return fake
