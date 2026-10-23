"""
Opponent AI for trainers, gym leaders, bosses and the Elite Four.

Wild Pokémon keep picking at random. Everything else scores every usable move against the current
board state and plays the best one:

  * damage: the real damage formula (STAB, type chart, stages, burn, abilities' effect on power are
    ignored) at the average roll, as a fraction of the defender's remaining HP — a KO scores highest
  * accuracy: expected damage is weighted by hit chance
  * priority: a priority move that finishes the target gets a big bonus
  * status moves: worth it when they would land (target has no status and isn't immune) and the
    battle isn't about to end; healing when low; setup (+Atk/+SpA/+Spe) only when healthy and not
    already boosted; debuffs rarely
  * no suicide plays: self-KO moves only as a last resort; recharge moves penalised
  * a little noise so fights aren't perfectly predictable (higher-level trainers use less)

It reads the SAME rules as the battle engine, so what the AI "thinks" a move does is what it does.
"""

import random
from typing import List

import rules

SETUP_STATS = {"atk", "spa", "spe", "def", "spd"}


def _expected_damage(bs, att, dfn, move) -> float:
    if move.power <= 0:
        return 0.0
    dmg = bs.calc_damage(att, dfn, move, roll=0.925, crit=False)
    acc = 1.0 if not move.accuracy else min(1.0, move.accuracy * att.acc_mult() / dfn.eva_mult() / 100)
    return dmg * acc


def _score(bs, att, dfn, move) -> float:
    dmg = _expected_damage(bs, att, dfn, move)
    hp_frac = att.hp / max(1, att.max_hp)
    foe_frac = dfn.hp / max(1, dfn.max_hp)
    score = 0.0

    if move.power > 0:
        frac = dmg / max(1, dfn.hp)
        score += min(frac, 1.0) * 100
        if dmg >= dfn.hp:                           # a clean KO beats everything
            score += 120
            if move.priority > 0:
                score += 40
        eff = move.get_type_effectiveness(dfn.types)
        if eff == 0:
            return -1000.0
        if eff > 1:
            score += 8
        for fx in move.fx:
            kind = fx[0]
            if kind == "selfko":
                score -= 90 if hp_frac > 0.25 else 0
            elif kind == "recharge":
                score -= 20 if dmg < dfn.hp else 0
            elif kind == "recoil":
                score -= 6
            elif kind == "drain":
                score += 10 * (1 - hp_frac)
            elif kind == "status" and not dfn.status and dfn.hp > 0:
                score += fx[2] / 100 * 12
            elif kind == "flinch":
                score += fx[1] / 100 * 5
        return score

    # ---- status / setup moves ----
    for fx in move.fx:
        kind = fx[0]
        if kind == "heal":
            if hp_frac < 0.45:
                score += 70 * (1 - hp_frac)
            else:
                score -= 40
        elif kind == "status":
            code = fx[1]
            if dfn.status or foe_frac < 0.25:
                score -= 40
            elif any(t in dfn.types for t in __import__("battle_system").STATUS_IMMUNE.get(code, ())):
                score -= 60
            else:
                score += {"slp": 38, "par": 30, "brn": 28, "tox": 30, "psn": 22, "frz": 36}.get(code, 20)
        elif kind == "stage":
            _, stat, n, _chance, who = fx
            have = att.stages.get(stat, 0) if who == "self" else dfn.stages.get(stat, 0)
            if who == "self" and n > 0 and stat in SETUP_STATS:
                if hp_frac > 0.6 and have < 2:
                    score += 24 - 8 * have
                else:
                    score -= 25
            elif who == "foe" and n < 0:
                score += 6 if have > -2 and foe_frac > 0.5 else -20
            else:
                score -= 15
        elif kind == "confuse":
            score += 14 if dfn.confused == 0 else -20
    return score - 5 if score == 0 else score


def choose_move(bs, usable: List) -> object:
    att, dfn = bs.o, bs.p
    scored = [(_score(bs, att, dfn, m), m) for m in usable]
    # trainers with higher-level teams play cleaner
    noise = 14 if att.level < 20 else 8 if att.level < 40 else 4
    best = max(scored, key=lambda sm: sm[0] + random.uniform(0, noise))
    return best[1]
