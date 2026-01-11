"""
Reputation & Vouch Bot - Part 1: Core Setup
Professional Reputation System with Leaderboard
"""

import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Button, View
import asyncio
from datetime import datetime, timedelta
from collections import defaultdict
import json
import os
from typing import Optional, Dict, List
from dotenv import load_dotenv
import logging

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

class Config:
    """Bot Configuration"""
    OWNER_ID = 1439497398190866495
    TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    PREFIX = '!'
    PORT = int(os.getenv('PORT', 8080))
    
    # Reputation Settings
    VOUCH_REP_AMOUNT = 3
    VOUCH_COOLDOWN = 600  # 10 minutes in seconds
    LEADERBOARD_PER_PAGE = 10

class DataManager:
    """Handle all data persistence"""
    
    def __init__(self):
        self.data_file = 'reputation_data.json'
        self.reputation: Dict[int, int] = {}
        self.vouch_history: Dict[int, List[Dict]] = defaultdict(list)
        self.last_vouch: Dict[int, float] = {}
        
        self.load_data()
    
    def load_data(self):
        """Load data from JSON file"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    self.reputation = {int(k): v for k, v in data.get('reputation', {}).items()}
                    self.vouch_history = defaultdict(list, {
                        int(k): v for k, v in data.get('vouch_history', {}).items()
                    })
                    self.last_vouch = {int(k): v for k, v in data.get('last_vouch', {}).items()}
                    logging.info("Data loaded successfully")
            else:
                logging.info("No existing data file, starting fresh")
        except Exception as e:
            logging.error(f"Error loading data: {e}")
    
    def save_data(self):
        """Save data to JSON file"""
        try:
            data = {
                'reputation': {str(k): v for k, v in self.reputation.items()},
                'vouch_history': {str(k): v for k, v in self.vouch_history.items()},
                'last_vouch': {str(k): v for k, v in self.last_vouch.items()}
            }
            with open(self.data_file, 'w') as f:
                json.dump(data, f, indent=4)
            logging.info("Data saved successfully")
        except Exception as e:
            logging.error(f"Error saving data: {e}")
    
    def add_reputation(self, user_id: int, amount: int):
        """Add reputation to a user"""
        if user_id not in self.reputation:
            self.reputation[user_id] = 0
        self.reputation[user_id] += amount
        self.save_data()
    
    def remove_reputation(self, user_id: int, amount: int):
        """Remove reputation from a user"""
        if user_id not in self.reputation:
            self.reputation[user_id] = 0
        self.reputation[user_id] = max(0, self.reputation[user_id] - amount)
        self.save_data()
    
    def set_reputation(self, user_id: int, amount: int):
        """Set user reputation to specific amount"""
        self.reputation[user_id] = max(0, amount)
        self.save_data()
    
    def get_reputation(self, user_id: int) -> int:
        """Get user reputation"""
        return self.reputation.get(user_id, 0)
    
    def clear_reputation(self, user_id: int):
        """Clear user reputation"""
        if user_id in self.reputation:
            del self.reputation[user_id]
        if user_id in self.vouch_history:
            del self.vouch_history[user_id]
        self.save_data()
    
    def add_vouch(self, target_id: int, voucher_id: int, reason: str):
        """Record a vouch"""
        vouch = {
            'voucher': voucher_id,
            'reason': reason,
            'timestamp': datetime.utcnow().isoformat(),
            'rep_amount': Config.VOUCH_REP_AMOUNT
        }
        self.vouch_history[target_id].append(vouch)
        self.last_vouch[voucher_id] = datetime.utcnow().timestamp()
        self.save_data()
    
    def get_vouch_cooldown(self, user_id: int) -> Optional[float]:
        """Get remaining cooldown time for user"""
        if user_id not in self.last_vouch:
            return None
        
        last_vouch_time = self.last_vouch[user_id]
        current_time = datetime.utcnow().timestamp()
        time_passed = current_time - last_vouch_time
        
        if time_passed >= Config.VOUCH_COOLDOWN:
            return None
        
        return Config.VOUCH_COOLDOWN - time_passed
    
    def get_leaderboard(self) -> List[tuple]:
        """Get sorted leaderboard"""
        return sorted(self.reputation.items(), key=lambda x: x[1], reverse=True)
    
    def get_vouch_history(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Get recent vouch history for user"""
        history = self.vouch_history.get(user_id, [])
        return history[-limit:][::-1]  # Last 10, reversed (newest first)

