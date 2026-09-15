"""
⚡ POSHOW - FIXED BATTLE SYSTEM V2
Proper turn-based battle with move handling
"""

import random
import logging
from typing import Dict, List, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════════
# MOVE CLASS
# ════════════════════════════════════════════════════════════════

class Move:
    """Represents a single move"""
    
    def __init__(self, name: str, power: int = 40, accuracy: int = 100, 
                 move_type: str = "normal", category: str = "physical"):
        self.name = name
        self.power = power
        self.accuracy = accuracy
        self.move_type = move_type
        self.category = category
    
    def __repr__(self):
        return f"Move({self.name}, Power:{self.power}, Acc:{self.accuracy}%)"
    
    def will_hit(self) -> bool:
        """Check if move hits based on accuracy"""
        return random.random() * 100 <= self.accuracy
    
    def calculate_damage(self, attacker_stats: Dict, defender_stats: Dict, 
                        defender_types: List[str]) -> int:
        """
        Calculate damage with type effectiveness
        
        Using simplified Gen 5+ formula:
        Damage = ((2 * Level + 10) / 250 * Attack / Defense * Power + 2) * Modifiers
        """
        try:
            # Get stats safely with fallbacks
            level = attacker_stats.get('level', 5)
            attack = attacker_stats.get('attack', 10)
            defense = defender_stats.get('defense', 10)
            
            # Avoid division by zero
            if defense <= 0:
                defense = 1
            
            # Base damage formula
            base_damage = ((2 * level + 10) / 250 * (attack / defense) * self.power + 2)
            base_damage = max(1, int(base_damage))  # Minimum 1 damage
            
            # Critical hit (5% chance = 1.5x)
            crit_multiplier = 1.5 if random.random() < 0.05 else 1.0
            
            # Type effectiveness multiplier
            type_multiplier = self.get_type_effectiveness(defender_types)
            
            # Random variance (0.85 to 1.0)
            variance = random.uniform(0.85, 1.0)
            
            final_damage = int(base_damage * crit_multiplier * type_multiplier * variance)
            final_damage = max(1, final_damage)
            
            return final_damage
        
        except Exception as e:
            logger.error(f"Damage calculation error: {e}")
            return random.randint(1, 20)  # Fallback: 1-20 damage
    
    def get_type_effectiveness(self, defender_types: List[str]) -> float:
        """Get type effectiveness multiplier"""
        type_chart = {
            "fire": {"strong": ["grass", "ice", "bug", "steel"], "weak": ["water", "ground", "rock"]},
            "water": {"strong": ["fire", "ground", "rock"], "weak": ["grass", "electric"]},
            "grass": {"strong": ["water", "ground", "rock"], "weak": ["fire", "ice", "poison", "flying", "bug"]},
            "electric": {"strong": ["water", "flying"], "weak": ["ground"]},
            "psychic": {"strong": ["fighting", "poison"], "weak": ["bug", "ghost", "dark"]},
            "flying": {"strong": ["fighting", "bug", "grass"], "weak": ["electric", "ice", "rock"]},
            "ground": {"strong": ["fire", "electric", "poison", "rock", "steel"], "weak": ["water", "grass", "ice"]},
            "rock": {"strong": ["flying", "bug", "fire", "ice"], "weak": ["water", "grass", "fighting", "ground", "steel"]},
            "dark": {"strong": ["ghost", "psychic"], "weak": ["fighting", "bug", "fairy"]},
            "steel": {"strong": ["ice", "rock", "fairy"], "weak": ["fire", "water", "ground"]},
            "normal": {"strong": [], "weak": ["fighting"]},
            "fighting": {"strong": ["normal", "ice", "rock", "dark", "steel"], "weak": ["flying", "psychic", "fairy"]},
            "poison": {"strong": ["grass", "fairy"], "weak": ["ground", "psychic"]},
            "ghost": {"strong": ["ghost", "psychic"], "weak": ["ghost", "dark"]},
            "ice": {"strong": ["flying", "ground", "grass", "dragon"], "weak": ["fire", "fighting", "rock", "steel"]},
            "dragon": {"strong": ["dragon"], "weak": ["ice", "dragon", "fairy"]},
            "fairy": {"strong": ["fighting", "bug", "dark"], "weak": ["poison", "steel"]},
            "bug": {"strong": ["grass", "psychic", "dark"], "weak": ["fire", "flying", "rock"]},
        }
        
        move_type = self.move_type.lower()
        multiplier = 1.0
        
        if move_type in type_chart:
            chart = type_chart[move_type]
            
            for def_type in defender_types:
                def_type = def_type.lower()
                
                if def_type in chart["strong"]:
                    multiplier *= 2.0
                elif def_type in chart["weak"]:
                    multiplier *= 0.5
        
        return multiplier

