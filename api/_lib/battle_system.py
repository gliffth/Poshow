"""
Turn-based 1v1 battle engine.

Rules covered:
  * real stats (IV/EV/nature), the physical / special split and stat stages
  * the 18-type chart with immunities, STAB and critical hits
  * accuracy / evasion, move priority and speed order (stages, paralysis)
  * PP per move (Struggle when out), status conditions (burn, poison, toxic, paralysis, sleep, freeze,
    confusion, flinch), secondary effects, drain / recoil / healing / recharge / self-KO
  * abilities (abilities_system.py, ability_events.py)
  * wild Pokémon pick moves at random; trainers, bosses and gym leaders use battle_ai.py

Used by the API and the Telegram bot: BattleSystem(player, opponent), get_player_moves(), get_opponent_move(),
execute_turn(player_move, opponent_move), .player_hp / .wild_hp / .is_finished / .winner / .battle_log.
"""

import logging
import random
from typing import Dict, List, Optional

import rules
import glyphs as G
import ability_events as AE

logger = logging.getLogger(__name__)

INFO_NAME = {k: v[0] for k, v in AE.INFO.items()}
STAGE_NAMES = {"atk": "Attack", "def": "Defense", "spa": "Sp. Atk", "spd": "Sp. Def", "spe": "Speed",
               "acc": "accuracy", "eva": "evasiveness"}
STATUS_TEXT = {"brn": "was burned", "psn": "was poisoned", "tox": "was badly poisoned",
               "par": "was paralyzed", "slp": "fell asleep", "frz": "was frozen solid"}
# type -> status it can't have
STATUS_IMMUNE = {"brn": ("fire",), "par": ("electric",), "psn": ("poison", "steel"), "tox": ("poison", "steel"),
                 "frz": ("ice",), "slp": ()}


# ── Move ──

class Move:
    """A move as the battle sees it. Built from rules.move_info() so it carries real PP / effects."""

    CATEGORY = {"p": "physical", "s": "special", "x": "status"}

    def __init__(self, name: str, power: int = 40, accuracy: int = 100, move_type: str = "normal",
                 category: str = "physical", pp: Optional[int] = None, priority: int = 0, fx: Optional[list] = None):
        self.name = name
        self.power = power
        self.accuracy = accuracy
        self.move_type = move_type
        self.category = category
        self.max_pp = pp if pp is not None else 25
        self.priority = priority
        self.fx = fx or []

    @classmethod
    def from_name(cls, name: str) -> "Move":
        d = rules.move_info(name)
        return cls(name, power=d["p"], accuracy=d["a"], move_type=d["t"], category=cls.CATEGORY[d["c"]],
                   pp=d["pp"], priority=d["pr"], fx=d["fx"])

    def __repr__(self):
        return f"Move({self.name}, P:{self.power}, A:{self.accuracy}%)"

    def get_type_effectiveness(self, defender_types: List[str]) -> float:
        return rules.type_multiplier(self.move_type, defender_types)

    # kept for older callers/tests: plain damage with no STAB/stages
    def calculate_damage(self, attacker_stats: Dict, defender_stats: Dict, defender_types: List[str]) -> int:
        level = attacker_stats.get("level", 5)
        attack = attacker_stats.get("attack", 10)
        defense = max(1, defender_stats.get("defense", 10))
        base = max(1, int(((2 * level / 5 + 2) * self.power * attack / defense) / 50 + 2))
        crit = 1.5 if random.random() < 1 / 16 else 1.0
        return max(1, int(base * crit * self.get_type_effectiveness(defender_types) * random.uniform(0.85, 1.0)))


# ── COMBATANT — one side's live battle state ──

def _under(mon):
    """The real Pokemon behind an adapter (BattleReadyPokemon keeps it in ._p)."""
    return getattr(mon, "_p", mon)


