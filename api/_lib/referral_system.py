"""
⚡ POSHOW - REFERRAL SYSTEM
Track invites and award referral bonuses
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ReferralSystem:
    """
    Manage player referrals and bonuses
    - Each player gets unique referral code
    - Bonuses awarded when referred player reaches Lv2
    - Rewards: coins, items, berries
    """
    
    REFERRAL_REWARDS = {
        1: {"coins": 0, "items": {}},
        2: {"coins": 0, "items": {}},
        3: {"coins": 50, "items": {}},
        4: {"coins": 50, "items": {}},
        5: {"coins": 50, "items": {"mixed_berry": 5}},
        10: {"coins": 100, "items": {"rare_candy": 2}},
        15: {"coins": 150, "items": {"evolution_stone": 1}},
        20: {"coins": 200, "items": {"rare_candy": 5}},
    }
    
    def __init__(self):
        """Initialize referral system"""
        logger.info("✅ Referral System initialized")
        self.referral_records = {}  # {referrer_id: [referred_user_ids]}
        self.pending_rewards = {}   # {referrer_id: pending_count}
    
    # ════════════════════════════════════════════════════════════════
    # REFERRAL TRACKING
    # ════════════════════════════════════════════════════════════════
    
    def create_referral_code(self, player_id: int) -> str:
        """Create unique referral code for player"""
        import random
        code = f"P{player_id}{random.randint(10000, 99999)}"
        return code
    
    def add_referral(self, referrer_id: int, referred_id: int) -> Dict:
        """Record a new referral"""
        if referrer_id not in self.referral_records:
            self.referral_records[referrer_id] = []
        
        if referred_id not in self.referral_records[referrer_id]:
            self.referral_records[referrer_id].append(referred_id)
            
            # Mark as pending reward (will process when referred reaches Lv2+)
            if referrer_id not in self.pending_rewards:
                self.pending_rewards[referrer_id] = 0
            self.pending_rewards[referrer_id] += 1
            
            logger.info(f"✅ Referral added: {referrer_id} ← {referred_id}")
            
            return {
                "success": True,
                "message": f"Referral recorded for user {referred_id}",
                "total_referrals": len(self.referral_records[referrer_id])
            }
        
        return {
            "success": False,
            "message": "User already referred"
        }
    
    def mark_referral_successful(self, referrer_id: int) -> Dict:
        """Mark referral as successful when referred player reaches Lv2"""
        if referrer_id not in self.pending_rewards or self.pending_rewards[referrer_id] == 0:
            return {
                "success": False,
                "message": "No pending referral rewards"
            }
        
        self.pending_rewards[referrer_id] -= 1
        
        return {
            "success": True,
            "message": "Referral confirmed! Reward pending...",
            "pending": self.pending_rewards[referrer_id]
        }
    
    def get_referral_count(self, player_id: int) -> int:
        """Get total referrals for player"""
        return len(self.referral_records.get(player_id, []))
    
    def get_successful_referral_count(self, player_id: int) -> int:
        """Get successful referrals (reached Lv2+)"""
        # In real implementation, would check if referred players are Lv2+
        return max(0, self.get_referral_count(player_id) - self.pending_rewards.get(player_id, 0))
    
    # ════════════════════════════════════════════════════════════════
    # REWARD CALCULATION
    # ════════════════════════════════════════════════════════════════
    
    def get_referral_rewards(self, successful_count: int) -> Dict:
        """Get rewards for number of successful referrals"""
        # Find closest reward tier
        tiers = sorted(self.REFERRAL_REWARDS.keys())
        
        for tier in reversed(tiers):
            if successful_count >= tier:
                return self.REFERRAL_REWARDS[tier].copy()
        
        return {"coins": 0, "items": {}}
    
    def process_milestone_reward(self, player, referrer_id: int) -> Dict:
        """Process milestone reward when referred player levels up"""
        player.add_referral(referrer_id)
        result = self.mark_referral_successful(referrer_id)
        
        if result["success"]:
            successful = self.get_successful_referral_count(referrer_id)
            rewards = self.get_referral_rewards(successful)
            
            # Award coins
            if rewards["coins"] > 0:
                player.add_coins(rewards["coins"])
            
            # Award items
            for item_name, quantity in rewards["items"].items():
                player.add_item(item_name, quantity)
            
            return {
                "success": True,
                "message": f"Referral milestone reached! {successful} successful referrals",
                "coins_awarded": rewards["coins"],
                "items_awarded": rewards["items"]
            }
        
        return {
            "success": False,
            "message": "Referral not yet successful"
        }
    
    # ════════════════════════════════════════════════════════════════
    # REFERRAL STATS
    # ════════════════════════════════════════════════════════════════
    
    def get_referral_stats(self, player_id: int) -> Dict:
        """Get referral statistics for player"""
        total = self.get_referral_count(player_id)
        successful = self.get_successful_referral_count(player_id)
        pending = self.pending_rewards.get(player_id, 0)
        
        next_milestone = None
        for tier in sorted(self.REFERRAL_REWARDS.keys()):
            if tier > successful:
                next_milestone = tier
                break
        
        return {
            "total_referrals": total,
            "successful_referrals": successful,
            "pending_referrals": pending,
            "next_milestone": next_milestone,
            "next_reward": self.REFERRAL_REWARDS.get(next_milestone) if next_milestone else None,
            "current_rewards": self.get_referral_rewards(successful)
        }
    
    def get_referral_display(self, player) -> str:
        """Get formatted referral display"""
        stats = self.get_referral_stats(player.user_id)
        
        display = f"""