# Bot Setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(
    command_prefix=Config.PREFIX,
    intents=intents,
    help_command=None,
    case_insensitive=True
)

data_manager = DataManager()

def is_owner():
    """Check if user is bot owner"""
    async def predicate(ctx):
        if ctx.author.id != Config.OWNER_ID:
            await ctx.send("Only the bot owner can use this command.")
            return False
        return True
    return commands.check(predicate)

def format_time(seconds: float) -> str:
    """Format seconds into readable time"""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    
    if minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"

@bot.event
async def on_ready():
    """Bot startup"""
    print('=' * 70)
    print(f'Bot Online: {bot.user}')
    print(f'Servers: {len(bot.guilds)}')
    print(f'Users: {len(bot.users)}')
    print(f'Prefix: {Config.PREFIX}')
    print('=' * 70)
    
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} slash commands')
    except Exception as e:
        logging.error(f'Command sync failed: {e}')
    
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{Config.PREFIX}vouch | Reputation System"
        ),
        status=discord.Status.online
    )
    
    print('All systems active')
    print('=' * 70)

"""
Reputation Bot - Part 2: Leaderboard with Pagination
Add this after Part 1
"""

class LeaderboardView(View):
    """Interactive leaderboard with page navigation"""
    
    def __init__(self, ctx, pages: List[discord.Embed], timeout=180):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.pages = pages
        self.current_page = 0
        self.message = None
        
        # Update button states
        self.update_buttons()
    
    def update_buttons(self):
        """Update button states based on current page"""
        self.first_page.disabled = self.current_page == 0
        self.prev_page.disabled = self.current_page == 0
        self.next_page.disabled = self.current_page == len(self.pages) - 1
        self.last_page.disabled = self.current_page == len(self.pages) - 1
    
    @discord.ui.button(label="⏮️", style=discord.ButtonStyle.gray, custom_id="first")
    async def first_page(self, interaction: discord.Interaction, button: Button):
        """Go to first page"""
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                "Only the command user can control this.",
                ephemeral=True
            )
            return
        
        self.current_page = 0
        self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
    
    @discord.ui.button(label="◀️", style=discord.ButtonStyle.primary, custom_id="prev")
    async def prev_page(self, interaction: discord.Interaction, button: Button):
        """Go to previous page"""
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                "Only the command user can control this.",
                ephemeral=True
            )
            return
        
        self.current_page = max(0, self.current_page - 1)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
    
    @discord.ui.button(label="▶️", style=discord.ButtonStyle.primary, custom_id="next")
    async def next_page(self, interaction: discord.Interaction, button: Button):
        """Go to next page"""
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                "Only the command user can control this.",
                ephemeral=True
            )
            return
        
        self.current_page = min(len(self.pages) - 1, self.current_page + 1)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
    
    @discord.ui.button(label="⏭️", style=discord.ButtonStyle.gray, custom_id="last")
    async def last_page(self, interaction: discord.Interaction, button: Button):
        """Go to last page"""
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                "Only the command user can control this.",
                ephemeral=True
            )
            return
        
        self.current_page = len(self.pages) - 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
    
    @discord.ui.button(label="🗑️", style=discord.ButtonStyle.danger, custom_id="delete")
    async def delete_message(self, interaction: discord.Interaction, button: Button):
        """Delete the leaderboard"""
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                "Only the command user can delete this.",
                ephemeral=True
            )
            return
        
        await interaction.message.delete()
        self.stop()
    
    async def on_timeout(self):
        """Disable buttons on timeout"""
        for item in self.children:
            item.disabled = True
        
        if self.message:
            try:
                await self.message.edit(view=self)
            except:
                pass

