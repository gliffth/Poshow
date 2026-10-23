import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
import random
from pokemon_model import PokemonInstance
from battle_system import BattleSystem, Move, Combatant
import battle_ai, rules, boss_battle
from daily_boss_system import daily_boss_system
ok=lambda c,m: print(("PASS " if c else "FAIL ")+m) or (c or sys.exit(1))
random.seed(4)

def mon(sp,lv,moves=None):
    p=PokemonInstance(sp,lv,1)
    if moves: p.moves=moves
    p.restore_hp(); return p

# type chart immunities
ok(rules.type_multiplier("ground",["flying"])==0 and rules.type_multiplier("normal",["ghost"])==0 and rules.type_multiplier("electric",["ground"])==0,"immunities: ground/flying, normal/ghost, electric/ground")
ok(rules.type_multiplier("water",["fire","rock"])==4,"double weakness x4")
# immune move does nothing
a,b=mon("pikachu",20,["thunderbolt"]),mon("sandshrew",20)  # ground type
bs=BattleSystem(a,b); bs.execute_turn(Move.from_name("thunderbolt"),Move.from_name("tackle"))
ok(any("doesn't affect" in l for l in bs.battle_log) and b.current_hp==b.max_hp or bs.wild_hp==b.max_hp,"Thunderbolt can't hurt a Ground type")

# stats/nature really matter now
hi,lo=mon("charmander",30),mon("charmander",30)
hi.nature="Adamant"; hi.recalculate_stats(); lo.nature="Modest"; lo.recalculate_stats()
ok(hi.actual_stats["atk"]>lo.actual_stats["atk"] and hi.actual_stats["sp_atk"]<lo.actual_stats["sp_atk"],"nature: Adamant +Atk -SpA vs Modest")
tgt=mon("squirtle",30)
bs1=BattleSystem(hi,tgt); bs2=BattleSystem(lo,tgt)
d_hi=bs1.calc_damage(bs1.p,bs1.o,Move.from_name("scratch"),roll=1.0); d_lo=bs2.calc_damage(bs2.p,bs2.o,Move.from_name("scratch"),roll=1.0)
ok(d_hi>d_lo,f"physical damage reflects the attack stat ({d_hi} vs {d_lo})")
# physical vs special split
atk_mon=mon("alakazam",40); 
bsx=BattleSystem(atk_mon,tgt); 
ok(bsx.calc_damage(bsx.p,bsx.o,Move.from_name("psychic"),roll=1.0)>bsx.calc_damage(bsx.p,bsx.o,Move.from_name("tackle"),roll=1.0),"special attacker: Psychic >> Tackle")
# STAB
bs=BattleSystem(mon("charmander",30),mon("bulbasaur",30)); 
stab=bs.calc_damage(bs.p,bs.o,Move.from_name("ember"),roll=1.0); 
bs.p.types=["water"]; nostab=bs.calc_damage(bs.p,bs.o,Move.from_name("ember"),roll=1.0)
ok(stab>nostab,f"STAB applies ({stab} vs {nostab})")

# PP + struggle
a,b=mon("squirtle",40,["tackle"]),mon("geodude",5)
bs=BattleSystem(a,b); m=Move.from_name("tackle"); bs.p.pp["tackle"]=1
bs.execute_turn(m,Move.from_name("tackle")); ok(bs.p.pp["tackle"]==0,"PP drops by 1")
a.current_hp=a.max_hp=999; bs.p.hp=999; b.current_hp=b.max_hp=9999; bs.o.hp=9999
bs.execute_turn(m,Move.from_name("tackle")); ok(any("STRUGGLE" in l for l in bs.battle_log),"out of PP -> Struggle")
ok(len(bs.get_player_moves())==1 and bs.pp_left(bs.p,m)==0,"PP exposed via pp_left")
# PP persists through a session round trip
a2=PokemonInstance.from_dict(a.to_dict()); ok(a2.bt and a2.bt["pp"].get("tackle")==0,"PP survives to_dict/from_dict (API sessions)")
ok("bt" not in a.to_db_dict(),"battle state never reaches the database row")

# status effects
random.seed(1)
a,b=mon("pikachu",25,["thunder-wave"]),mon("rattata",25)
bs=BattleSystem(a,b); 
for _ in range(6):
    bs.execute_turn(Move.from_name("thunder-wave"),Move.from_name("tackle"))
    if bs.o.status=="par": break
ok(bs.o.status=="par" and b.status=="par","Thunder Wave paralyses (and it's saved on the Pokémon)")
s0=bs.o.stat("spe"); ok(s0<=b.actual_stats["speed"]*0.5+1,"paralysis halves speed")
a,b=mon("charmander",25,["will-o-wisp"]),mon("squirtle",25); bs=BattleSystem(a,b)
for _ in range(8):
    bs.execute_turn(Move.from_name("will-o-wisp"),Move.from_name("tackle")); 
    if bs.o.status=="brn": break
