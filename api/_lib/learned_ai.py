"""
Learned battle policy (roadmap §7.5): a small linear scorer over features a legitimate player could know.

Only information visible in a real battle is used:
  * the move's own published data (power, type, accuracy, category, PP)
  * type matchups (public), and both sides' current HP (the health bars)
  * base stats from the Pokédex (public), not the hidden computed stats
  * our own PP and status
The opponent's moveset, hidden IVs/EVs and computed stats are never read. The features are computed from the
mover's point of view, so the same policy can play either side.

Scoring: for each usable move, score = weights · features(move); the highest score is played (ties: the first).
Training (tools/train_learned_ai.py) only ships weights that beat the rule-based AI on held-out matchups.

Nothing here is used in a live battle unless the caller sets BattleSystem.opponent_policy; by default it is None.
"""

import json
import math
import os
from typing import Dict, List, Optional

import rules
import species_data

FEATURES: List[str] = [
    "power",          # the move's power / 100 (0 for status moves)
    "effectiveness",  # type multiplier / 2 (1.0 = super effective)
    "stab",           # 1 when the move shares a type with its user
    "accuracy",       # accuracy / 100
    "is_status",      # 1 for status moves
    "pp_left",        # remaining PP / max PP
    "my_hp",          # the mover's HP fraction
    "their_hp",       # the target's HP fraction
    "damage_share",   # a proxy for how much of the target's health this hit removes
    "kill",           # damage_share relative to the target's remaining HP (capped at 1)
    "speed_edge",     # (mover base Speed - target base Speed) / 100, clipped to [-1, 1]
    "est_frac",       # estimated damage as a share of the target's max HP: our own (public) attack stat against
                      # an estimate of the target's defence from its Pokédex base stats and level
    "reply_frac",     # lookahead: what a typical hit from the target takes off us, as a share of our max HP
    "survives",       # lookahead: 1 when we are still standing after that reply
    "race",           # lookahead: who wins the exchange of hits, (turns they need - turns we need) / 3, clipped
    "bias",           # constant 1
]

DEFAULT_WEIGHTS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "learned_ai_weights.json")


def _base(c, key: str, default: float = 60.0) -> float:
    rec = species_data.get(getattr(c.real, "species_name", "") or "")
    try:
        return float(rec["base_stats"][key])
    except (TypeError, KeyError):
        return default


def _base_speed(c) -> float:
    return _base(c, "speed")


def _estimated_damage_share(bs, mover, target, move) -> float:
    """A player's estimate: the standard damage formula with our own real attack stat (visible on our summary)
    and the target's defence estimated from its base stats at its level (a Pokédex lookup, not a hidden stat)."""
    if not move.power or move.power <= 0:
        return 0.0
    physical = move.category != "special"
    attack = mover.stat("atk" if physical else "spa")
    base_def = _base(target, "defense" if physical else "sp_def", 60.0)
    defence_est = base_def * target.level / 50.0 + 5.0
    level = mover.level
    base = ((2 * level / 5.0 + 2) * move.power * attack / max(1.0, defence_est)) / 50.0 + 2.0
    stab = 1.5 if move.move_type in mover.types else 1.0
    eff = move.get_type_effectiveness(target.types)
    acc = (move.accuracy or 100) / 100.0
    return min(2.0, base * stab * eff * acc / max(1, target.max_hp))


REPLY_POWER = 80.0     # the target's moves are hidden, so assume one 80-power hit of each of its own types


def _reply_share(mover, target) -> float:
    """The target's likely reply, as a share of the mover's max HP. Uses only public information: the target's
    types, level and Pokédex base attack stats, and the mover's own (visible) defence and HP."""
    physical = _base(target, "attack", 60.0) >= _base(target, "sp_atk", 60.0)
    base_att = _base(target, "attack" if physical else "sp_atk", 60.0)
    attack = base_att * target.level / 50.0 + 5.0
    defence = max(1.0, mover.stat("def" if physical else "spd"))
    base = ((2 * target.level / 5.0 + 2) * REPLY_POWER * attack / defence) / 50.0 + 2.0
    best = 0.0
    for t in target.types:
        best = max(best, base * 1.5 * rules.type_multiplier(t, mover.types))
    return min(2.0, best / max(1, mover.max_hp))