def create_leaderboard_pages(leaderboard: List[tuple], bot: commands.Bot) -> List[discord.Embed]:
    """Create paginated leaderboard embeds"""
    if not leaderboard:
        embed = discord.Embed(
            title="📊 Reputation Leaderboard",
            description="No reputation data yet. Start vouching!",
            color=discord.Color.blue()
        )
        return [embed]
    
    pages = []
    total_pages = (len(leaderboard) + Config.LEADERBOARD_PER_PAGE - 1) // Config.LEADERBOARD_PER_PAGE
    
    for page_num in range(total_pages):
        start_idx = page_num * Config.LEADERBOARD_PER_PAGE
        end_idx = start_idx + Config.LEADERBOARD_PER_PAGE
        page_data = leaderboard[start_idx:end_idx]
        
        embed = discord.Embed(
            title="📊 Reputation Leaderboard",
            description="Users ranked by reputation points",
            color=discord.Color.gold()
        )
        
        leaderboard_text = []
        for idx, (user_id, rep) in enumerate(page_data, start=start_idx + 1):
            user = bot.get_user(user_id)
            
            # Medal emojis for top 3
            if idx == 1:
                medal = "🥇"
            elif idx == 2:
                medal = "🥈"
            elif idx == 3:
                medal = "🥉"
            else:
                medal = f"`#{idx}`"
            
            user_name = user.name if user else f"Unknown User"
            leaderboard_text.append(f"{medal} **{user_name}** - {rep} rep")
        
        embed.add_field(
            name=f"Rankings {start_idx + 1}-{start_idx + len(page_data)}",
            value="\n".join(leaderboard_text),
            inline=False
        )
        
        embed.set_footer(text=f"Page {page_num + 1}/{total_pages} | Total Users: {len(leaderboard)}")
        embed.timestamp = datetime.utcnow()
        
        pages.append(embed)
    
    return pages

@bot.command(name='leaderboard', aliases=['lb', 'top'])
async def leaderboard_cmd(ctx):
    """View the reputation leaderboard"""
    leaderboard = data_manager.get_leaderboard()
    
    if not leaderboard:
        embed = discord.Embed(
            title="📊 Reputation Leaderboard",
            description="No reputation data yet. Use `!vouch @user reason` to give reputation!",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)
        return
    
    pages = create_leaderboard_pages(leaderboard, bot)
    
    if len(pages) == 1:
        await ctx.send(embed=pages[0])
    else:
        view = LeaderboardView(ctx, pages)
        view.message = await ctx.send(embed=pages[0], view=view)