def type_names(mon) -> List[str]:
    direct = getattr(mon, "types", None)
    if direct:
        return [str(t).lower() for t in direct]
    raw = (getattr(_under(mon), "api_data", None) or {}).get("types", [])
    out = [(t if isinstance(t, str) else t.get("type", {}).get("name", "")).lower() for t in raw]
    return [t for t in out if t] or ["normal"]


class Combatant:
    def __init__(self, mon, hp: int):
        self.mon = mon
        self.real = _under(mon)
        self.hp = hp
        self.max_hp = int(getattr(mon, "max_hp", hp) or hp)
        self.level = int(getattr(mon, "level", 5))
        self.types = type_names(mon)
        self.ability = getattr(mon, "ability", None)
        self.stats = self._read_stats(mon)

        bt = getattr(self.real, "bt", None) or {}
        self.stages: Dict[str, int] = dict(bt.get("stages") or {})
        self.pp: Dict[str, int] = dict(bt.get("pp") or {})
        self.confused: int = int(bt.get("conf", 0))
        self.sleep_turns: int = int(bt.get("slp", 0))
        self.tox: int = int(bt.get("tox", 0))
        self.recharge: bool = bool(bt.get("rch", False))
        self.status: Optional[str] = getattr(self.real, "status", None) or None
        self.flinched = False
        self.entered: bool = bool(bt.get("ent", False))
        self.ff: bool = bool(bt.get("ff", False))        # Flash Fire has been triggered
        self.weather: Optional[str] = None
        self.ab = AE.norm(self.ability)

    @staticmethod
    def _read_stats(mon) -> Dict[str, int]:
        a = getattr(_under(mon), "actual_stats", None)
        if isinstance(a, dict) and a:
            return {"atk": a.get("atk", 10), "def": a.get("def", 10), "spa": a.get("sp_atk", a.get("atk", 10)),
                    "spd": a.get("sp_def", a.get("def", 10)), "spe": a.get("speed", 50)}
        atk, dfn = getattr(mon, "attack", 10), getattr(mon, "defense", 10)      # plain stat attributes (tests, stubs)
        return {"atk": atk, "def": dfn, "spa": getattr(mon, "sp_attack", atk), "spd": getattr(mon, "sp_defense", dfn),
                "spe": getattr(mon, "speed", 50)}

    def stat(self, key: str) -> float:
        n = max(-6, min(6, self.stages.get(key, 0)))
        mult = (2 + n) / 2 if n >= 0 else 2 / (2 - n)
        value = self.stats[key] * mult
        if key == "spe":
            if self.status == "par":
                value *= 0.5
            value *= AE.speed_mult(self.ability, self.weather)
        elif key == "def":
            if self.ab == "fur_coat":
                value *= 2
            elif self.ab == "marvel_scale" and self.status:
                value *= 1.5
        elif key == "atk":
            if self.ab in ("huge_power", "pure_power"):
                value *= 2
            elif self.ab == "guts" and self.status:
                value *= 1.5
        return value

    def acc_mult(self) -> float:
        n = max(-6, min(6, self.stages.get("acc", 0)))
        return (3 + n) / 3 if n >= 0 else 3 / (3 - n)

    def eva_mult(self) -> float:
        n = max(-6, min(6, self.stages.get("eva", 0)))
        return (3 + n) / 3 if n >= 0 else 3 / (3 - n)

    def save(self):
        """Write the state that outlives a single request back onto the Pokemon."""
        self.real.status = self.status
        self.real.current_hp = max(0, min(self.max_hp, int(self.hp)))      # damage sticks after the battle
        bt = {"stages": {k: v for k, v in self.stages.items() if v}, "pp": self.pp,
              "conf": self.confused, "slp": self.sleep_turns, "tox": self.tox, "rch": self.recharge, "ent": self.entered}
        if self.ff:
            bt["ff"] = True
        self.real.bt = bt
        w = getattr(self, "weather_state", None)
        if w:
            self.real.bt["w"] = w


# ── Battle ──