def move_features(bs, mover, target, move) -> List[float]:
    """Features for one move, from `mover`'s point of view against `target` (both battle Combatants)."""
    power = (move.power or 0) / 100.0 if move.power and move.power > 0 else 0.0
    eff = move.get_type_effectiveness(target.types) / 2.0
    stab = 1.0 if move.move_type in mover.types else 0.0
    acc = (move.accuracy or 100) / 100.0
    is_status = 1.0 if (move.category == "status" or not move.power) else 0.0
    max_pp = max(1, getattr(move, "max_pp", 1) or 1)
    pp_left = min(1.0, bs.pp_left(mover, move) / max_pp)
    my_hp = mover.hp / max(1, mover.max_hp)
    their_hp = target.hp / max(1, target.max_hp)
    damage_share = min(1.5, power * eff * (1.0 + 0.5 * stab) * acc)
    kill = min(1.0, damage_share / max(their_hp, 0.05))
    speed_edge = max(-1.0, min(1.0, (_base_speed(mover) - _base_speed(target)) / 100.0))
    est = _estimated_damage_share(bs, mover, target, move)
    reply = _reply_share(mover, target)
    survives = 1.0 if my_hp > reply else 0.0
    turns_us = their_hp / max(est, 0.02)
    turns_them = my_hp / max(reply, 0.02)
    race = max(-1.0, min(1.0, (turns_them - turns_us) / 3.0))
    return [power, eff, stab, acc, is_status, pp_left, my_hp, their_hp, damage_share, kill, speed_edge, est,
            reply, survives, race, 1.0]


class LinearPolicy:
    def __init__(self, weights: Optional[List[float]] = None, meta: Optional[Dict] = None):
        self.weights = list(weights) if weights is not None else [0.0] * len(FEATURES)
        if len(self.weights) != len(FEATURES):
            raise ValueError(f"expected {len(FEATURES)} weights, got {len(self.weights)}")
        self.meta = dict(meta or {})

    def score(self, feats: List[float]) -> float:
        return sum(w * f for w, f in zip(self.weights, feats))

    def choose(self, bs, usable, mover, target):
        """The move this policy plays for `mover` against `target`. `usable` must be non-empty."""
        best, best_score = None, None
        for m in usable:
            s = self.score(move_features(bs, mover, target, m))
            if best_score is None or s > best_score:
                best, best_score = m, s
        return best

    def to_json(self) -> str:
        return json.dumps({"features": FEATURES, "weights": self.weights, "meta": self.meta}, indent=2)

    @classmethod
    def from_json(cls, text: str) -> "LinearPolicy":
        d = json.loads(text)
        if d.get("features") != FEATURES:
            raise ValueError("weights were trained with a different feature list; retrain")
        return cls(d["weights"], d.get("meta"))

    def save(self, path: str = DEFAULT_WEIGHTS_PATH) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())

    @classmethod
    def load(cls, path: str = DEFAULT_WEIGHTS_PATH) -> Optional["LinearPolicy"]:
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8") as f:
            return cls.from_json(f.read())


class MLPPolicy(LinearPolicy):
    """One hidden layer (tanh), same features and interface as LinearPolicy. Can express the conditional choices a
    linear scorer can't. Weights: W1 (H x F), b1 (H), w2 (H), b2 (1), flattened."""
    HIDDEN = 8

    @classmethod
    def size(cls) -> int:
        f = len(FEATURES)
        return cls.HIDDEN * f + cls.HIDDEN + cls.HIDDEN + 1

    def __init__(self, weights: Optional[List[float]] = None, meta: Optional[Dict] = None):
        if weights is None:
            weights = [0.0] * self.size()
        if len(weights) != self.size():
            raise ValueError(f"expected {self.size()} weights, got {len(weights)}")
        self.weights = list(weights)
        self.meta = dict(meta or {"architecture": "mlp"})

    def score(self, feats: List[float]) -> float:
        f, H = len(FEATURES), self.HIDDEN
        w = self.weights
        out = w[-1]
        for h in range(H):
            pre = w[H * f + h]
            base = h * f
            for i in range(f):
                pre += w[base + i] * feats[i]
            out += w[H * f + H + h] * math.tanh(pre)
        return out

    def to_json(self) -> str:
        return json.dumps({"architecture": "mlp", "features": FEATURES, "hidden": self.HIDDEN,
                           "weights": self.weights, "meta": self.meta}, indent=2)

    @classmethod
    def from_json(cls, text: str) -> "MLPPolicy":
        d = json.loads(text)
        if d.get("features") != FEATURES or d.get("hidden") != cls.HIDDEN:
            raise ValueError("weights were trained with a different architecture or feature list; retrain")
        return cls(d["weights"], d.get("meta"))


def load_policy(path: str = DEFAULT_WEIGHTS_PATH):
    """The shipped policy (linear or MLP, by the file's architecture), or None when nothing is shipped."""
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        text = f.read()
    return MLPPolicy.from_json(text) if '"architecture": "mlp"' in text else LinearPolicy.from_json(text)


def as_opponent_policy(policy: LinearPolicy):
    """A function the battle engine can call for the opponent's move (BattleSystem.opponent_policy)."""
    def choose(bs, usable):
        return policy.choose(bs, usable, mover=bs.o, target=bs.p)
    return choose


# ── switching (team battles) ──────────────────────────────────────────────────────────────────────────────