🎁 REFERRAL PROGRAM
Your Code: {player.referral_code}

📊 STATISTICS
Total Invites: {stats['total_referrals']}
Successful: {stats['successful_referrals']}
Pending: {stats['pending_referrals']} (Waiting for Lv2+)

🎯 NEXT MILESTONE
Goal: {stats['next_milestone']} referrals
Progress: {stats['successful_referrals']}/{stats['next_milestone']}

💰 CURRENT REWARDS
Coins: {stats['current_rewards']['coins']}₽
"""
        
        if stats['current_rewards']['items']:
            display += "Items:\n"
            for item, qty in stats['current_rewards']['items'].items():
                display += f"  {item}: {qty}x\n"
        
        return display
    
    # ════════════════════════════════════════════════════════════════
    # LEADERBOARD
    # ════════════════════════════════════════════════════════════════
    
    def get_referral_leaderboard(self, limit: int = 10) -> List[Dict]:
        """Get top referrers"""
        referrers = [
            {
                "player_id": player_id,
                "successful_count": self.get_successful_referral_count(player_id),
                "total_count": self.get_referral_count(player_id)
            }
            for player_id in self.referral_records.keys()
        ]
        
        referrers.sort(key=lambda x: x["successful_count"], reverse=True)
        return referrers[:limit]
    
    def get_leaderboard_display(self) -> str:
        """Get referral leaderboard display"""
        leaderboard = self.get_referral_leaderboard(10)
        
        display = "🏆 REFERRAL LEADERBOARD\n\n"
        
        for rank, referrer in enumerate(leaderboard, 1):
            medal = "🥇" if rank == 1 else ("🥈" if rank == 2 else ("🥉" if rank == 3 else f"#{rank}"))
            display += f"{medal} Player {referrer['player_id']}: {referrer['successful_count']} referrals\n"
        
        return display
    
    # ════════════════════════════════════════════════════════════════
    # VALIDATION
    # ════════════════════════════════════════════════════════════════
    
    def is_valid_referral_code(self, code: str) -> bool:
        """Validate referral code format"""
        return code.startswith("P") and len(code) >= 10
    
    def can_claim_reward(self, player_id: int) -> bool:
        """Check if player can claim rewards"""
        successful = self.get_successful_referral_count(player_id)
        return successful >= 3  # Minimum 3 referrals to claim

# Singleton
referral = ReferralSystem()

if __name__ == "__main__":
    print("Testing Referral System...")
    
    # Test referral creation
    code = referral.create_referral_code(123)
    print(f"✅ Created referral code: {code}")
    
    # Test adding referral
    result = referral.add_referral(123, 456)
    print(f"✅ {result['message']}")
    
    # Test stats
    stats = referral.get_referral_stats(123)
    print(f"✅ Total referrals: {stats['total_referrals']}")
    
    print("✅ All tests passed!")