# ════════════════════════════════════════════════════════════════
# BATTLE SYSTEM
# ════════════════════════════════════════════════════════════════

class BattleSystem:
    """Manages turn-based battles"""
    
    def __init__(self, player_pokemon, wild_pokemon):
        self.player_pokemon = player_pokemon
        self.wild_pokemon = wild_pokemon
        
        self.player_hp = player_pokemon.current_hp
        self.wild_hp = wild_pokemon.current_hp
        
        self.turn = 0
        self.is_finished = False
        self.winner = None
        self.battle_log = []
    
    def get_player_moves(self) -> List[Move]:
        """Get player's available moves"""
        try:
            # Get moves from Pokemon (safely)
            move_names = []
            
            if hasattr(self.player_pokemon, 'moves') and self.player_pokemon.moves:
                move_names = self.player_pokemon.moves[:4]
            else:
                move_names = ["tackle"]  # Fallback
            
            # Convert to Move objects
            moves = []
            for move_name in move_names:
                if isinstance(move_name, str):
                    # Get move data from moves_database if available
                    try:
                        from moves_database import get_move_data
                        move_data = get_move_data(move_name)
                        move = Move(
                            move_name,
                            power=move_data.get("power", 40),
                            accuracy=move_data.get("accuracy", 100),
                            move_type=move_data.get("type", "normal"),
                            category=move_data.get("category", "physical")
                        )
                    except:
                        # Fallback if moves_database not available
                        move = Move(move_name, power=40, accuracy=100)
                    
                    moves.append(move)
            
            return moves if moves else [Move("tackle")]
        
        except Exception as e:
            logger.error(f"Error getting player moves: {e}")
            return [Move("tackle")]  # Ultimate fallback
    
    def get_opponent_move(self) -> Move:
        """Get opponent's random move"""
        try:
            move_names = []
            
            if hasattr(self.wild_pokemon, 'moves') and self.wild_pokemon.moves:
                move_names = self.wild_pokemon.moves[:4]
            else:
                move_names = ["tackle"]
            
            chosen_move = random.choice(move_names) if move_names else "tackle"
            
            try:
                from moves_database import get_move_data
                move_data = get_move_data(chosen_move)
                move = Move(
                    chosen_move,
                    power=move_data.get("power", 40),
                    accuracy=move_data.get("accuracy", 100),
                    move_type=move_data.get("type", "normal"),
                    category=move_data.get("category", "physical")
                )
            except:
                move = Move(chosen_move, power=40, accuracy=100)
            
            return move
        
        except Exception as e:
            logger.error(f"Error getting opponent move: {e}")
            return Move("tackle")
    
    def execute_turn(self, player_move: Move, opponent_move: Move) -> Dict:
        """
        Execute one turn of battle
        
        Returns:
            {
                "log": ["message 1", "message 2"],
                "is_finished": bool,
                "winner": "player" or "opponent" or None
            }
        """
        self.turn += 1
        self.battle_log = []
        
        try:
            # Determine order by speed
            player_speed = getattr(self.player_pokemon, 'speed', 50)
            opponent_speed = getattr(self.wild_pokemon, 'speed', 50)
            
            if player_speed >= opponent_speed:
                # Player goes first
                self._execute_move(player_move, "player", self.wild_pokemon, self.wild_hp)
                if not self.is_finished:
                    self._execute_move(opponent_move, "opponent", self.player_pokemon, self.player_hp)
            else:
                # Opponent goes first
                self._execute_move(opponent_move, "opponent", self.player_pokemon, self.player_hp)
                if not self.is_finished:
                    self._execute_move(player_move, "player", self.wild_pokemon, self.wild_hp)
            
            self.battle_log.append(f"\nTurn {self.turn}")
            
            return {
                "log": self.battle_log,
                "is_finished": self.is_finished,
                "winner": self.winner
            }
        
        except Exception as e:
            logger.error(f"Turn execution error: {e}")
            return {
                "log": [f"⚠️ Battle error: {str(e)[:50]}"],
                "is_finished": True,
                "winner": None
            }
    
    def _execute_move(self, move: Move, attacker_type: str, defender_pokemon, defender_hp: int):
        """Execute a single move"""
        try:
            attacker_name = "You" if attacker_type == "player" else f"{self.wild_pokemon.species_name}"
            defender_name = "Wild" if attacker_type == "player" else "You"
            
            # Check if move hits
            if not move.will_hit():
                self.battle_log.append(f"❌ {attacker_name}'s {move.name} missed!")
                return
            
            # Get attacker stats
            if attacker_type == "player":
                attacker_stats = {
                    "level": getattr(self.player_pokemon, 'level', 5),
                    "attack": getattr(self.player_pokemon, 'attack', 10),
                }
            else:
                attacker_stats = {
                    "level": getattr(self.wild_pokemon, 'level', 5),
                    "attack": getattr(self.wild_pokemon, 'attack', 10),
                }
            
            # Get defender stats
            defender_stats = {
                "defense": getattr(defender_pokemon, 'defense', 10),
            }
            
            # Get defender types
            defender_types = getattr(defender_pokemon, 'types', ["normal"])
            if isinstance(defender_types, str):
                defender_types = [defender_types]
            
            # Calculate damage
            damage = move.calculate_damage(attacker_stats, defender_stats, defender_types)
            
            # Apply damage
            if attacker_type == "player":
                self.wild_hp -= damage
                self.wild_hp = max(0, self.wild_hp)
                hp_display = f"{max(0, self.wild_hp)}/{self.wild_pokemon.max_hp}"
            else:
                self.player_hp -= damage
                self.player_hp = max(0, self.player_hp)
                hp_display = f"{max(0, self.player_hp)}/{self.player_pokemon.max_hp}"
            
            # Type effectiveness message
            effectiveness = move.get_type_effectiveness(defender_types)
            if effectiveness > 1.0:
                effect_msg = " 💥 Super effective!"
            elif effectiveness < 1.0:
                effect_msg = " ❄️ Not very effective..."
            else:
                effect_msg = ""
            
            self.battle_log.append(f"⚔️ {attacker_name} used {move.name.upper()}!")
            self.battle_log.append(f"💥 {damage} damage to {defender_name}!{effect_msg}")
            self.battle_log.append(f"❤️ HP: {hp_display}")
            
            # Check if battle is finished
            if self.wild_hp <= 0:
                self.is_finished = True
                self.winner = "player"
                self.battle_log.append(f"✅ {self.wild_pokemon.species_name} fainted!")
            elif self.player_hp <= 0:
                self.is_finished = True
                self.winner = "opponent"
                self.battle_log.append(f"❌ Your Pokemon fainted!")
        
        except Exception as e:
            logger.error(f"Move execution error: {e}")
            self.battle_log.append(f"⚠️ Error executing move: {str(e)[:30]}")

# ════════════════════════════════════════════════════════════════
# TEST
# ════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Battle System Loaded ✅")