SWITCH_FEATURES: List[str] = [
    "hp",          # the candidate's HP fraction
    "threat",      # what a typical hit from the opponent takes off the candidate (it is taken for free on entry)
    "best_hit",    # the candidate's best estimated damage against the opponent, as a share of the opponent's max HP
    "race",        # who wins the exchange of hits if the candidate fights: (turns they need - turns we need) / 3
    "gain",        # candidate's best_hit minus the current Pokémon's best estimated damage (0 on a forced switch)
    "cur_threat",  # the same typical hit against the Pokémon on the field now (0 on a forced switch)
    "bias",        # constant 1
]


def _best_hit(bs, mover, target) -> float:
    best = 0.0
    for m in bs._moves_for(mover, mover.mon):
        best = max(best, _estimated_damage_share(bs, mover, target, m))
    return best


def switch_features(bs, cand, target, current=None) -> List[float]:
    """Features for sending `cand` (a Combatant of our own bench Pokémon) in against `target`, from public information."""
    hp = cand.hp / max(1, cand.max_hp)
    threat = _reply_share(cand, target)
    best = _best_hit(bs, cand, target)
    their_hp = target.hp / max(1, target.max_hp)
    race = max(-1.0, min(1.0, (hp / max(threat, 0.02) - their_hp / max(best, 0.02)) / 3.0))
    gain = cur_threat = 0.0
    if current is not None:
        gain = max(-1.0, min(1.0, best - _best_hit(bs, current, target)))
        cur_threat = _reply_share(current, target)
    return [hp, min(2.0, threat), min(2.0, best), race, gain, min(2.0, cur_threat), 1.0]


RESIDUAL_SCALE = 40.0   # the rule-based move score runs in tens; the learned correction is scaled to match


class TeamPolicy:
    """Picks a move or a switch. A move's score is the rule-based AI's score plus a learned correction (a
    LinearPolicy or MLPPolicy over the move features, times RESIDUAL_SCALE), so zero weights play exactly like the
    rule-based AI. The switch scorer is linear. A switch is chosen when its best score (times RESIDUAL_SCALE) beats
    the best move score. A forced switch (the Pokémon fainted) always picks the highest switch score."""

    def __init__(self, move_policy: LinearPolicy, switch_weights: Optional[List[float]] = None, meta: Optional[Dict] = None):
        self.move_policy = move_policy
        self.switch_weights = list(switch_weights) if switch_weights is not None else [0.0] * len(SWITCH_FEATURES)
        if len(self.switch_weights) != len(SWITCH_FEATURES):
            raise ValueError(f"expected {len(SWITCH_FEATURES)} switch weights, got {len(self.switch_weights)}")
        self.meta = dict(meta or {})

    @classmethod
    def from_theta(cls, theta: List[float], make=LinearPolicy, meta: Optional[Dict] = None) -> "TeamPolicy":
        n = len(theta) - len(SWITCH_FEATURES)
        return cls(make(theta[:n]), theta[n:], meta)

    def switch_score(self, feats: List[float]) -> float:
        return sum(w * f for w, f in zip(self.switch_weights, feats))

    def pick_switch(self, bs, bench, target, current=None):
        """The bench Pokémon to send in, with its score. `bench` is a non-empty list of PokemonInstances."""
        from battle_system import Combatant
        best, best_score = None, None
        for mon in bench:
            s = self.switch_score(switch_features(bs, Combatant(mon, mon.current_hp), target, current))
            if best_score is None or s > best_score:
                best, best_score = mon, s
        return best, best_score

    def move_score(self, bs, mover, target, move) -> float:
        import battle_ai
        return battle_ai._score(bs, mover, target, move) + RESIDUAL_SCALE * self.move_policy.score(move_features(bs, mover, target, move))

    def choose_action(self, bs, usable, mover, target, bench):
        """('move', Move) or ('switch', PokemonInstance)."""
        scored = [(self.move_score(bs, mover, target, m), m) for m in usable]      # each move scored once (the base score is noisy)
        best_score, move = max(scored, key=lambda x: x[0])
        if not bench:
            return "move", move
        mon, score = self.pick_switch(bs, bench, target, mover)
        return ("switch", mon) if RESIDUAL_SCALE * score > best_score else ("move", move)

    def pick_forced(self, bs, bench, target):
        return self.pick_switch(bs, bench, target, None)[0]

    def to_json(self) -> str:
        return json.dumps({"kind": "team", "features": FEATURES, "switch_features": SWITCH_FEATURES, "residual_scale": RESIDUAL_SCALE,
                           "move_policy": json.loads(self.move_policy.to_json()),
                           "switch_weights": self.switch_weights, "meta": self.meta}, indent=2)

    @classmethod
    def from_json(cls, text: str) -> "TeamPolicy":
        d = json.loads(text)
        if d.get("features") != FEATURES or d.get("switch_features") != SWITCH_FEATURES or d.get("residual_scale") != RESIDUAL_SCALE:
            raise ValueError("weights were trained with a different feature list; retrain")
        mp = d["move_policy"]
        move = MLPPolicy.from_json(json.dumps(mp)) if mp.get("architecture") == "mlp" else LinearPolicy.from_json(json.dumps(mp))
        return cls(move, d["switch_weights"], d.get("meta"))