class BattleSystem:
    """Manages one turn-based battle"""

    def __init__(self, player_pokemon, wild_pokemon, smart: Optional[bool] = None, labels=None):
        # labels = (name for side 1, name for side 2); the default ("You" / the species) suits PvE,
        # PvP passes "Ash's Pikachu" / "Gary's Onix" so the log reads the same for both players
        self.labels = labels
        self.player_pokemon = player_pokemon
        self.wild_pokemon = wild_pokemon
        self.p = Combatant(player_pokemon, player_pokemon.current_hp)
        self.o = Combatant(wild_pokemon, wild_pokemon.current_hp)

        real = _under(wild_pokemon)
        self.smart = bool(smart) if smart is not None else bool(
            getattr(real, "is_boss", False) or getattr(real, "gym_floor", 0) or getattr(real, "story_ref", None))

        wt = (getattr(self.p.real, "bt", None) or {}).get("w") or (getattr(self.o.real, "bt", None) or {}).get("w")
        self.weather: Optional[str] = wt[0] if wt else None
        self.weather_turns: int = int(wt[1]) if wt else 0
        self._sync_weather()

        self.turn = 0
        self.is_finished = False
        self.winner = None
        self.battle_log: List[str] = []

    def _sync_weather(self):
        self.p.weather = self.o.weather = self.weather

    def _set_weather(self, weather: str, who: str):
        if self.weather == weather:
            return
        self.weather, self.weather_turns = weather, AE.WEATHER_TURNS
        self._sync_weather()
        self.battle_log.append(f"{G.WEATHER} {who} brought on {AE.WEATHER_NAME[weather]}!")

    # HP is exposed under the names the API/bot already use
    @property
    def player_hp(self) -> int:
        return self.p.hp

    @player_hp.setter
    def player_hp(self, v: int):
        self.p.hp = v

    @property
    def wild_hp(self) -> int:
        return self.o.hp

    @wild_hp.setter
    def wild_hp(self, v: int):
        self.o.hp = v

    # ── moves ──────────────────────────────────────────────────────
    def _move_names(self, mon) -> List[str]:
        names = list(getattr(mon, "moves", None) or [])[:4]
        return [n for n in names if isinstance(n, str)] or ["tackle"]

    def _moves_for(self, c: Combatant, mon) -> List[Move]:
        out = []
        for n in self._move_names(mon):
            m = Move.from_name(n)
            c.pp.setdefault(m.name, m.max_pp)
            out.append(m)
        return out

    def pp_left(self, c: Combatant, move: Move) -> int:
        return c.pp.get(move.name, move.max_pp)

    def get_player_moves(self) -> List[Move]:
        try:
            return self._moves_for(self.p, self.player_pokemon)
        except Exception as e:
            logger.error(f"Error getting player moves: {e}")
            return [Move("tackle")]

    def _usable(self, c: Combatant, moves: List[Move]) -> List[Move]:
        return [m for m in moves if self.pp_left(c, m) > 0]

    def get_opponent_move(self) -> Move:
        try:
            moves = self._moves_for(self.o, self.wild_pokemon)
            usable = self._usable(self.o, moves)
            if not usable:
                return Move.from_name("struggle")
            if self.smart:
                import battle_ai
                return battle_ai.choose_move(self, usable)
            return random.choice(usable)
        except Exception as e:
            logger.error(f"Error getting opponent move: {e}")
            return Move("tackle")

    # ── damage ─────────────────────────────────────────────────────
    def calc_damage(self, att: Combatant, dfn: Combatant, move: Move, roll: Optional[float] = None,
                    crit: bool = False) -> int:
        """Damage for one hit (before abilities). roll=None draws the random 85-100% factor; AI passes 0.925."""
        if move.power <= 0:
            return 0
        eff = move.get_type_effectiveness(dfn.types)
        if eff == 0:
            return 0
        special = move.category == "special"
        a = att.stat("spa" if special else "atk")
        d = dfn.stat("spd" if special else "def")
        if crit:                                   # crits ignore the attacker's drops / the defender's boosts
            a = max(a, att.stats["spa" if special else "atk"])
            d = min(d, dfn.stats["spd" if special else "def"])
        power = move.power
        facade = any(f[0] == "facade" for f in move.fx) and att.status in ("brn", "psn", "tox", "par")
        if facade:
            power *= 2
        if att.ab == "technician" and power <= 60:
            power = int(power * 1.5)
        base = ((2 * att.level / 5 + 2) * power * a / max(1.0, d)) / 50 + 2
        mult = eff
        if move.move_type in att.types:
            mult *= 2.0 if att.ab == "adaptability" else 1.5      # STAB
        if crit:
            mult *= 1.5
        if att.status == "brn" and not special and att.ab != "guts" and not facade:
            mult *= 0.5
        mult *= AE.weather_damage_mult(move.move_type, self.weather)
        if dfn.ab == "thick_fat" and move.move_type in ("fire", "ice"):
            mult *= 0.5
        if dfn.ab == "heatproof" and move.move_type == "fire":
            mult *= 0.5
        if eff > 1 and dfn.ab in AE.SUPER_EFFECTIVE_REDUCE:
            mult *= 0.75
        if eff < 1 and att.ab == "tinted_lens":
            mult *= 2.0
        if att.ab == "flash_fire" and att.ff and move.move_type == "fire":
            mult *= 1.5
        if att.ab == "reckless" and any(f[0] == "recoil" for f in move.fx):
            mult *= 1.2
        mult *= roll if roll is not None else random.uniform(0.85, 1.0)
        return max(1, int(base * mult))

    # ── turn ───────────────────────────────────────────────────────
    def execute_turn(self, player_move: Move, opponent_move: Move) -> Dict:
        self.turn += 1
        self.battle_log = []
        try:
            for c in (self.p, self.o):
                c.flinched = False
            self._enter_events()

            # a player move with no PP left becomes Struggle
            if player_move is not None and self.pp_left(self.p, player_move) <= 0:
                player_move = Move.from_name("struggle")
            if opponent_move is not None and self.pp_left(self.o, opponent_move) <= 0:
                opponent_move = Move.from_name("struggle")

            if player_move is None or opponent_move is None:        # the other side switched Pokémon this turn
                order = [("player", player_move)] if opponent_move is None else [("opponent", opponent_move)]
                order = [o for o in order if o[1] is not None]
            else:
                order = self._order(player_move, opponent_move)
            for side, move in order:
                if self.is_finished:
                    break
                self._act(side, move, moved_first=(side == order[0][0]))

            if not self.is_finished:
                self._end_of_turn()
                self._weather_tick()

            self.battle_log.append(f"\nTurn {self.turn}")
            return {"log": self.battle_log, "is_finished": self.is_finished, "winner": self.winner}
        except Exception as e:
            logger.exception(f"Turn execution error: {e}")
            raise
        finally:
            ws = [self.weather, self.weather_turns] if self.weather else None
            self.p.weather_state = self.o.weather_state = ws
            self.p.save()
            self.o.save()

    def _enter_events(self):
        """Abilities that trigger when a Pokémon enters the battle (once per Pokémon — remembered in its saved state)."""
        for side in ("player", "opponent"):
            att_name, def_name, att, dfn = self._names(side)
            if att.entered or att.hp <= 0:
                continue
            att.entered = True
            if att.ab == "intimidate":
                self.battle_log.append(f"{G.ABILITY} {att_name}'s Intimidate!")
                self._secondary(["stage", "atk", -1, 100, "foe"], att, dfn, att_name, def_name, True, from_status=True, foe_effect=True)
            elif att.ab in AE.ENTRY_WEATHER:
                self._set_weather(AE.ENTRY_WEATHER[att.ab], att_name)

    def _weather_tick(self):
        if not self.weather:
            return
        for side in ("player", "opponent"):
            name, _, c, _o = self._names(side)
            if c.hp <= 0:
                continue
            if self.weather in ("sand", "hail") and not AE.chip_immune(c.types, self.weather) and c.ab not in ("overcoat", "magic_guard"):
                d = max(1, c.max_hp // 16)
                self._damage(c, d)
                self.battle_log.append(f"{G.RECOIL} {name} is buffeted by the {'sandstorm' if self.weather == 'sand' else 'hail'}! ({d})")
            elif self.weather == "rain" and c.ab == "rain_dish" and c.hp < c.max_hp:
                c.hp = min(c.max_hp, c.hp + max(1, c.max_hp // 16))
                self.battle_log.append(f"{G.HEAL} {name}'s Rain Dish restored a little HP.")
            self._check_faint()
        self.weather_turns -= 1
        if self.weather_turns <= 0:
            self.battle_log.append(f"{G.WEATHER} The {AE.WEATHER_NAME[self.weather].replace('harsh ', '')} faded.")
            self.weather = None
        self._sync_weather()

    def _order(self, pm: Move, om: Move):
        if pm.priority != om.priority:
            first_is_player = pm.priority > om.priority
        else:
            ps, os_ = self.p.stat("spe"), self.o.stat("spe")
            first_is_player = ps > os_ if ps != os_ else random.random() < 0.5
        player, opp = ("player", pm), ("opponent", om)
        return [player, opp] if first_is_player else [opp, player]

    def _names(self, side: str):
        if self.labels:
            a, b = self.labels
            return (a, b, self.p, self.o) if side == "player" else (b, a, self.o, self.p)
        if side == "player":
            return "You", "Wild", self.p, self.o
        return f"{self.wild_pokemon.species_name}", "You", self.o, self.p

    def _act(self, side: str, move: Move, moved_first: bool):
        att_name, def_name, att, dfn = self._names(side)
        log = self.battle_log

        # can this Pokemon act at all?
        if att.recharge:
            att.recharge = False
            log.append(f"{G.STATUS} {att_name} must recharge!")
            return
        if att.flinched:
            log.append(f"{G.STATUS} {att_name} flinched and couldn't move!")
            return
        if att.status == "slp":
            if att.sleep_turns > 0:
                att.sleep_turns -= 1
                log.append(f"{G.STATUS} {att_name} is fast asleep.")
                return
            att.status = None
            log.append(f"{G.UP} {att_name} woke up!")
        if att.status == "frz":
            if random.random() < 0.2:
                att.status = None
                log.append(f"{G.UP} {att_name} thawed out!")
            else:
                log.append(f"{G.STATUS} {att_name} is frozen solid!")
                return
        if att.status == "par" and random.random() < 0.25:
            log.append(f"{G.STATUS} {att_name} is paralyzed and can't move!")
            return
        if att.confused > 0:
            att.confused -= 1
            if att.confused == 0:
                log.append(f"{G.UP} {att_name} snapped out of confusion!")
            elif random.random() < 1 / 3:
                hit = max(1, int(((2 * att.level / 5 + 2) * 40 * att.stat("atk") / max(1.0, att.stat("def"))) / 50 + 2))
                self._damage(att, hit)
                log.append(f"{G.RECOIL} {att_name} hurt itself in confusion! ({hit})")
                self._check_faint()
                return

        # spend PP
        if move.name != "struggle":
            att.pp[move.name] = self.pp_left(att, move) - 1
        log.append(f"{G.MOVE} {att_name} used {move.name.upper().replace('-', ' ')}!")

        # accuracy
        if move.accuracy and move.accuracy > 0:
            chance = move.accuracy * att.acc_mult() / dfn.eva_mult()
            if random.random() * 100 > chance:
                log.append(f"{G.MISS} {att_name}'s {move.name} missed!")
                return

        if move.category == "status":
            targets_foe = any(f[0] in ("status", "confuse") or (f[0] == "stage" and f[4] == "foe") for f in move.fx)
            if dfn.ab == "magic_bounce" and targets_foe:
                log.append(f"{G.ABILITY} {def_name}'s Magic Bounce reflected {move.name.replace('-', ' ')}!")
                self._status_move(dfn, att, def_name, att_name, move)
            else:
                self._status_move(att, dfn, att_name, def_name, move)
            return

        eff = move.get_type_effectiveness(dfn.types)
        if dfn.ab == "flash_fire" and move.move_type == "fire" and move.power > 0:
            dfn.ff = True
            log.append(f"{G.ABILITY} {def_name}'s Flash Fire absorbed the attack! Its Fire moves are stronger now.")
            return
        if dfn.ab == "levitate" and move.move_type == "ground":
            eff = 0
        if eff == 0:
            log.append(f"{G.IMMUNE} It doesn't affect {def_name}...")
            return

        hits = 1
        for f in move.fx:
            if f[0] == "multihit":
                hits = f[1] if f[1] == f[2] else random.choices([2, 3, 4, 5], [3, 3, 1, 1])[0]
        dealt, heal, notes, crit_seen, landed = 0, 0, [], False, 0
        for _hit in range(hits):
            if dfn.hp <= 0:
                break
            crit = random.random() < 1 / 16 and dfn.ab not in AE.NO_CRIT
            damage = self.calc_damage(att, dfn, move, crit=crit)
            try:
                from abilities_system import AbilitySystem
                damage, note = AbilitySystem.modify_outgoing(att.ability, damage, move.move_type, att.hp, att.max_hp)
                if note and note not in notes:
                    notes.append(note)
                damage, h, note = AbilitySystem.modify_incoming(dfn.ability, damage, move.move_type, eff, dfn.hp, dfn.max_hp)
                heal += h
                if note and note not in notes:
                    notes.append(note)
            except Exception as e:
                logger.error(f"Ability hook error: {e}")
            damage = max(0, damage)
            if any(f[0] == "falseswipe" for f in move.fx):
                damage = min(damage, max(0, dfn.hp - 1))          # False Swipe never knocks out
            hp_before = dfn.hp
            self._damage(dfn, damage)
            taken = min(damage, hp_before)           # recoil / drain follow the HP actually taken, not the overkill
            dealt += taken
            landed += 1
            crit_seen = crit_seen or (crit and taken > 0)
            if move.category == "physical" and taken:
                self._contact(att, dfn, att_name, def_name)
        if heal:
            dfn.hp = min(dfn.max_hp, dfn.hp + heal)
        msg = f" {G.SUPER} Super effective!" if eff > 1 else f" {G.WEAK} Not very effective..." if eff < 1 else ""
        log.append(f"{G.HIT} {dealt} damage to {def_name}!{msg}")
        if landed > 1:
            log.append(f"{G.MOVE} It hit {landed} times!")
        if crit_seen:
            log.append(f"{G.CRIT} A critical hit!")
        log.extend(notes)
        if dfn.hp <= 0 and att.ab == "moxie" and att.hp > 0:
            att.stages["atk"] = min(6, att.stages.get("atk", 0) + 1)
            log.append(f"{G.ABILITY} {att_name}'s Moxie raised its Attack!")
        log.append(f"{G.HP} HP: {max(0, dfn.hp)}/{dfn.max_hp}")

        # secondary effects (only if the target is still standing)
        for fx in move.fx:
            kind = fx[0]
            if kind == "drain" and dealt:
                gain = max(1, int(dealt * fx[1]))
                att.hp = min(att.max_hp, att.hp + gain)
                log.append(f"{G.HEAL} {att_name} drained {gain} HP.")
            elif kind == "recoil" and dealt and (att.ab in ("rock_head", "magic_guard") and move.name != "struggle"):
                continue
            elif kind == "recoil" and dealt:
                back = max(1, int(dealt * fx[1])) if move.name != "struggle" else max(1, att.max_hp // 4)
                self._damage(att, back)
                log.append(f"{G.RECOIL} {att_name} was hurt by recoil ({back}).")
            elif kind == "selfko":
                att.hp = 0
            elif kind == "recharge":
                att.recharge = True
            elif dfn.hp > 0:
                self._secondary(fx, att, dfn, att_name, def_name, moved_first)
        if move.name == "struggle" and att.ab != "magic_guard":
            back = max(1, att.max_hp // 4)
            self._damage(att, back)
            log.append(f"{G.RECOIL} {att_name} was hurt by recoil ({back}).")
        self._check_faint()

    def _status_move(self, att, dfn, att_name, def_name, move):
        log = self.battle_log
        did = False
        for fx in move.fx:
            kind = fx[0]
            if kind == "heal":
                gain = max(1, int(att.max_hp * fx[1]))
                if att.hp >= att.max_hp:
                    log.append(f"{G.HEAL} {att_name}'s HP is already full!")
                else:
                    att.hp = min(att.max_hp, att.hp + gain)
                    log.append(f"{G.HEAL} {att_name} recovered HP! ({att.hp}/{att.max_hp})")
                did = True
            else:
                did = self._secondary(fx, att, dfn, att_name, def_name, True, from_status=True) or did
        if not move.fx or not did:
            if not move.fx:
                log.append("…but nothing happened.")

    def _secondary(self, fx, att, dfn, att_name, def_name, moved_first, from_status=False, foe_effect=False) -> bool:
        log = self.battle_log
        kind = fx[0]
        if kind == "status":
            _, code, chance, who = fx
            if not from_status and random.random() * 100 >= chance:
                return False
            if dfn.status:
                if from_status:
                    log.append(f"{G.IMMUNE} {def_name} already has a status condition.")
                return False
            if code in AE.STATUS_BLOCK.get(dfn.ab, ()):
                if from_status:
                    log.append(f"{G.ABILITY} {def_name}'s {INFO_NAME.get(dfn.ab, dfn.ab)} prevents that!")
                return False
            if any(t in dfn.types for t in STATUS_IMMUNE.get(code, ())):
                if from_status:
                    log.append(f"{G.IMMUNE} It doesn't affect {def_name}...")
                return False
            dfn.status = code
            if code == "slp":
                dfn.sleep_turns = random.randint(1, 3)
            if code == "tox":
                dfn.tox = 0
            log.append(f"{G.STATUS} {def_name} {STATUS_TEXT[code]}!")
            return True
        if kind == "stage":
            _, stat, n, chance, who = fx
            if not from_status and random.random() * 100 >= chance:
                return False
            target, name = (att, att_name) if who == "self" else (dfn, def_name)
            if n < 0 and who != "self" and (target.ab in AE.NO_DROP_ALL or (target.ab == "hyper_cutter" and stat == "atk")):
                log.append(f"{G.ABILITY} {name}'s {INFO_NAME.get(target.ab, target.ab)} prevents its stats from being lowered!")
                return False
            old = target.stages.get(stat, 0)
            new = max(-6, min(6, old + n))
            if new == old:
                log.append(f"…{name}'s {STAGE_NAMES[stat]} won't go any {'higher' if n > 0 else 'lower'}!")
                return False
            target.stages[stat] = new
            word = ("sharply " if abs(n) >= 2 else "") + ("rose" if n > 0 else "fell")
            if n < 0 and who == "foe":        # a foe lowered our stat: Competitive / Defiant answer
                reply = {"competitive": "spa", "defiant": "atk"}.get(target.ab)
                if reply:
                    target.stages[reply] = min(6, target.stages.get(reply, 0) + 2)
                    log.append(f"{G.ABILITY} {name}'s {INFO_NAME.get(target.ab, target.ab)} sharply raised its {STAGE_NAMES[reply]}!")
            log.append(f"{G.UP if n > 0 else G.DOWN} {name}'s {STAGE_NAMES[stat]} {word}!")
            return True
        if kind == "confuse":
            if dfn.ab == "own_tempo":
                if from_status:
                    log.append(f"{G.ABILITY} {def_name}'s Own Tempo prevents confusion!")
                return False
            if random.random() * 100 >= fx[1] or dfn.confused > 0:
                return False
            dfn.confused = random.randint(2, 4)
            log.append(f"{G.STATUS} {def_name} became confused!")
            return True
        if kind == "flinch":
            if moved_first and dfn.ab != "inner_focus" and random.random() * 100 < fx[1]:
                dfn.flinched = True
            return False
        return False

    def _contact(self, att: Combatant, dfn: Combatant, att_name: str, def_name: str):
        """Abilities that answer a physical hit: Static / Flame Body / Poison Point / Effect Spore / Rough Skin."""
        if att.hp <= 0:
            return
        if dfn.ab in AE.CONTACT_STATUS and random.random() < 0.3:
            self._secondary(["status", AE.CONTACT_STATUS[dfn.ab], 100, "foe"], dfn, att, def_name, att_name, True, from_status=True)
        elif dfn.ab == "effect_spore" and random.random() < 0.3:
            code = random.choice(["slp", "par", "psn"])
            self._secondary(["status", code, 100, "foe"], dfn, att, def_name, att_name, True, from_status=True)
        elif dfn.ab in AE.CONTACT_CHIP and att.ab != "magic_guard":
            d = max(1, att.max_hp // 8)
            self._damage(att, d)
            self.battle_log.append(f"{G.RECOIL} {att_name} was hurt by {def_name}'s {INFO_NAME.get(dfn.ab, dfn.ab)}! ({d})")

    def _damage(self, c: Combatant, amount: int):
        c.hp = max(0, c.hp - max(0, amount))

    def _check_faint(self):
        if self.is_finished:
            return
        if self.o.hp <= 0:
            self.is_finished = True
            self.winner = "player"
            self.battle_log.append(f"{G.FAINT} {self.labels[1] if self.labels else self.wild_pokemon.species_name} fainted!")
        elif self.p.hp <= 0:
            self.is_finished = True
            self.winner = "opponent"
            self.battle_log.append(f"{G.FAINT} {self.labels[0] if self.labels else 'Your Pokemon'} fainted!")

    def _end_of_turn(self):
        for side in ("player", "opponent"):
            if self.is_finished:
                return
            name, _, c, _o = self._names(side)
            if c.hp <= 0:
                continue
            if c.ab == "speed_boost":
                if c.stages.get("spe", 0) < 6:
                    c.stages["spe"] = c.stages.get("spe", 0) + 1
                    self.battle_log.append(f"{G.ABILITY} {name}'s Speed Boost raised its Speed!")
            if c.ab == "magic_guard":
                pass                       # no indirect damage at all
            elif c.ab == "poison_heal" and c.status in ("psn", "tox"):
                if c.hp < c.max_hp:
                    c.hp = min(c.max_hp, c.hp + max(1, c.max_hp // 8))
                    self.battle_log.append(f"{G.HEAL} {name}'s Poison Heal restored HP.")
            elif c.status == "brn":
                d = max(1, c.max_hp // 16)
                self._damage(c, d)
                self.battle_log.append(f"{G.RECOIL} {name} is hurt by its burn! ({d})")
            elif c.status == "psn":
                d = max(1, c.max_hp // 8)
                self._damage(c, d)
                self.battle_log.append(f"{G.POISON} {name} is hurt by poison! ({d})")
            elif c.status == "tox":
                c.tox += 1
                d = max(1, c.max_hp * min(c.tox, 15) // 16)
                self._damage(c, d)
                self.battle_log.append(f"{G.POISON} {name} is badly poisoned! ({d})")
            self._check_faint()

    # kept for older callers/tests (they drive a single move directly)
    def _execute_move(self, move: Move, attacker_type: str, defender_pokemon=None, defender_hp: int = 0):
        self.battle_log = []
        self._act(attacker_type, move, moved_first=True)
        self.p.save()
        self.o.save()


if __name__ == "__main__":
    print("Battle System V3 loaded ✅")