@bot.command(name='rank', aliases=['rep', 'reputation'])
async def rank_cmd(ctx, member: discord.Member = None):
    """Check reputation of a user"""
    member = member or ctx.author
    
    rep = data_manager.get_reputation(member.id)
    leaderboard = data_manager.get_leaderboard()
    
    # Find rank
    rank = None
    for idx, (user_id, _) in enumerate(leaderboard, 1):
        if user_id == member.id:
            rank = idx
            break
    
    embed = discord.Embed(
        title=f"{member.display_name}'s Reputation",
        color=discord.Color.blue()
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    
    embed.add_field(name="Reputation", value=f"⭐ {rep}", inline=True)
    embed.add_field(name="Rank", value=f"#{rank}" if rank else "Unranked", inline=True)
    embed.add_field(name="Total Users", value=str(len(leaderboard)), inline=True)
    
    # Get recent vouches
    recent_vouches = data_manager.get_vouch_history(member.id, limit=5)
    if recent_vouches:
        vouch_text = []
        for vouch in recent_vouches:
            voucher = bot.get_user(vouch['voucher'])
            voucher_name = voucher.name if voucher else "Unknown"
            timestamp = datetime.fromisoformat(vouch['timestamp'])
            time_str = timestamp.strftime('%Y-%m-%d %H:%M')
            vouch_text.append(f"**{voucher_name}**: {vouch['reason']}\n*{time_str}*")
        
        embed.add_field(
            name="Recent Vouches (Last 5)",
            value="\n\n".join(vouch_text[:5]),
            inline=False
        )
    
    embed.set_footer(text=f"Requested by {ctx.author.name}")
    
    await ctx.send(embed=embed)

"""
Reputation Bot - Part 3: Vouch Command System
Add this after Part 2
"""

@bot.command(name='vouch')
async def vouch_cmd(ctx, member: discord.Member, *, reason: str = None):
    """Vouch for a user and give them reputation"""
    
    # Disclaimer embed if no reason provided
    if not reason or len(reason.strip()) < 3:
        disclaimer_embed = discord.Embed(
            title="⚠️ Vouch Reason Required",
            description=(
                "You must provide a valid reason when vouching for someone.\n\n"
                "**Proper Usage:**\n"
                "`!vouch @user reason for vouching`\n\n"
                "**Examples:**\n"
                "✅ `!vouch @John Great trader, smooth deal!`\n"
                "✅ `!vouch @Sarah Trustworthy and fast service`\n"
                "❌ `!vouch @Mike`\n"
                "❌ `!vouch @Alex good`\n\n"
                "⚠️ **WARNING:** Vouching without a valid reason will result in punishment."
            ),
            color=discord.Color.red()
        )
        await ctx.send(embed=disclaimer_embed)
        return
    
    # Check if vouching self
    if member.id == ctx.author.id:
        embed = discord.Embed(
            title="❌ Cannot Vouch Yourself",
            description="You cannot vouch for yourself!",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return
    
    # Check if target is a bot
    if member.bot:
        embed = discord.Embed(
            title="❌ Cannot Vouch Bots",
            description="You cannot vouch for bots!",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return
    
    # Check cooldown
    cooldown = data_manager.get_vouch_cooldown(ctx.author.id)
    if cooldown is not None:
        time_remaining = format_time(cooldown)
        
        embed = discord.Embed(
            title="⏰ Vouch Cooldown Active",
            description=f"You can vouch again in **{time_remaining}**",
            color=discord.Color.orange()
        )
        embed.add_field(
            name="Cooldown",
            value=f"You can vouch once every {Config.VOUCH_COOLDOWN // 60} minutes",
            inline=False
        )
        embed.set_footer(text=f"Requested by {ctx.author.name}")
        
        await ctx.send(embed=embed)
        return
    
    # Add reputation
    data_manager.add_reputation(member.id, Config.VOUCH_REP_AMOUNT)
    data_manager.add_vouch(member.id, ctx.author.id, reason)
    
    new_rep = data_manager.get_reputation(member.id)
    
    # Success embed
    embed = discord.Embed(
        title="✅ Vouch Successful",
        description=f"{ctx.author.mention} vouched for {member.mention}",
        color=discord.Color.green()
    )
    
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(name="Reputation Given", value=f"+{Config.VOUCH_REP_AMOUNT} ⭐", inline=True)
    embed.add_field(name="New Total", value=f"{new_rep} ⭐", inline=True)
    embed.add_field(
        name="Next Vouch",
        value=f"Available in {Config.VOUCH_COOLDOWN // 60} minutes",
        inline=False
    )
    
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text=f"Vouched by {ctx.author.name}")
    
    await ctx.send(embed=embed)
    
    # Try to notify the user
    try:
        dm_embed = discord.Embed(
            title="🎉 You Received a Vouch!",
            description=f"**{ctx.author.name}** vouched for you in **{ctx.guild.name}**",
            color=discord.Color.gold()
        )
        dm_embed.add_field(name="Reason", value=reason, inline=False)
        dm_embed.add_field(name="Reputation Gained", value=f"+{Config.VOUCH_REP_AMOUNT} ⭐", inline=True)
        dm_embed.add_field(name="Total Reputation", value=f"{new_rep} ⭐", inline=True)
        dm_embed.timestamp = datetime.utcnow()
        
        await member.send(embed=dm_embed)
    except:
        pass

@bot.command(name='vouchhistory', aliases=['vh', 'vouches'])
async def vouch_history_cmd(ctx, member: discord.Member = None):
    """View vouch history for a user"""
    member = member or ctx.author
    
    vouches = data_manager.get_vouch_history(member.id, limit=10)
    
    if not vouches:
        embed = discord.Embed(
            title=f"{member.display_name}'s Vouch History",
            description="No vouches yet.",
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        await ctx.send(embed=embed)
        return
    
    embed = discord.Embed(
        title=f"{member.display_name}'s Vouch History",
        description=f"Showing last {len(vouches)} vouches",
        color=discord.Color.blue()
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    
    for idx, vouch in enumerate(vouches, 1):
        voucher = bot.get_user(vouch['voucher'])
        voucher_name = voucher.name if voucher else "Unknown User"
        
        timestamp = datetime.fromisoformat(vouch['timestamp'])
        time_str = timestamp.strftime('%Y-%m-%d %H:%M UTC')
        
        embed.add_field(
            name=f"Vouch #{idx} - {voucher_name}",
            value=f"**Reason:** {vouch['reason']}\n**Rep Given:** +{vouch['rep_amount']} ⭐\n**Date:** {time_str}",
            inline=False
        )
    
    total_rep = data_manager.get_reputation(member.id)
    embed.set_footer(text=f"Total Reputation: {total_rep} ⭐")
    
    await ctx.send(embed=embed)

@bot.command(name='cooldown', aliases=['cd'])
async def cooldown_cmd(ctx):
    """Check your vouch cooldown"""
    cooldown = data_manager.get_vouch_cooldown(ctx.author.id)
    
    embed = discord.Embed(
        title="⏰ Vouch Cooldown",
        color=discord.Color.blue()
    )
    
    if cooldown is None:
        embed.description = "✅ You can vouch now!"
        embed.add_field(
            name="Usage",
            value=f"`{Config.PREFIX}vouch @user reason`",
            inline=False
        )
    else:
        time_remaining = format_time(cooldown)
        embed.description = f"You can vouch again in **{time_remaining}**"
        embed.add_field(
            name="Cooldown Duration",
            value=f"{Config.VOUCH_COOLDOWN // 60} minutes",
            inline=False
        )
    
    embed.set_footer(text=f"Requested by {ctx.author.name}")
    
    await ctx.send(embed=embed)

"""
Reputation Bot - Part 4: Owner Management Commands
Add this after Part 3
"""

@bot.command(name='addrep')
@is_owner()
async def addrep_cmd(ctx, member: discord.Member, amount: int):
    """Add reputation to a user (Owner only)"""
    if amount <= 0:
        await ctx.send("Amount must be greater than 0")
        return
    
    old_rep = data_manager.get_reputation(member.id)
    data_manager.add_reputation(member.id, amount)
    new_rep = data_manager.get_reputation(member.id)
    
    embed = discord.Embed(
        title="✅ Reputation Added",
        description=f"Added reputation to {member.mention}",
        color=discord.Color.green()
    )
    
    embed.add_field(name="Previous Rep", value=f"{old_rep} ⭐", inline=True)
    embed.add_field(name="Amount Added", value=f"+{amount} ⭐", inline=True)
    embed.add_field(name="New Total", value=f"{new_rep} ⭐", inline=True)
    
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text=f"Modified by {ctx.author.name}")
    
    await ctx.send(embed=embed)
    
    logging.info(f"Owner {ctx.author.name} added {amount} rep to {member.name}")

@bot.command(name='removerep')
@is_owner()
async def removerep_cmd(ctx, member: discord.Member, amount: int):
    """Remove reputation from a user (Owner only)"""
    if amount <= 0:
        await ctx.send("Amount must be greater than 0")
        return
    
    old_rep = data_manager.get_reputation(member.id)
    data_manager.remove_reputation(member.id, amount)
    new_rep = data_manager.get_reputation(member.id)
    
    embed = discord.Embed(
        title="✅ Reputation Removed",
        description=f"Removed reputation from {member.mention}",
        color=discord.Color.orange()
    )
    
    embed.add_field(name="Previous Rep", value=f"{old_rep} ⭐", inline=True)
    embed.add_field(name="Amount Removed", value=f"-{amount} ⭐", inline=True)
    embed.add_field(name="New Total", value=f"{new_rep} ⭐", inline=True)
    
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text=f"Modified by {ctx.author.name}")
    
    await ctx.send(embed=embed)
    
    logging.info(f"Owner {ctx.author.name} removed {amount} rep from {member.name}")

@bot.command(name='setrep')
@is_owner()
async def setrep_cmd(ctx, member: discord.Member, amount: int):
    """Set a user's reputation to a specific amount (Owner only)"""
    if amount < 0:
        await ctx.send("Amount cannot be negative")
        return
    
    old_rep = data_manager.get_reputation(member.id)
    data_manager.set_reputation(member.id, amount)
    
    embed = discord.Embed(
        title="✅ Reputation Set",
        description=f"Set reputation for {member.mention}",
        color=discord.Color.blue()
    )
    
    embed.add_field(name="Previous Rep", value=f"{old_rep} ⭐", inline=True)
    embed.add_field(name="New Rep", value=f"{amount} ⭐", inline=True)
    embed.add_field(name="Difference", value=f"{amount - old_rep:+d} ⭐", inline=True)
    
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text=f"Modified by {ctx.author.name}")
    
    await ctx.send(embed=embed)
    
    logging.info(f"Owner {ctx.author.name} set {member.name}'s rep to {amount}")

@bot.command(name='clearrep')
@is_owner()
async def clearrep_cmd(ctx, member: discord.Member):
    """Clear all reputation and vouch history for a user (Owner only)"""
    old_rep = data_manager.get_reputation(member.id)
    vouch_count = len(data_manager.get_vouch_history(member.id, limit=999))
    
    # Confirmation
    confirm_embed = discord.Embed(
        title="⚠️ Confirm Clear Reputation",
        description=f"Are you sure you want to clear all data for {member.mention}?",
        color=discord.Color.red()
    )
    confirm_embed.add_field(name="Reputation to Clear", value=f"{old_rep} ⭐", inline=True)
    confirm_embed.add_field(name="Vouches to Clear", value=str(vouch_count), inline=True)
    confirm_embed.add_field(
        name="Confirmation",
        value="React with ✅ to confirm or ❌ to cancel",
        inline=False
    )
    
    msg = await ctx.send(embed=confirm_embed)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")
    
    def check(reaction, user):
        return user == ctx.author and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == msg.id
    
    try:
        reaction, user = await bot.wait_for('reaction_add', timeout=30.0, check=check)
        
        if str(reaction.emoji) == "✅":
            data_manager.clear_reputation(member.id)
            
            success_embed = discord.Embed(
                title="✅ Reputation Cleared",
                description=f"All reputation data cleared for {member.mention}",
                color=discord.Color.green()
            )
            success_embed.add_field(name="Reputation Cleared", value=f"{old_rep} ⭐", inline=True)
            success_embed.add_field(name="Vouches Cleared", value=str(vouch_count), inline=True)
            success_embed.set_footer(text=f"Cleared by {ctx.author.name}")
            success_embed.timestamp = datetime.utcnow()
            
            await msg.edit(embed=success_embed)
            await msg.clear_reactions()
            
            logging.info(f"Owner {ctx.author.name} cleared all rep data for {member.name}")
        else:
            cancel_embed = discord.Embed(
                title="❌ Action Cancelled",
                description="Reputation clear cancelled",
                color=discord.Color.blue()
            )
            await msg.edit(embed=cancel_embed)
            await msg.clear_reactions()
    
    except asyncio.TimeoutError:
        timeout_embed = discord.Embed(
            title="⏰ Confirmation Timeout",
            description="Action cancelled due to timeout",
            color=discord.Color.orange()
        )
        await msg.edit(embed=timeout_embed)
        await msg.clear_reactions()

@bot.command(name='resetcooldown', aliases=['resetcd'])
@is_owner()
async def resetcooldown_cmd(ctx, member: discord.Member):
    """Reset vouch cooldown for a user (Owner only)"""
    if member.id in data_manager.last_vouch:
        del data_manager.last_vouch[member.id]
        data_manager.save_data()
        
        embed = discord.Embed(
            title="✅ Cooldown Reset",
            description=f"Vouch cooldown reset for {member.mention}",
            color=discord.Color.green()
        )
        embed.add_field(name="Status", value="Can vouch immediately", inline=False)
        embed.set_footer(text=f"Reset by {ctx.author.name}")
        
        await ctx.send(embed=embed)
        logging.info(f"Owner {ctx.author.name} reset cooldown for {member.name}")
    else:
        await ctx.send(f"{member.mention} doesn't have an active cooldown.")

@bot.command(name='repstats')
@is_owner()
async def repstats_cmd(ctx):
    """View reputation system statistics (Owner only)"""
    total_users = len(data_manager.reputation)
    total_rep = sum(data_manager.reputation.values())
    total_vouches = sum(len(vouches) for vouches in data_manager.vouch_history.values())
    users_on_cooldown = len([cd for cd in data_manager.last_vouch.values() 
                              if datetime.utcnow().timestamp() - cd < Config.VOUCH_COOLDOWN])
    
    # Get top user
    leaderboard = data_manager.get_leaderboard()
    top_user = None
    if leaderboard:
        top_user_id, top_rep = leaderboard[0]
        top_user = bot.get_user(top_user_id)
    
    embed = discord.Embed(
        title="📊 Reputation System Statistics",
        color=discord.Color.blue(),
    )
    
    embed.add_field(name="Total Users", value=str(total_users), inline=True)
    embed.add_field(name="Total Reputation", value=f"{total_rep} ⭐", inline=True)
    embed.add_field(name="Total Vouches", value=str(total_vouches), inline=True)
    
    embed.add_field(name="Users on Cooldown", value=str(users_on_cooldown), inline=True)
    embed.add_field(name="Vouch Cooldown", value=f"{Config.VOUCH_COOLDOWN // 60} minutes", inline=True)
    embed.add_field(name="Rep per Vouch", value=f"{Config.VOUCH_REP_AMOUNT} ⭐", inline=True)
    
    if top_user:
        embed.add_field(
            name="Top User",
            value=f"{top_user.mention} - {leaderboard[0][1]} ⭐",
            inline=False
        )
    
    embed.set_footer(text=f"Requested by {ctx.author.name}")
    
    await ctx.send(embed=embed)

"""
Reputation Bot - Part 5: Help Command & Web Server
Add this after Part 4 - FINAL PART
"""

@bot.command(name='help')
async def help_cmd(ctx):
    """Display all available commands"""
    is_owner_user = ctx.author.id == Config.OWNER_ID
    
    embed = discord.Embed(
        title="📖 Reputation Bot - Commands",
        description=f"Prefix: `{Config.PREFIX}` | Vouch Cooldown: {Config.VOUCH_COOLDOWN // 60} minutes",
        color=discord.Color.blue()
    )
    
    # Public Commands
    embed.add_field(
        name="🌟 Reputation Commands",
        value=(
            f"`{Config.PREFIX}vouch @user reason` - Vouch for a user (+{Config.VOUCH_REP_AMOUNT} rep)\n"
            f"`{Config.PREFIX}leaderboard` - View reputation leaderboard\n"
            f"`{Config.PREFIX}rank [@user]` - Check reputation\n"
            f"`{Config.PREFIX}vouchhistory [@user]` - View vouch history\n"
            f"`{Config.PREFIX}cooldown` - Check your vouch cooldown"
        ),
        inline=False
    )
    
    # Owner Commands
    if is_owner_user:
        embed.add_field(
            name="👑 Owner Commands",
            value=(
                f"`{Config.PREFIX}addrep @user amount` - Add reputation\n"
                f"`{Config.PREFIX}removerep @user amount` - Remove reputation\n"
                f"`{Config.PREFIX}setrep @user amount` - Set reputation\n"
                f"`{Config.PREFIX}clearrep @user` - Clear all user data\n"
                f"`{Config.PREFIX}resetcooldown @user` - Reset vouch cooldown\n"
                f"`{Config.PREFIX}repstats` - View system statistics"
            ),
            inline=False
        )
    
    # Information
    embed.add_field(
        name="ℹ️ Information",
        value=(
            f"• Each vouch gives **{Config.VOUCH_REP_AMOUNT} reputation** points\n"
            f"• You can vouch once every **{Config.VOUCH_COOLDOWN // 60} minutes**\n"
            f"• You must provide a valid reason when vouching\n"
            f"• Use the leaderboard buttons to navigate pages"
        ),
        inline=False
    )
    
    # Warning
    embed.add_field(
        name="⚠️ Important Warning",
        value=(
            "**Vouching without a valid reason will result in punishment.**\n"
            "Always provide a detailed reason for your vouch.\n"
            "Example: `!vouch @user Great trader, smooth transaction!`"
        ),
        inline=False
    )
    
    embed.set_footer(text=f"Requested by {ctx.author.name}")
    
    await ctx.send(embed=embed)

@bot.command(name='aliases')
async def aliases_cmd(ctx):
    """Show command aliases"""
    embed = discord.Embed(
        title="📝 Command Aliases",
        description="Alternative ways to use commands",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="Leaderboard",
        value="`!leaderboard` = `!lb` = `!top`",
        inline=False
    )
    
    embed.add_field(
        name="Rank",
        value="`!rank` = `!rep` = `!reputation`",
        inline=False
    )
    
    embed.add_field(
        name="Vouch History",
        value="`!vouchhistory` = `!vh` = `!vouches`",
        inline=False
    )
    
    embed.add_field(
        name="Cooldown",
        value="`!cooldown` = `!cd`",
        inline=False
    )
    
    if ctx.author.id == Config.OWNER_ID:
        embed.add_field(
            name="Reset Cooldown",
            value="`!resetcooldown` = `!resetcd`",
            inline=False
        )
    
    await ctx.send(embed=embed)

# Error Handler
@bot.event
async def on_command_error(ctx, error):
    """Handle command errors"""
    if isinstance(error, commands.CommandNotFound):
        return
    
    elif isinstance(error, commands.MissingRequiredArgument):
        embed = discord.Embed(
            title="❌ Missing Argument",
            description=f"Missing required argument: `{error.param.name}`",
            color=discord.Color.red()
        )
        embed.add_field(
            name="Help",
            value=f"Use `{Config.PREFIX}help` to see command usage",
            inline=False
        )
        await ctx.send(embed=embed)
    
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("Member not found. Make sure you mention a valid server member.")
    
    elif isinstance(error, commands.BadArgument):
        await ctx.send("Invalid argument provided. Check your command syntax.")
    
    elif isinstance(error, commands.CheckFailure):
        # Already handled by is_owner check
        pass
    
    else:
        logging.error(f'Command error in {ctx.command}: {error}')
        await ctx.send("An error occurred while executing this command.")

# Keep-Alive Web Server
async def start_keep_alive():
    """Start web server for 24/7 hosting"""
    from aiohttp import web
    
    async def health(request):
        return web.Response(text='Bot Online!', status=200)
    
    async def status_page(request):
        leaderboard = data_manager.get_leaderboard()
        total_rep = sum(data_manager.reputation.values())
        
        html = f'''
<!DOCTYPE html>
<html>
<head>
    <title>Reputation Bot</title>
    <style>
        body {{
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }}
        .container {{
            text-align: center;
            padding: 40px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 20px;
            backdrop-filter: blur(10px);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            max-width: 600px;
        }}
        h1 {{ font-size: 48px; margin: 0 0 20px 0; }}
        .status {{ font-size: 24px; margin: 20px 0; }}
        .info {{ font-size: 18px; margin: 10px 0; opacity: 0.9; }}
        .badge {{
            display: inline-block;
            padding: 8px 16px;
            background: rgba(255, 255, 255, 0.2);
            border-radius: 20px;
            margin: 5px;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>⭐ Reputation Bot</h1>
        <div class="status">✅ ONLINE</div>
        <div class="info">Servers: {len(bot.guilds)}</div>
        <div class="info">Total Users: {len(leaderboard)}</div>
        <div class="info">Total Reputation: {total_rep}</div>
        <div class="info">Prefix: {Config.PREFIX}</div>
        <div class="info">Latency: {round(bot.latency * 1000)}ms</div>
        <div style="margin-top: 20px;">
            <span class="badge">Vouch: {Config.VOUCH_REP_AMOUNT} Rep</span>
            <span class="badge">Cooldown: {Config.VOUCH_COOLDOWN // 60} min</span>
        </div>
    </div>
</body>
</html>
        '''
        return web.Response(text=html, content_type='text/html')
    
    async def stats(request):
        leaderboard = data_manager.get_leaderboard()
        stats_data = {
            'online': True,
            'servers': len(bot.guilds),
            'users': len(bot.users),
            'total_users_with_rep': len(leaderboard),
            'total_reputation': sum(data_manager.reputation.values()),
            'prefix': Config.PREFIX,
            'latency': round(bot.latency * 1000),
            'vouch_amount': Config.VOUCH_REP_AMOUNT,
            'vouch_cooldown_minutes': Config.VOUCH_COOLDOWN // 60
        }
        return web.json_response(stats_data)
    
    app = web.Application()
    app.router.add_get('/', status_page)
    app.router.add_get('/health', health)
    app.router.add_get('/ping', health)
    app.router.add_get('/stats', stats)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', Config.PORT)
    await site.start()
    
    logging.info(f'Web server running on port {Config.PORT}')

# Main Function
async def main():
    """Main bot startup"""
    await start_keep_alive()
    
    try:
        await bot.start(Config.TOKEN)
    except KeyboardInterrupt:
        logging.info('Bot shutdown requested')
        await bot.close()
    except Exception as e:
        logging.error(f'Bot error: {e}')
        await bot.close()

# Run Bot
if __name__ == '__main__':
    print('=' * 70)
    print('REPUTATION & VOUCH BOT')
    print('=' * 70)
    print(f'Owner ID: {Config.OWNER_ID}')
    print(f'Prefix: {Config.PREFIX}')
    print(f'Vouch Amount: {Config.VOUCH_REP_AMOUNT} rep')
    print(f'Vouch Cooldown: {Config.VOUCH_COOLDOWN // 60} minutes')
    print(f'Port: {Config.PORT}')
    print('=' * 70)
    
    if not Config.TOKEN:
        logging.error('DISCORD_BOT_TOKEN not set!')
        print('\nERROR: DISCORD_BOT_TOKEN not found!')
        print('Set it in your environment variables or .env file')
        exit(1)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info('Bot stopped by user')
    except Exception as e:
        logging.error(f'Failed to start: {e}')
        print(f'\nFailed to start: {e}')
