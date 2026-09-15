"""
⚡ POSHOW - IMAGE GENERATOR
Generate stat cards and player profile images like HeXaBot
"""

from PIL import Image, ImageDraw, ImageFont
import os
from typing import Dict, Optional
from pokemon_model import PokemonInstance

class ImageGenerator:
    """Generate stat card images"""
    
    # Colors
    COLOR_BG = "#1a1a1a"
    COLOR_BORDER = "#ff6b6b"
    COLOR_TEXT = "#ffffff"
    COLOR_STAT_HP = "#4ecca3"
    COLOR_STAT_ATK = "#f77f7f"
    COLOR_STAT_DEF = "#f5d547"
    COLOR_STAT_SPATK = "#5dade2"
    COLOR_STAT_SPDEF = "#a569bd"
    COLOR_STAT_SPEED = "#f8b739"
    
    # Fonts (use defaults if not available)
    FONT_SIZE_TITLE = 36
    FONT_SIZE_STAT = 16
    FONT_SIZE_SMALL = 12
    
    def __init__(self):
        """Initialize image generator"""
        os.makedirs("images", exist_ok=True)
        self.output_dir = "images"
    
    def generate_pokemon_card(self, pokemon: PokemonInstance) -> str:
        """
        Generate Pokemon stat card image
        Returns: filepath to saved image
        """
        # Create image (like HeXaBot trainer card)
        width, height = 400, 600
        img = Image.new('RGB', (width, height), color=self.COLOR_BG)
        draw = ImageDraw.Draw(img)
        
        # Border
        border_color = self.COLOR_BORDER
        draw.rectangle([0, 0, width-1, height-1], outline=border_color, width=3)
        
        # Header
        y = 20
        self._draw_text(draw, pokemon.nickname.upper(), 20, y, 24, self.COLOR_BORDER)
        y += 40
        
        # Pokemon image placeholder (text version)
        self._draw_text(draw, f"#{pokemon.api_data['id']}", 20, y, 16, self.COLOR_TEXT)
        self._draw_text(draw, f"Level {pokemon.level}", 300, y, 16, self.COLOR_TEXT)
        y += 30
        
        # Types
        types_str = " / ".join([t.capitalize() for t in pokemon.api_data['types']])
        self._draw_text(draw, f"Type: {types_str}", 20, y, 14, self.COLOR_TEXT)
        y += 25
        
        # Nature
        self._draw_text(draw, f"Nature: {pokemon.nature}", 20, y, 14, self.COLOR_TEXT)
        y += 30
        
        # HP Bar
        self._draw_hp_bar(draw, 20, y, pokemon.current_hp, pokemon.max_hp)
        y += 35
        
        # Stats Table
        self._draw_stats_table(draw, 20, y, pokemon)
        y += 180
        
        # IV/EV Summary
        iv_total = sum(pokemon.iv.values())
        ev_total = sum(pokemon.ev.values())
        self._draw_text(draw, f"IV Total: {iv_total}/186", 20, y, 12, self.COLOR_TEXT)
        y += 20
        self._draw_text(draw, f"EV Total: {ev_total}/510", 20, y, 12, self.COLOR_TEXT)
        y += 20
        
        # Shiny indicator
        if pokemon.is_shiny:
            self._draw_text(draw, "✨ SHINY ✨", 20, y, 16, "#ffff00")
        
        # Save
        filename = f"{pokemon.id}_card.png"
        filepath = os.path.join(self.output_dir, filename)
        img.save(filepath)
        
        return filepath
    
    def _draw_hp_bar(self, draw: ImageDraw.ImageDraw, x: int, y: int, current_hp: int, max_hp: int):
        """Draw HP bar"""
        bar_width = 350
        bar_height = 20
        
        # Background
        draw.rectangle([x, y, x + bar_width, y + bar_height], fill="#333333", outline=self.COLOR_TEXT)
        
        # HP fill
        percent = current_hp / max_hp if max_hp > 0 else 0
        fill_width = int(bar_width * percent)
        
        # Color based on HP
        if percent > 0.5:
            color = self.COLOR_STAT_HP
        elif percent > 0.25:
            color = "#f5d547"
        else:
            color = "#f77f7f"
        
        draw.rectangle([x, y, x + fill_width, y + bar_height], fill=color)
        
        # Text
        hp_text = f"{current_hp}/{max_hp}"
        self._draw_text(draw, hp_text, x + bar_width // 2 - 20, y + 3, 12, self.COLOR_TEXT)
    
    def _draw_stats_table(self, draw: ImageDraw.ImageDraw, x: int, y: int, pokemon: PokemonInstance):
        """Draw stats table"""
        stats_data = [
            ("HP", "hp", self.COLOR_STAT_HP),
            ("ATK", "atk", self.COLOR_STAT_ATK),
            ("DEF", "def", self.COLOR_STAT_DEF),
            ("SP.ATK", "sp_atk", self.COLOR_STAT_SPATK),
            ("SP.DEF", "sp_def", self.COLOR_STAT_SPDEF),
            ("SPEED", "speed", self.COLOR_STAT_SPEED),
        ]
        
        col1_x, col2_x = x, x + 200
        
        for i, (name, key, color) in enumerate(stats_data):
            row_y = y + (i % 3) * 25
            col_x = col1_x if i < 3 else col2_x
            
            stat_val = pokemon.actual_stats[key]
            iv_val = pokemon.iv[key]
            ev_val = pokemon.ev[key]
            
            # Name
            self._draw_text(draw, f"{name}:", col_x, row_y, 12, color)
            
            # Value (IV | EV)
            stat_text = f"{stat_val} ({iv_val}|{ev_val})"
            self._draw_text(draw, stat_text, col_x + 80, row_y, 11, self.COLOR_TEXT)
    
    def _draw_text(self, draw: ImageDraw.ImageDraw, text: str, x: int, y: int, 
                   size: int = 16, fill: str = "#ffffff"):
        """Draw text with fallback"""
        try:
            font = ImageFont.truetype("/system/fonts/DroidSans.ttf", size)
        except:
            font = ImageFont.load_default()
        
        draw.text((x, y), text, fill=fill, font=font)
    
    def generate_trainer_card(self, trainer_data: Dict, pokemon_list: list) -> str:
        """
        Generate trainer profile card
        Shows: Name, Level, Rank, Pokemon count, Wins/Losses
        """
        width, height = 400, 500
        img = Image.new('RGB', (width, height), color=self.COLOR_BG)
        draw = ImageDraw.Draw(img)
        
        # Border
        draw.rectangle([0, 0, width-1, height-1], outline=self.COLOR_BORDER, width=3)
        
        y = 20
        
        # Trainer Name
        name = trainer_data.get("username", "Trainer")
        self._draw_text(draw, name.upper(), 20, y, 28, self.COLOR_BORDER)
        y += 40
        
        # ID
        trainer_id = trainer_data.get("id", "??")
        self._draw_text(draw, f"Trainer ID: {trainer_id}", 20, y, 14, self.COLOR_TEXT)
        y += 25
        
        # Level & Stats
        level = trainer_data.get("level", 1)
        exp = trainer_data.get("exp", 0)
        elo = trainer_data.get("elo", 1000)
        coins = trainer_data.get("coins", 0)
        
        self._draw_text(draw, f"Level: {level}", 20, y, 14, self.COLOR_STAT_HP)
        self._draw_text(draw, f"ELO: {elo}", 200, y, 14, self.COLOR_STAT_SPEED)
        y += 25
        
        self._draw_text(draw, f"Coins: {coins} Pₖ", 20, y, 14, self.COLOR_TEXT)
        y += 30
        
        # Stats
        wins = trainer_data.get("wins", 0)
        losses = trainer_data.get("losses", 0)
        pokemon_caught = trainer_data.get("pokemon_caught", 0)
        
        self._draw_text(draw, "STATISTICS", 20, y, 16, self.COLOR_BORDER)
        y += 25
        
        self._draw_text(draw, f"Pokemon Caught: {pokemon_caught}", 20, y, 12, self.COLOR_TEXT)
        y += 20
        self._draw_text(draw, f"Wins: {wins} | Losses: {losses}", 20, y, 12, self.COLOR_TEXT)
        y += 20
        
        win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
        self._draw_text(draw, f"Win Rate: {win_rate:.1f}%", 20, y, 12, self.COLOR_TEXT)
        y += 30
        
        # Top Pokemon
        if pokemon_list:
            self._draw_text(draw, "TEAM", 20, y, 16, self.COLOR_BORDER)
            y += 25
            
            for i, poke in enumerate(pokemon_list[:3]):
                poke_name = poke.get("nickname", poke.get("species_name", "?"))
                poke_level = poke.get("level", 1)
                self._draw_text(draw, f"{i+1}. {poke_name} Lv{poke_level}", 20, y, 11, self.COLOR_TEXT)
                y += 18
        
        # Save
        filename = f"trainer_{trainer_data.get('id', 'unknown')}.png"
        filepath = os.path.join(self.output_dir, filename)
        img.save(filepath)
        
        return filepath
    
    def generate_battle_scene(self, player_pokemon: Dict, opponent_pokemon: Dict, 
                             turn: int = 1) -> str:
        """
        Generate battle scene image
        Shows: Both Pokemon, HP bars, current turn
        """
        width, height = 500, 400
        img = Image.new('RGB', (width, height), color=self.COLOR_BG)
        draw = ImageDraw.Draw(img)
        
        # Title
        self._draw_text(draw, f"TURN {turn}", 20, 20, 20, self.COLOR_BORDER)
        
        # Opponent Pokemon (top)
        y = 50
        opp_name = opponent_pokemon.get("nickname", "Enemy")
        opp_level = opponent_pokemon.get("level", 1)
        opp_hp = opponent_pokemon.get("current_hp", 100)
        opp_max_hp = opponent_pokemon.get("max_hp", 100)
        
        self._draw_text(draw, f"{opp_name} Lv{opp_level}", 20, y, 16, self.COLOR_TEXT)
        y += 25
        self._draw_hp_bar(draw, 20, y, opp_hp, opp_max_hp)
        y += 50
        
        # Middle space (action log would go here)
        y += 50
        
        # Player Pokemon (bottom)
        player_name = player_pokemon.get("nickname", "Your Pokemon")
        player_level = player_pokemon.get("level", 1)
        player_hp = player_pokemon.get("current_hp", 100)
        player_max_hp = player_pokemon.get("max_hp", 100)
        
        self._draw_text(draw, f"{player_name} Lv{player_level}", 20, y, 16, self.COLOR_TEXT)
        y += 25
        self._draw_hp_bar(draw, 20, y, player_hp, player_max_hp)
        
        # Save
        filename = f"battle_scene_{turn}.png"
        filepath = os.path.join(self.output_dir, filename)
        img.save(filepath)
        
        return filepath
    
    def generate_leaderboard_image(self, leaderboard_data: list) -> str:
        """
        Generate leaderboard image
        Shows: Top 10 trainers with ranks and ELO
        """
        width, height = 500, 600
        img = Image.new('RGB', (width, height), color=self.COLOR_BG)
        draw = ImageDraw.Draw(img)
        
        # Title
        self._draw_text(draw, "🏅 LEADERBOARD 🏅", 20, 20, 24, self.COLOR_BORDER)
        
        y = 60
        
        for rank, trainer in enumerate(leaderboard_data[:10], 1):
            name = trainer.get("username", "?")
            elo = trainer.get("elo", 0)
            
            # Rank indicator
            if rank == 1:
                medal = "🥇"
            elif rank == 2:
                medal = "🥈"
            elif rank == 3:
                medal = "🥉"
            else:
                medal = f"#{rank}"
            
            # Trainer info
            text = f"{medal} {name} - {elo} ELO"
            self._draw_text(draw, text, 20, y, 14, self.COLOR_TEXT)
            y += 30
        
        # Save
        filename = "leaderboard.png"
        filepath = os.path.join(self.output_dir, filename)
        img.save(filepath)
        
        return filepath

# Singleton
image_gen = ImageGenerator()

# Test
if __name__ == "__main__":
    print("Testing Image Generator...")
    from pokemon_model import PokemonInstance
    
    poke = PokemonInstance("pikachu", 25, trainer_id=123)
    card_path = image_gen.generate_pokemon_card(poke)
    print(f"✅ Generated Pokemon card: {card_path}")
    
    trainer_data = {
        "username": "Master",
        "id": 123,
        "level": 5,
        "elo": 1500,
        "coins": 5000,
        "wins": 25,
        "losses": 10,
        "pokemon_caught": 42
    }
    trainer_path = image_gen.generate_trainer_card(trainer_data, [])
    print(f"✅ Generated trainer card: {trainer_path}")
    
    print("✅ All tests passed!")

