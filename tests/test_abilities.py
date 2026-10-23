import os, sys; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'harness.py')).read())
import random
from abilities_system import AbilitySystem as A
from battle_system import BattleSystem, Move
ok=lambda c,m: print(("PASS " if c else "FAIL ")+m) or (c or sys.exit(1))
# pure functions
d,n=A.modify_outgoing("blaze",100,"fire",30,100); ok(d==150 and n,"blaze boosts fire at low HP")
d,n=A.modify_outgoing("blaze",100,"fire",90,100); ok(d==100,"blaze inactive at high HP")
d,n=A.modify_outgoing("blaze",100,"water",10,100); ok(d==100,"blaze ignores non-fire")
d,h,n=A.modify_incoming("volt_absorb",50,"electric",1,40,100); ok(d==0 and h==25,"volt absorb: 0 dmg, heals 25%")
d,h,n=A.modify_incoming("lightning_rod",50,"electric",1,40,100); ok(d==0 and h==0,"lightning rod: electric nullified, no heal")
d,h,n=A.modify_incoming("dry_skin",50,"water",1,40,100); ok(d==0 and h==25,"dry skin: water heals 25%")
d,h,n=A.modify_incoming("filter",100,"rock",2.0,50,100); ok(d==75,"filter softens super effective")
d,h,n=A.modify_incoming("filter",100,"rock",1.0,50,100); ok(d==100,"filter neutral otherwise")
d,h,n=A.modify_incoming("multiscale",100,"rock",1.0,100,100); ok(d==50,"multiscale halves at full HP")
d,h,n=A.modify_incoming("multiscale",100,"rock",1.0,60,100); ok(d==100,"multiscale off when damaged")
d,h,n=A.modify_incoming("sturdy",999,"rock",1.0,100,100); ok(d==99,"sturdy leaves 1 HP from full")
d,h,n=A.modify_incoming("sturdy",999,"rock",1.0,50,100); ok(d==999,"sturdy inactive when damaged")
ok(A.modify_incoming("nonsense",10,"fire",1,10,10)[0]==10 and A.modify_outgoing(None,10,"fire",1,1)[0]==10,"unknown/None ability = no-op")
ok(A.pick_ability(["keen-eye"],["normal"]) is None,"no match -> None")
ok(A.pick_ability(["solar-power"],["fire"])=="blaze","type default fallback")
ok(A.pick_ability(["intimidate","moxie"],["water"])=="intimidate","API ability preferred")
# through the real engine
import pokemon_model
def mk(sp,lv,ab=None,hp=None):
    p=pokemon_model.PokemonInstance(sp,lv,1); 
    if ab is not None: p.ability=ab
    if hp is not None: p.current_hp=hp
    return p
random.seed(3)
class W:  # engine expects attack/defense/speed/types attrs
    def __init__(s,p): s._p=p
    def __getattr__(s,k): return getattr(s._p,k)
    attack=property(lambda s:s._p.actual_stats["atk"]); defense=property(lambda s:s._p.actual_stats["def"]); speed=property(lambda s:s._p.actual_stats["speed"])
    types=property(lambda s:s._p.api_data.get("types",["normal"]))
att=mk("charmander",30,"blaze"); att.current_hp=att.max_hp//4
dfn=mk("pikachu",30,None)
tot_b=tot_n=0
for i in range(200):
    for ab,acc in (("blaze","b"),(None,"n")):
        att.ability=ab
        b=BattleSystem(W(att),W(dfn)); m=Move("ember",power=40,accuracy=100,move_type="fire")
        b.wild_hp=dfn.max_hp; random.seed(i); b._execute_move(m,"player",b.wild_pokemon,b.wild_hp)
        dmg=dfn.max_hp-b.wild_hp
        if acc=="b": tot_b+=dmg
        else: tot_n+=dmg
ok(tot_b>tot_n*1.3, f"engine: Blaze at low HP hits harder ({tot_b} vs {tot_n})")
# absorb via engine: pikachu volt absorb takes 0 from electric move and heals
dfn.ability="volt_absorb"; att.ability=None
b=BattleSystem(W(att),W(dfn)); b.wild_hp=dfn.max_hp//2
b._execute_move(Move("thunderbolt",power=90,accuracy=100,move_type="electric"),"player",b.wild_pokemon,b.wild_hp)
ok(b.wild_hp>dfn.max_hp//2 and any("absorbed" in l for l in b.battle_log),"engine: Volt Absorb heals instead of damaging; log: "+b.battle_log[-2])
print("ALL ABILITY TESTS PASSED")
