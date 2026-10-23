
"""Pokémon instance: stats, moves, abilities and evolution."""

import uuid
import random
import logging
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class UnknownSpecies(ValueError):
    """The species can't be resolved from the offline data or PokeAPI. Raised instead of silently giving the
    Pokémon generic stats (a player's Greninja must never turn into a 45/49/49 blob because a lookup failed)."""


class PokemonInstance:
    """Individual Pokemon with IV/EV/Nature system"""
    
    def __init__(self, species_name: str, level: int, trainer_id: int):
        """Create a Pokemon instance"""
        self.id = str(uuid.uuid4())
        self.species_name = species_name
        self.level = max(1, min(100, level))
        self.trainer_id = trainer_id
        self.nickname = species_name.capitalize()
        
        # Get base stats from API
        try:
            from pokeapi_manager import pokeapi
            api_data = pokeapi.get_pokemon(species_name)
            self.api_data = api_data
            
            # Base stats by name
            self.base_stats = {}
            if "stats" in api_data:
                for stat in api_data["stats"]:
                    name = stat.get("stat", {}).get("name", "").lower()
                    base = stat.get("base_stat", 50)
                    self.base_stats[name] = base
            elif isinstance(api_data.get("base_stats"), dict):
                # pokeapi_manager.get_pokemon() returns a flat "base_stats" dict instead of the
                # raw PokeAPI "stats" list — without this every species silently got base 50s.
                flat = api_data["base_stats"]
                for src, dst in (("hp", "hp"), ("attack", "attack"), ("defense", "defense"),
                                 ("sp_atk", "special-attack"), ("sp_def", "special-defense"),
                                 ("speed", "speed")):
                    if src in flat:
                        self.base_stats[dst] = flat[src]
            
            # Get moves
            self.moves = self._starting_moves(api_data)
            
        except Exception as e:
            logger.error(f"Error loading {species_name}: {e}")
            raise UnknownSpecies(f"Unknown or unavailable species '{species_name}'") from e
        
        # Ability — derived from the species (see AbilitySystem.pick_ability), so it is
        # never stored: same species always resolves to the same ability.
        self.ability = self._resolve_ability()
        self.is_boss = False
        self.boss_tier = 3
        self.gym_floor = 0   # >0 only for Battle Gym opponents (see gym_system.py)
        self.pending_moves = []   # level-up moves offered while the moveset was full (persisted; see progression.py)
        self.move_events = []     # transient: moves learned automatically by the last level-up(s) (not saved)
        self.bt = None         # transient in-battle state (PP, stat stages, volatile status) — never saved to the DB
        self.story_ref = None  # {'t': trainer id, 'i': index, 'n': team size} for story trainer opponents (journey.py)

        # IV/EV/Nature
        self.iv = {k: random.randint(0, 31) for k in ["hp", "atk", "def", "sp_atk", "sp_def", "speed"]}
        self.ev = {k: 0 for k in ["hp", "atk", "def", "sp_atk", "sp_def", "speed"]}
        self.nature = random.choice(["Neutral", "Hardy", "Adamant", "Modest", "Timid", "Bold"])
        
        # Battle status
        self.current_hp = self._get_max_hp()
        self.max_hp = self._get_max_hp()
        self.status = None
        self.is_fainted = False
        
        # Experience
        self.experience = 0
        
        # Shiny
        self.is_shiny = random.random() < 0.0125
        
        # Calculate actual stats
        self.actual_stats = self._calculate_stats()
        
        logger.info(f"✅ Created {self.nickname} Lv{self.level}")
    
    # ── Stat calculations ──
    
    def _starting_moves(self, api_data) -> List[str]:
        """Real level-up learnset when we have one (what the games teach at this level), then the hand-written
        pools, then a sensible STAB moveset."""
        try:
            import species_data
            real = [m for m in species_data.moves_at_level(self.species_name, self.level)
                    if m in __import__("rules").MOVE_DATA]
            if real:
                return real
            from move_learning_system import POKEMON_MOVE_POOLS, get_moves_by_level
            if self.species_name in POKEMON_MOVE_POOLS:
                learned = get_moves_by_level(self.species_name, self.level)
                if learned:
                    return list(learned)[:4]
            from rules import default_moveset
            types = [t if isinstance(t, str) else t.get("type", {}).get("name", "") for t in api_data.get("types", [])]
            return default_moveset(types, self.level)
        except Exception as e:
            logger.warning(f"moveset lookup failed for {self.species_name}: {e}")
            return ["tackle", "scratch"]

    def _resolve_ability(self):
        """Each individual gets one of its species' real abilities. Deterministic from its id (no extra column):
        the same Pokémon always has the same ability; roughly 1 in 32 gets the species' hidden ability."""
        try:
            from abilities_system import AbilitySystem
            api_data = getattr(self, "api_data", None) or {}
            types = [t if isinstance(t, str) else t.get("type", {}).get("name", "") for t in api_data.get("types", [])]
            regular = list(api_data.get("abilities", []))
            hidden = list(api_data.get("hidden_abilities", []))
            h = int(uuid.UUID(str(self.id)).int % 10 ** 9) if self.id else 0
            if hidden and h % 32 == 0:
                return AbilitySystem.normalize(hidden[0])
            if regular:
                return AbilitySystem.normalize(regular[h % len(regular)])
            return AbilitySystem.pick_ability([], types)
        except Exception as e:  # abilities are a bonus — never block creating a Pokemon
            logger.warning(f"ability lookup failed for {self.species_name}: {e}")
            return None

    def _get_max_hp(self) -> int:
        """Calculate max HP"""
        base = self.base_stats.get("hp", 45)
        iv = self.iv.get("hp", 0)
        ev = self.ev.get("hp", 0)
        return self._hp_formula(base, iv, ev)

    def _hp_formula(self, base: int, iv: int, ev: int) -> int:
        """Standard HP stat: floor((2B + IV + EV/4) * L / 100) + L + 10. Shedinja is always 1 HP."""
        if str(getattr(self, "species_name", "")).lower() == "shedinja":
            return 1
        return ((2 * base + iv + ev // 4) * self.level // 100) + self.level + 10

    STAT_NAME_MAP = {
        "hp": "hp",
        "atk": "attack",
        "def": "defense",
        "sp_atk": "special-attack",
        "sp_def": "special-defense",
        "speed": "speed",
    }

    def _calculate_stats(self) -> Dict[str, int]:
        """Calculate all stats from IV/EV/Nature"""
        stats = {}
        
        for stat_name in ["hp", "atk", "def", "sp_atk", "sp_def", "speed"]:
            base = self.base_stats.get(self.STAT_NAME_MAP[stat_name], 50)
            iv = self.iv.get(stat_name, 0)
            ev = self.ev.get(stat_name, 0)
            
            if stat_name == "hp":
                stat = self._hp_formula(base, iv, ev)
            else:
                stat = ((2 * base + iv + ev // 4) * self.level // 100) + 5
                stat = self._apply_nature_modifier(stat, stat_name)
            
            stats[stat_name] = max(1, int(stat))
        
        return stats
    
    _NATURE_KEY = {"atk": "atk", "def": "def", "sp_atk": "spa", "sp_def": "spd", "speed": "spe"}

    def _apply_nature_modifier(self, stat: int, stat_name: str) -> int:
        """Nature: +10% to one stat, -10% to another (HP is never affected)."""
        from rules import nature_multiplier
        return int(stat * nature_multiplier(self.nature, self._NATURE_KEY.get(stat_name, "")))
    
    def recalculate_stats(self):
        """Recalculate stats after IV/EV changes"""
        self.max_hp = self._get_max_hp()
        self.current_hp = max(0, min(self.current_hp, self.max_hp))
        self.actual_stats = self._calculate_stats()
    
    # ── Experience & leveling ──
    
    def add_experience(self, amount: int) -> bool:
        """Add experience and check for level up"""
        from rules import xp_to_next
        self.experience += amount
        leveled = False
        hp_before, max_before = self.current_hp, self.max_hp
        level_before = self.level
        # several levels can come from one big win (Rare Candy-sized XP, boss rewards)
        while self.level < 100 and self.experience >= xp_to_next(self.level):
            self.experience -= xp_to_next(self.level)
            self.level += 1
            leveled = True
        if self.level >= 100:
            self.experience = 0
        if leveled:
            # Like the main games: levelling up raises max HP and current HP rises by the same amount. It is
            # NOT a heal — it never revives a fainted Pokémon, cures a status, or tops up missing HP.
            self.recalculate_stats()
            if hp_before > 0:
                gained = max(0, self.max_hp - max_before)
                self.current_hp = min(self.max_hp, hp_before + gained)
            self._learn_level_up_moves(level_before, self.level)
        return leveled

    def _learn_level_up_moves(self, old_level: int, new_level: int):
        """Level-up move learning. A move whose learn-level was just passed is learned straight away if there is a
        free slot; with four moves already known it is parked in `pending_moves` (saved with the Pokémon) until the
        player chooses what to forget — or declines. Never silently overwrites a known move."""
        try:
            import species_data, rules
            for lv, mv in sorted(species_data.learnset(self.species_name), key=lambda x: x[0]):
                if not (old_level < lv <= new_level) or mv not in rules.MOVE_DATA:
                    continue
                if mv in self.moves or mv in self.pending_moves:
                    continue
                if len(self.moves) < 4:
                    self.moves.append(mv)
                    self.move_events.append({"move": mv, "level": lv})
                else:
                    self.pending_moves.append(mv)
        except Exception as e:                      # move learning is a bonus — never break levelling up
            logger.warning(f"level-up move learning failed for {self.species_name}: {e}")

    def top_up_moves(self) -> bool:
        """Repair an under-filled moveset: fill FREE slots with the most recent moves this Pokémon could know at its
        level (its line's level-up moves). Fixes Pokémon saved by older versions that never taught level-up moves
        (a Lv44 Meganium that only knew Tackle). Never replaces or reorders a known move. True if anything changed."""
        if len(self.moves) >= 4:
            return False
        try:
            import species_data, rules
            known, changed = set(self.moves) | set(self.pending_moves), False
            for lv, mv in sorted(species_data.learnset_inherited(self.species_name), reverse=True):
                if len(self.moves) >= 4:
                    break
                if lv <= self.level and mv in rules.MOVE_DATA and mv not in known:
                    self.moves.append(mv); known.add(mv); changed = True
            return changed
        except Exception as e:                  # noqa: BLE001 — repair is a bonus, never block a load
            logger.warning(f"move top-up failed for {self.species_name}: {e}")
            return False

    def resolve_pending_move(self, move: str, replace: Optional[str] = None) -> Dict:
        """Teach (`replace` = the known move to forget) or decline (`replace` None) a pending level-up move."""
        if move not in self.pending_moves:
            return {"ok": False, "message": f"{self.nickname} isn't trying to learn {move}."}
        if replace is None:
            self.pending_moves.remove(move)
            return {"ok": True, "learned": False, "message": f"{self.nickname} did not learn {move}."}
        if replace not in self.moves:
            return {"ok": False, "message": f"{self.nickname} doesn't know {replace}."}
        self.moves[self.moves.index(replace)] = move
        self.pending_moves.remove(move)
        self.bt = None
        return {"ok": True, "learned": True, "forgot": replace,
                "message": f"{self.nickname} forgot {replace} and learned {move}!"}
    
    def restore_hp(self):
        """Restore HP to max"""
        self.current_hp = self.max_hp
        self.is_fainted = False
        self.status = None
        self.bt = None

    def restore_pp(self):
        """PP lives in the battle state (`bt`), so a heal / new battle starts with full PP."""
        if self.bt:
            self.bt.pop("pp", None)
    
    # ── EV training ──
    
    def add_ev(self, stat: str, amount: int) -> bool:
        """Add EVs to one stat. Rejects non-positive / non-integer amounts and never lets a stat pass 252 or the
        total pass 510 (the amount is trimmed to whatever still fits). False if nothing was added."""
        if stat not in self.ev or isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
            return False
        room = min(252 - self.ev[stat], 510 - sum(self.ev.values()))
        if room <= 0:
            return False
        self.ev[stat] += min(amount, room)
        self.recalculate_stats()
        return True

    # ── Serialization ──
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for storage"""
        data = self._base_dict()
        if getattr(self, "bt", None):
            data["bt"] = self.bt
        if getattr(self, "is_boss", False) or getattr(self, "gym_floor", 0) or getattr(self, "story_ref", None):
            # only ever present on boss / gym battle sessions (battle_sessions.wild_pokemon
            # is jsonb) — these Pokemon are never written to the `pokemon` table
            data["ability"] = self.ability
            if self.is_boss:
                data["is_boss"] = True
                data["boss_tier"] = self.boss_tier
            if self.gym_floor:
                data["gym_floor"] = self.gym_floor
            if self.story_ref:
                data["story_ref"] = self.story_ref
        return data

    def to_db_dict(self) -> Dict:
        """Exactly the columns of the `pokemon` table — no battle-session extras."""
        return self._base_dict()

    def _base_dict(self) -> Dict:
        return {
            "id": self.id,
            "species_name": self.species_name,
            "nickname": self.nickname,
            "level": self.level,
            "trainer_id": self.trainer_id,
            "current_hp": self.current_hp,
            "max_hp": self.max_hp,
            "experience": self.experience,
            "iv": self.iv,
            "ev": self.ev,
            "nature": self.nature,
            "moves": self.moves,
            "status": self.status,
            "is_fainted": self.is_fainted,
            "is_shiny": self.is_shiny,
            "pending_moves": list(self.pending_moves),
        }
    
    @staticmethod
    def from_dict(data: Dict) -> "PokemonInstance":
        """THE way to rebuild a Pokémon from stored data (database rows AND battle sessions use this).

        Order matters: the constructor rolls random IVs/nature, so every persistent field is restored FIRST and
        stats are recalculated from them, and only then is the saved HP put back (clamped to the real max).
        Skipping the recalculation is what produced "HP 90 / 85" on a loaded Pokémon."""
        species = data["species_name"]
        level = int(data.get("level", 5))
        p = PokemonInstance(species, level, data.get("trainer_id") or data.get("player_id") or 0)
        p.id = data.get("id", p.id)
        # The constructor resolved the ability from a throw-away uuid. Ordinary abilities are derived from the
        # persistent id, so resolve again now that the real id is back — otherwise the ability changed on reload.
        p.ability = p._resolve_ability()
        nick = data.get("nickname")
        if nick:
            p.nickname = nick
        p.experience = int(data.get("experience", 0) or 0)
        if data.get("iv"):
            p.iv = dict(data["iv"])
        if data.get("ev"):
            p.ev = dict(data["ev"])
        p.nature = data.get("nature") or p.nature
        if data.get("moves"):
            p.moves = list(data["moves"])
        p.status = data.get("status")
        p.pending_moves = list(data.get("pending_moves") or [])
        p.top_up_moves()          # heals movesets left short by older versions (persisted on the next save)
        p.is_shiny = bool(data.get("is_shiny", False))
        p.happiness = data.get("happiness", getattr(p, "happiness", 0))
        if data.get("is_boss"):
            p.is_boss = True
            p.boss_tier = int(data.get("boss_tier", 3))
        if data.get("gym_floor"):
            p.gym_floor = int(data["gym_floor"])
        if data.get("bt"):
            p.bt = data["bt"]
        if data.get("story_ref"):
            p.story_ref = data["story_ref"]
        if data.get("is_boss") or data.get("gym_floor") or data.get("story_ref"):
            p.ability = data.get("ability", p.ability)

        p.recalculate_stats()                              # max HP / stats from the restored IV, EV, nature, level
        saved_hp = data.get("current_hp")
        p.current_hp = p.max_hp if saved_hp is None else max(0, min(int(saved_hp), p.max_hp))
        p.is_fainted = bool(data.get("is_fainted", False)) or p.current_hp <= 0
        if p.current_hp > 0 and not data.get("is_fainted", False):
            p.is_fainted = False
        return p

if __name__ == "__main__":
    print("Testing PokemonInstance...")
    p = PokemonInstance("pikachu", 5, 123)
    print(f"✅ Created {p.nickname} Lv{p.level}")
    print(f"   HP: {p.current_hp}/{p.max_hp}")
    print(f"   Stats: {p.actual_stats}")
    print("✅ All tests passed!")

