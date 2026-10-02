"""
⚡ POSHOW - POKEMON TRADING SYSTEM
Player-to-player trades with balance constraints
"""

import logging
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════════
# TRADE CONSTANTS
# ════════════════════════════════════════════════════════════════

MAX_LEVEL_DIFFERENCE = 20  # Can't trade 30 for 51+ level Pokemon
TRADE_COOLDOWN_HOURS = 1  # Wait 1 hour between trades with same player
MAX_DAILY_TRADES = 10  # Max 10 trades per day per player

# ════════════════════════════════════════════════════════════════
# TRADE CLASS
# ════════════════════════════════════════════════════════════════

class PokemonTrade:
    """Represents a single trade"""
    
    def __init__(self, trader1_id: int, pokemon1_id: str, 
                 trader2_id: int, pokemon2_id: str):
        self.trader1_id = trader1_id
        self.pokemon1_id = pokemon1_id
        self.pokemon1_name = None
        self.pokemon1_level = None
        
        self.trader2_id = trader2_id
        self.pokemon2_id = pokemon2_id
        self.pokemon2_name = None
        self.pokemon2_level = None
        
        self.status = "pending"  # pending, accepted, rejected, completed
        self.created_at = datetime.now()
        self.completed_at = None
    
    def __repr__(self):
        return f"Trade({self.trader1_id} ↔ {self.trader2_id})"

# ════════════════════════════════════════════════════════════════
# TRADING SYSTEM
# ════════════════════════════════════════════════════════════════