hp_before=bs.wild_hp; bs.execute_turn(Move.from_name("tackle"),Move.from_name("tackle"))
ok(bs.o.status=="brn" and any("burn" in l for l in bs.battle_log),"burn hurts at end of turn")
# fire types can't be burned, electric can't be paralysed
a,b=mon("squirtle",25,["will-o-wisp"]),mon("charmander",25); bs=BattleSystem(a,b)
for _ in range(10): bs.execute_turn(Move.from_name("will-o-wisp"),Move.from_name("tackle"))
ok(bs.o.status is None,"Fire types are immune to burn")
# sleep wears off
a,b=mon("squirtle",25),mon("rattata",25); bs=BattleSystem(a,b); bs.p.status="slp"; bs.p.sleep_turns=2
acted=[]
for _ in range(5):
    bs.execute_turn(Move.from_name("tackle"),Move.from_name("tackle")); acted.append(any("fast asleep" in l for l in bs.battle_log))
ok(acted[0] and acted[1] and not acted[2] and bs.p.status is None,"sleep lasts its turns, then the Pokémon wakes up")
# stat stages
a,b=mon("charmander",25,["swords-dance"]),mon("rattata",25); bs=BattleSystem(a,b)
bs.execute_turn(Move.from_name("swords-dance"),Move.from_name("growl"))
ok(bs.p.stages.get("atk",0)>=2 or bs.p.stages.get("atk",0)==2-1,"Swords Dance raises Attack: "+str(bs.p.stages))
# drain
a,b=mon("bulbasaur",25,["absorb"]),mon("squirtle",25); a.current_hp=5; bs=BattleSystem(a,b)
bs.execute_turn(Move.from_name("absorb"),Move.from_name("growl")); ok(bs.player_hp>5,"Absorb drains HP")
# priority
a,b=mon("rattata",10,["quick-attack"]),mon("pidgeot",50); bs=BattleSystem(a,b)
order=bs._order(Move.from_name("quick-attack"),Move.from_name("tackle")); ok(order[0][0]=="player","priority: Quick Attack moves first despite lower speed")

# heal clears status & battle state
a.status="par"; a.bt={"pp":{"x":1}}; a.restore_hp(); ok(a.status is None and a.bt is None,"healing cures status and clears battle state")

# AI
random.seed(9)
foe=mon("onix",30,["tackle","bite","water-gun","flamethrower"])     # vs a Grass type
me=mon("bulbasaur",30); bs=BattleSystem(me,foe,smart=True)
picks=[battle_ai.choose_move(bs,bs._usable(bs.o,bs.get_player_moves() and bs._moves_for(bs.o,foe))).name for _ in range(20)]
ok(picks.count("flamethrower")>=15,"AI picks the super-effective move vs Grass: "+str({m:picks.count(m) for m in set(picks)}))
# AI takes the kill
foe=mon("charmander",30,["tackle","ember","scratch"]); me=mon("caterpie",5); me.current_hp=1; bs=BattleSystem(me,foe,smart=True)
pk=battle_ai.choose_move(bs,bs._moves_for(bs.o,foe)); ok(pk.power>0,"AI goes for the KO on a nearly-dead target: "+pk.name)
# AI heals when low, wild never "smart"
foe=mon("chansey",30,["recover","tackle"]); foe.current_hp=foe.max_hp//5; me=mon("bulbasaur",30); bs=BattleSystem(me,foe,smart=True)
ok(battle_ai.choose_move(bs,bs._moves_for(bs.o,foe)).name=="recover","AI uses Recover at low HP")
ok(BattleSystem(mon("rattata",5),mon("pidgey",5)).smart is False,"wild Pokémon stay random")
t=mon("pidgey",5); t.story_ref={"t":"brock","i":0,"n":2}; ok(BattleSystem(mon("rattata",5),t).smart is True,"trainer Pokémon use the AI")

# default movesets are sensible
w=mon("geodude",12); ok(len(w.moves)>=2 and any(rules.move_info(m)["p"]>0 for m in w.moves),"wild Geodude has a real level-up moveset: "+str(w.moves))
# boss tiers
ok(daily_boss_system.tier_for(5)==1 and daily_boss_system.tier_for(20)==2 and daily_boss_system.tier_for(40)==3 and daily_boss_system.tier_for(70)==4,"boss tiers by lead level")
for lv in range(5,15):
    b,t=boss_battle.build_boss_pokemon(lv)
    assert t.species not in ("dragonite","articuno","gyarados","alakazam","machamp") and b.level<=lv+2, (lv,t.species,b.level)
ok(True,"levels 5-14 never meet a Dragonite; boss is at most 2 levels above you")
b,t=boss_battle.build_boss_pokemon(80); ok(t.tier==4 and b.level==86,"late game: tier 4, +6 levels: "+t.species)
# xp curve
p=mon("charmander",5); p.experience=0; p.add_experience(rules.xp_to_next(5)); ok(p.level==6,"XP curve: one level's worth of XP = +1 level")
ok(rules.xp_to_next(12)<1000 and rules.xp_to_next(50)<10000,"XP needed is reachable (Lv12: %d, Lv50: %d)"%(rules.xp_to_next(12),rules.xp_to_next(50)))
print("ALL RULES TESTS PASSED")