class TradingSystem:
    """Manage Pokemon trades between players"""
    
    def __init__(self):
        """Initialize trading system"""
        logger.info("✅ Trading System initialized")
        self.active_trades = {}  # {trade_id: PokemonTrade}
        self.trade_history = {}  # {player_id: [trades]}
        self.last_trade_time = {}  # {(player1, player2): datetime}
        self.daily_trade_count = {}  # {player_id: count}
    
    # ════════════════════════════════════════════════════════════════
    # VALIDATION
    # ════════════════════════════════════════════════════════════════
    
    def can_trade(self, player1, pokemon1, player2, pokemon2) -> Tuple[bool, str]:
        """
        Check if trade is valid
        
        Returns:
            (is_valid, error_message)
        """
        # Check level difference
        level_diff = abs(pokemon1.level - pokemon2.level)
        if level_diff > MAX_LEVEL_DIFFERENCE:
            return (False, f"❌ Level difference too high! Max {MAX_LEVEL_DIFFERENCE} levels apart")
        
        # Check if players are different
        if player1.user_id == player2.user_id:
            return (False, "❌ Can't trade with yourself!")
        
        # Check cooldown
        if not self.can_trade_with_player(player1.user_id, player2.user_id):
            return (False, "❌ Wait 1 hour before trading with this player again")
        
        # Check daily limit
        if self.get_daily_trade_count(player1.user_id) >= MAX_DAILY_TRADES:
            return (False, f"❌ Daily trade limit reached! Max {MAX_DAILY_TRADES} per day")
        
        # Check if Pokemon is in team (can't trade active Pokemon)
        if pokemon1.id in player1.active_team:
            return (False, "❌ Can't trade Pokemon in your active team!")
        
        if pokemon2.id in player2.active_team:
            return (False, "❌ Target's Pokemon is in their active team!")
        
        return (True, "✅ Trade is valid")
    
    def can_trade_with_player(self, player1_id: int, player2_id: int) -> bool:
        """Check if cooldown has passed"""
        key = tuple(sorted([player1_id, player2_id]))
        
        if key not in self.last_trade_time:
            return True
        
        last_time = self.last_trade_time[key]
        cooldown = timedelta(hours=TRADE_COOLDOWN_HOURS)
        
        return datetime.now() >= last_time + cooldown
    
    def get_daily_trade_count(self, player_id: int) -> int:
        """Get trades made today"""
        today = datetime.now().date()
        
        if player_id not in self.trade_history:
            return 0
        
        count = 0
        for trade in self.trade_history[player_id]:
            if trade.completed_at and trade.completed_at.date() == today:
                count += 1
        
        return count
    
    # ════════════════════════════════════════════════════════════════
    # TRADE INITIATION
    # ════════════════════════════════════════════════════════════════
    
    def create_trade_offer(self, player1, pokemon1, player2, pokemon2) -> Dict:
        """
        Create a trade offer
        
        Returns:
            {
                "success": bool,
                "message": str,
                "trade_id": str or None,
                "level_diff": int
            }
        """
        # Validate trade
        is_valid, error_msg = self.can_trade(player1, pokemon1, player2, pokemon2)
        
        if not is_valid:
            return {
                "success": False,
                "message": error_msg,
                "trade_id": None
            }
        
        # Create trade
        trade_id = f"TRADE_{player1.user_id}_{pokemon1.id}_{player2.user_id}_{pokemon2.id}"
        trade = PokemonTrade(player1.user_id, pokemon1.id, player2.user_id, pokemon2.id)
        
        trade.pokemon1_name = pokemon1.species_name
        trade.pokemon1_level = pokemon1.level
        trade.pokemon2_name = pokemon2.species_name
        trade.pokemon2_level = pokemon2.level
        
        self.active_trades[trade_id] = trade
        
        level_diff = abs(pokemon1.level - pokemon2.level)
        
        return {
            "success": True,
            "message": f"🤝 Trade offer created!\n{pokemon1.nickname} Lv{pokemon1.level} ↔ {pokemon2.nickname} Lv{pokemon2.level}",
            "trade_id": trade_id,
            "level_diff": level_diff
        }
    
    # ════════════════════════════════════════════════════════════════
    # TRADE COMPLETION
    # ════════════════════════════════════════════════════════════════
    
    def accept_trade(self, trade_id: str, player1, player2, 
                    pokemon1, pokemon2) -> Dict:
        """
        Accept and complete a trade
        
        Args:
            trade_id: Trade identifier
            player1: First player (offering pokemon1)
            player2: Second player (offering pokemon2)
            pokemon1: Pokemon being given by player1
            pokemon2: Pokemon being given by player2
        """
        if trade_id not in self.active_trades:
            return {
                "success": False,
                "message": "❌ Trade not found!"
            }
        
        trade = self.active_trades[trade_id]
        
        try:
            # Swap Pokemon between collections
            # Remove from current owners
            player1.pokemon_collection = [p for p in player1.pokemon_collection if p.id != pokemon1.id]
            player2.pokemon_collection = [p for p in player2.pokemon_collection if p.id != pokemon2.id]
            
            # Add to new owners
            player1.pokemon_collection.append(pokemon2)
            player2.pokemon_collection.append(pokemon1)
            
            # Update trade status
            trade.status = "completed"
            trade.completed_at = datetime.now()
            
            # Record cooldown
            key = tuple(sorted([player1.user_id, player2.user_id]))
            self.last_trade_time[key] = datetime.now()
            
            # Record in history
            if player1.user_id not in self.trade_history:
                self.trade_history[player1.user_id] = []
            if player2.user_id not in self.trade_history:
                self.trade_history[player2.user_id] = []
            
            self.trade_history[player1.user_id].append(trade)
            self.trade_history[player2.user_id].append(trade)
            
            # Award points/badges (optional)
            player1.coins += 10  # Small bonus
            player2.coins += 10
            
            message = f"""✅ TRADE COMPLETED!

{player1.username}: Gave {pokemon1.nickname} Lv{pokemon1.level}
{player2.username}: Gave {pokemon2.nickname} Lv{pokemon2.level}

+10₽ for both players!"""
            
            return {
                "success": True,
                "message": message,
                "player1_new_pokemon": pokemon2,
                "player2_new_pokemon": pokemon1
            }
        
        except Exception as e:
            logger.error(f"Trade completion error: {e}")
            return {
                "success": False,
                "message": f"❌ Trade failed: {str(e)[:50]}"
            }
    
    def reject_trade(self, trade_id: str) -> Dict:
        """Reject a trade offer"""
        if trade_id not in self.active_trades:
            return {
                "success": False,
                "message": "❌ Trade not found!"
            }
        
        trade = self.active_trades[trade_id]
        trade.status = "rejected"
        
        return {
            "success": True,
            "message": "❌ Trade rejected"
        }
    
    # ════════════════════════════════════════════════════════════════
    # TRADE INFO
    # ════════════════════════════════════════════════════════════════
    
    def get_trade_info(self, trade_id: str) -> Dict:
        """Get trade details"""
        if trade_id not in self.active_trades:
            return None
        
        trade = self.active_trades[trade_id]
        
        return {
            "trader1_id": trade.trader1_id,
            "pokemon1_name": trade.pokemon1_name,
            "pokemon1_level": trade.pokemon1_level,
            "trader2_id": trade.trader2_id,
            "pokemon2_name": trade.pokemon2_name,
            "pokemon2_level": trade.pokemon2_level,
            "status": trade.status,
            "created_at": trade.created_at
        }
    
    def format_trade_offer(self, trade_id: str) -> str:
        """Format trade for display"""
        info = self.get_trade_info(trade_id)
        
        if not info:
            return "❌ Trade not found"
        
        return f"""🤝 TRADE OFFER

Player 1 offers:
{info['pokemon1_name']} Lv{info['pokemon1_level']}

Player 2 offers:
{info['pokemon2_name']} Lv{info['pokemon2_level']}

Level difference: {abs(info['pokemon1_level'] - info['pokemon2_level'])} levels
Status: {info['status'].upper()}"""
    
    # ════════════════════════════════════════════════════════════════
    # TRADING STATS
    # ════════════════════════════════════════════════════════════════
    
    def get_player_trade_stats(self, player_id: int) -> Dict:
        """Get trade statistics for player"""
        if player_id not in self.trade_history:
            return {
                "total_trades": 0,
                "completed_trades": 0,
                "total_pokemon_obtained": 0
            }
        
        trades = self.trade_history[player_id]
        completed = [t for t in trades if t.status == "completed"]
        
        return {
            "total_trades": len(trades),
            "completed_trades": len(completed),
            "total_pokemon_obtained": len(completed)
        }
    
    def get_trade_display(self, player_id: int) -> str:
        """Get formatted trade stats for player"""
        stats = self.get_player_trade_stats(player_id)
        
        return f"""🤝 TRADING STATS

Total Trades: {stats['total_trades']}
Completed: {stats['completed_trades']}
Pokemon Obtained: {stats['total_pokemon_obtained']}

Max Level Difference: {MAX_LEVEL_DIFFERENCE} levels
Daily Limit: {MAX_DAILY_TRADES} trades
Cooldown: {TRADE_COOLDOWN_HOURS} hour(s)"""

# Singleton
trading = TradingSystem()

# ════════════════════════════════════════════════════════════════
# TEST
# ════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("✅ Trading System loaded")

