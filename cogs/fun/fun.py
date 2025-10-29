import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
from datetime import datetime
from typing import Union, Optional
import pytz
import aiohttp
import random
import json
import re

class TicTacToeButton(discord.ui.Button):
    def __init__(self, x: int, y: int):
        position = y * 3 + x + 1
        super().__init__(style=discord.ButtonStyle.gray, label=str(position), row=y)
        self.x = x
        self.y = y

    async def callback(self, interaction: discord.Interaction):
        view: TicTacToeView = self.view
        state = view.board[self.y][self.x]
        
        # Check if it's the correct player's turn
        if interaction.user.id != view.current_player:
            await interaction.response.send_message('It\'s not your turn!', ephemeral=True)
            return
        
        # Check if spot is already taken
        if state is not None:
            await interaction.response.send_message('This spot is already taken!', ephemeral=True)
            return

        # Make the move
        view.board[self.y][self.x] = view.players[view.current_player]
        self.style = discord.ButtonStyle.blurple if view.players[view.current_player] == 'X' else discord.ButtonStyle.red
        self.label = view.players[view.current_player]
        self.disabled = True

        # Check for winner
        winner = view.check_winner()
        if winner:
            for child in view.children:
                child.disabled = True
            view.stop()
            
            embed = discord.Embed(
                title='🎮 Tic Tac Toe',
                description=f'🎉 <@{view.current_player}> ({view.players[view.current_player]}) wins!\n\n<@{view.player1}> (🔵 X) vs <@{view.player2}> (🔴 O)',
                color=view.color
            )
            await interaction.response.edit_message(embed=embed, view=view)
            return

        # Check for tie
        if view.check_tie():
            for child in view.children:
                child.disabled = True
            view.stop()
            
            embed = discord.Embed(
                title='🎮 Tic Tac Toe',
                description=f'🤝 It\'s a tie!\n\n<@{view.player1}> (🔵 X) vs <@{view.player2}> (🔴 O)',
                color=view.color
            )
            await interaction.response.edit_message(embed=embed, view=view)
            return

        # Switch player
        view.current_player = view.player1 if view.current_player == view.player2 else view.player2
        
        embed = discord.Embed(
            title='🎮 Tic Tac Toe',
            description=f'<@{view.player1}> (🔵 X) vs <@{view.player2}> (🔴 O)\n\n**Current Turn:** <@{view.current_player}> ({view.players[view.current_player]})',
            color=view.color
        )
        await interaction.response.edit_message(embed=embed, view=view)


class TicTacToeView(discord.ui.View):
    def __init__(self, player1: discord.User, player2: discord.User, color: int):
        super().__init__(timeout=300)
        self.player1 = player1.id
        self.player2 = player2.id
        self.current_player = self.player1
        self.players = {self.player1: 'X', self.player2: 'O'}
        self.board = [[None, None, None], [None, None, None], [None, None, None]]
        self.color = color
        
        # Add 9 buttons (3x3 grid)
        for y in range(3):
            for x in range(3):
                self.add_item(TicTacToeButton(x, y))

    def check_winner(self):
        # Check rows
        for row in self.board:
            if row[0] == row[1] == row[2] and row[0] is not None:
                return True
        
        # Check columns
        for col in range(3):
            if self.board[0][col] == self.board[1][col] == self.board[2][col] and self.board[0][col] is not None:
                return True
        
        # Check diagonals
        if self.board[0][0] == self.board[1][1] == self.board[2][2] and self.board[0][0] is not None:
            return True
        if self.board[0][2] == self.board[1][1] == self.board[2][0] and self.board[0][2] is not None:
            return True
        
        return False

    def check_tie(self):
        for row in self.board:
            for cell in row:
                if cell is None:
                    return False
        return True

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        self.stop()

class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.timezone_db = "data/timezones.db"
        self.bday_db = "data/bday.db"
        self.api_base = "https://nekos.best/api/v2/"
        self.init_databases()
        self.color = 0xa6afe7
        self.eightball_responses = [
            # Positive responses
            "It is certain.", "It is decidedly so.", "Without a doubt.",
            "Yes definitely.", "You may rely on it.", "As I see it, yes.",
            "Most likely.", "Outlook good.", "Yes.", "Signs point to yes.",
            
            # Non-committal responses
            "Reply hazy, try again.", "Ask again later.", "Better not tell you now.",
            "Cannot predict now.", "Concentrate and ask again.",
            
            # Negative responses
            "Don't count on it.", "My reply is no.", "My sources say no.",
            "Outlook not so good.", "Very doubtful."
        ]
        
        # Coin flip options
        self.coin_sides = ["Heads", "Tails"]
        
        # Dice emojis
        self.dice_emojis = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]
    
    async def get_gif(self, endpoint: str):
        """Fetch a GIF from nekos.best API"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.api_base}{endpoint}") as response:
                    if response.status == 200:
                        data = await response.json()
                        return data['results'][0]['url']
        except:
            pass
        return None

    def init_databases(self):
        """Initialize the SQLite databases"""
        # Timezone database
        conn = sqlite3.connect(self.timezone_db)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS timezones (
                discord_id INTEGER PRIMARY KEY,
                timezone TEXT NOT NULL
            )
        ''')
        conn.commit()
        conn.close()
        
        # Birthday database
        conn = sqlite3.connect(self.bday_db)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS birthdays (
                discord_id INTEGER PRIMARY KEY,
                birthday TEXT NOT NULL
            )
        ''')
        conn.commit()
        conn.close()
    
    # ===== TIMEZONE HELPER FUNCTIONS =====
    
    def get_user_timezone(self, discord_id):
        """Get user's timezone from database"""
        conn = sqlite3.connect(self.timezone_db)
        cursor = conn.cursor()
        cursor.execute('SELECT timezone FROM timezones WHERE discord_id = ?', (discord_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    
    def set_user_timezone(self, discord_id, timezone):
        """Set user's timezone in database"""
        conn = sqlite3.connect(self.timezone_db)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO timezones (discord_id, timezone)
            VALUES (?, ?)
        ''', (discord_id, timezone))
        conn.commit()
        conn.close()
    
    # ===== BIRTHDAY HELPER FUNCTIONS =====
    
    def get_user_birthday(self, discord_id):
        """Get user's birthday from database"""
        conn = sqlite3.connect(self.bday_db)
        cursor = conn.cursor()
        cursor.execute('SELECT birthday FROM birthdays WHERE discord_id = ?', (discord_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    
    def set_user_birthday(self, discord_id, birthday):
        """Set user's birthday in database"""
        conn = sqlite3.connect(self.bday_db)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO birthdays (discord_id, birthday)
            VALUES (?, ?)
        ''', (discord_id, birthday))
        conn.commit()
        conn.close()
    
    # ===== TIMEZONE COMMANDS =====
    
    @commands.group(name="timezone", aliases=["tz"], invoke_without_command=True)
    async def timezone(self, ctx, user: Union[discord.Member, discord.User] = None):
        """View your timezone or another user's timezone"""
        
        target_user = user or ctx.author
        user_tz = self.get_user_timezone(target_user.id)
        
        if not user_tz:
            if target_user == ctx.author:
                embed = discord.Embed(
                    description=f"❌ You haven't set your timezone! Use `{ctx.prefix}timezone set <timezone>`\n\nExamples: `America/New_York`, `Europe/London`, `Asia/Tokyo`",
                    color=discord.Color.from_str("#a6afe7")
                )
            else:
                embed = discord.Embed(
                    description=f"❌ **{target_user.name}** hasn't set their timezone!",
                    color=discord.Color.from_str("#a6afe7")
                )
            return await ctx.send(embed=embed)
        
        try:
            tz = pytz.timezone(user_tz)
            current_time = datetime.now(tz).strftime("%B %d, %I:%M %p")
            
            if target_user == ctx.author:
                description = f"⏰ {target_user.mention} Your current time is **{current_time}**"
            else:
                description = f"⏰ {target_user.mention} Your current time is **{current_time}**"
            
            embed = discord.Embed(
                description=description,
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                description="❌ Error fetching timezone information!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
    
    @timezone.command(name="set")
    async def timezone_set(self, ctx, *, timezone: str):
        """Set your timezone (e.g. America/New_York, Europe/London, Asia/Tokyo)"""
        
        try:
            # Validate timezone
            tz = pytz.timezone(timezone)
            self.set_user_timezone(ctx.author.id, timezone)
            
            current_time = datetime.now(tz).strftime("%I:%M %p")
            
            embed = discord.Embed(
                description=f"✅ Your timezone has been set to **{timezone}**\n**Current Time:** {current_time}",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
        except pytz.exceptions.UnknownTimeZoneError:
            embed = discord.Embed(
                description=f"❌ Invalid timezone! Use format like `America/New_York`, `Europe/London`, `Asia/Tokyo`\n\nFind your timezone: <https://en.wikipedia.org/wiki/List_of_tz_database_time_zones>",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
    
    @timezone.command(name="remove", aliases=["delete"])
    async def timezone_remove(self, ctx):
        """Remove your timezone"""
        
        user_tz = self.get_user_timezone(ctx.author.id)
        
        if not user_tz:
            embed = discord.Embed(
                description="❌ You don't have a timezone set!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        conn = sqlite3.connect(self.timezone_db)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM timezones WHERE discord_id = ?', (ctx.author.id,))
        conn.commit()
        conn.close()
        
        embed = discord.Embed(
            description="✅ Your timezone has been removed",
            color=discord.Color.from_str("#a6afe7")
        )
        await ctx.send(embed=embed)
    
    # ===== BIRTHDAY COMMANDS =====
    
    @commands.group(name="birthday", aliases=["bday"], invoke_without_command=True)
    async def birthday(self, ctx, user: Union[discord.Member, discord.User] = None):
        """View your birthday or another user's birthday"""
        
        target_user = user or ctx.author
        user_bday = self.get_user_birthday(target_user.id)
        
        if not user_bday:
            if target_user == ctx.author:
                embed = discord.Embed(
                    description=f"❌ You haven't set your birthday! Use `{ctx.prefix}birthday set <MM/DD>` or `{ctx.prefix}birthday set <MM/DD/YYYY>`",
                    color=discord.Color.from_str("#a6afe7")
                )
            else:
                embed = discord.Embed(
                    description=f"❌ **{target_user.name}** hasn't set their birthday!",
                    color=discord.Color.from_str("#a6afe7")
                )
            return await ctx.send(embed=embed)
        
        try:
            # Parse birthday
            if len(user_bday.split('/')) == 3:
                bday_obj = datetime.strptime(user_bday, "%m/%d/%Y")
                # Calculate next birthday occurrence
                today = datetime.now()
                next_bday = datetime(bday_obj.month, bday_obj.day)
                if next_bday < today:
                    next_bday = datetime(bday_obj.month, bday_obj.day)
            else:
                bday_obj = datetime.strptime(user_bday, "%m/%d")
                # Calculate next birthday occurrence
                today = datetime.now()
                next_bday = datetime(today.year, bday_obj.month, bday_obj.day)
                if next_bday < today:
                    next_bday = datetime(today.year + 1, bday_obj.month, bday_obj.day)
            
            # Format date as text
            formatted_date = next_bday.strftime("%B %d, %Y")
            
            # Convert to Unix timestamp for relative time
            unix_timestamp = int(next_bday.timestamp())
            
            if target_user == ctx.author:
                description = f"🎂 Your **birthday** is **{formatted_date}**. That's <t:{unix_timestamp}:R>!"
            else:
                description = f"🎂 {target_user.mention} Your **birthday** is **{formatted_date}**. That's <t:{unix_timestamp}:R>!"
            
            embed = discord.Embed(
                description=description,
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                description="❌ Error fetching birthday information!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
    
    @birthday.command(name="set")
    async def birthday_set(self, ctx, *, birthday: str):
        """Set your birthday (format: MM/DD, MM/DD/YYYY, 18 sep, or sep 18)"""
        
        try:
            bday_obj = None
            stored_format = None
            
            # Try MM/DD or MM/DD/YYYY format first
            if '/' in birthday:
                parts = birthday.split('/')
                if len(parts) == 2:
                    # MM/DD format
                    bday_obj = datetime.strptime(birthday, "%m/%d")
                    formatted_bday = bday_obj.strftime("%B %d")
                    stored_format = birthday
                elif len(parts) == 3:
                    # MM/DD/YYYY format
                    bday_obj = datetime.strptime(birthday, "%m/%d/%Y")
                    formatted_bday = bday_obj.strftime("%B %d, %Y")
                    stored_format = birthday
            else:
                # Try "18 sep" or "sep 18" format
                parts = birthday.lower().split()
                if len(parts) == 2:
                    # Try "18 sep" format (day month)
                    try:
                        bday_obj = datetime.strptime(birthday, "%d %b")
                        stored_format = bday_obj.strftime("%m/%d")
                        formatted_bday = bday_obj.strftime("%B %d")
                    except ValueError:
                        # Try "sep 18" format (month day)
                        try:
                            bday_obj = datetime.strptime(birthday, "%b %d")
                            stored_format = bday_obj.strftime("%m/%d")
                            formatted_bday = bday_obj.strftime("%B %d")
                        except ValueError:
                            pass
                elif len(parts) == 3:
                    # Try with year: "18 sep 2000" or "sep 18 2000"
                    try:
                        bday_obj = datetime.strptime(birthday, "%d %b %Y")
                        stored_format = bday_obj.strftime("%m/%d/%Y")
                        formatted_bday = bday_obj.strftime("%B %d, %Y")
                    except ValueError:
                        try:
                            bday_obj = datetime.strptime(birthday, "%b %d %Y")
                            stored_format = bday_obj.strftime("%m/%d/%Y")
                            formatted_bday = bday_obj.strftime("%B %d, %Y")
                        except ValueError:
                            pass
            
            if bday_obj is None or stored_format is None:
                raise ValueError("Invalid format")
            
            self.set_user_birthday(ctx.author.id, stored_format)
            
            embed = discord.Embed(
                description=f"✅ Your birthday has been set to **{formatted_bday}**",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
        except ValueError:
            embed = discord.Embed(
                description=f"❌ Invalid birthday format! Use one of these formats:\n`MM/DD` • `MM/DD/YYYY` • `18 sep` • `sep 18`\n\nExample: `{ctx.prefix}birthday set 03/15` or `{ctx.prefix}birthday set 18 sep`",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
    
    @birthday.command(name="remove", aliases=["delete"])
    async def birthday_remove(self, ctx):
        """Remove your birthday"""
        
        user_bday = self.get_user_birthday(ctx.author.id)
        
        if not user_bday:
            embed = discord.Embed(
                description="❌ You don't have a birthday set!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        conn = sqlite3.connect(self.bday_db)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM birthdays WHERE discord_id = ?', (ctx.author.id,))
        conn.commit()
        conn.close()
        
        embed = discord.Embed(
            description="✅ Your birthday has been removed",
            color=discord.Color.from_str("#a6afe7")
        )
        await ctx.send(embed=embed)

    @commands.command(name="spotify", aliases=["sp"])
    async def spotify_prefix(self, ctx, user: discord.User = None):
        """Get the current Spotify song from a user's Discord activity"""
        user = user or ctx.author
        
        # Try to get member object
        member = user
        if ctx.guild:
            if isinstance(user, discord.Member):
                member = user
            else:
                member = ctx.guild.get_member(user.id)
        else:
            # In DMs, search mutual guilds
            for guild in self.bot.guilds:
                member = guild.get_member(user.id)
                if member and isinstance(member, discord.Member):
                    break
        
        # Check if we have a member with activities
        if not isinstance(member, discord.Member):
            await ctx.send("❌ Could not find this user in any mutual servers!")
            return
        
        # Look for Spotify activity
        spotify_activity = None
        for activity in member.activities:
            if isinstance(activity, discord.Spotify):
                spotify_activity = activity
                break
        
        if not spotify_activity:
            await ctx.send(f"{user.mention} is not currently listening to Spotify!")
            return
        
        # Create embed
        embed = discord.Embed(color=0x495678)  # Dark embed color
        
        embed.set_author(
            name=f"{user.display_name}'s Spotify",
            icon_url=user.display_avatar.url
        )
        
        # Create clickable song title
        if spotify_activity.track_id:
            track_url = f"https://open.spotify.com/track/{spotify_activity.track_id}"
            song_title = f"[{spotify_activity.title}]({track_url})"
        else:
            song_title = spotify_activity.title
        
        # Song info as description
        embed.description = f"{song_title}\nby {spotify_activity.artist}"
        
        embed.set_thumbnail(url=spotify_activity.album_cover_url)
        
        await ctx.send(embed=embed)

    @commands.command(name="hug")
    async def hug(self, ctx, user: Union[discord.Member, discord.User] = None):
        """Hug someone!"""
        if user is None:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Please mention someone to hug!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        if user.id == ctx.author.id:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> You can't hug yourself!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        gif_url = await self.get_gif("hug")
        
        if gif_url:
            embed = discord.Embed(
                description=f"**{ctx.author.mention}** hugged **{user.mention}**!",
                color=discord.Color.from_str("#a6afe7")
            )
            embed.set_image(url=gif_url)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Failed to fetch GIF from API!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="kiss")
    async def kiss(self, ctx, user: Union[discord.Member, discord.User] = None):
        """Kiss someone"""
        if user is None:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Please mention someone to kiss!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        if user.id == ctx.author.id:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> You can't kiss yourself!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        gif_url = await self.get_gif("kiss")
        
        if gif_url:
            embed = discord.Embed(
                description=f"**{ctx.author.mention}** kissed **{user.mention}**!",
                color=discord.Color.from_str("#a6afe7")
            )
            embed.set_image(url=gif_url)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Failed to fetch GIF from API!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="fuck")
    async def fuck(self, ctx, user: Union[discord.Member, discord.User] = None):
        """Fuck someone."""
        # Check if channel is NSFW
        if not ctx.channel.nsfw:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> This command can only be used in NSFW channels!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        if user is None:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Please mention someone!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        if user.id == ctx.author.id:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> You can't do that to yourself!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        # nekos.best uses "fuck" endpoint
        gif_url = await self.get_gif("fuck")
        
        if gif_url:
            embed = discord.Embed(
                description=f"**{ctx.author.mention}** fucked **{user.mention}**!",
                color=discord.Color.from_str("#a6afe7")
            )
            embed.set_image(url=gif_url)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Failed to fetch GIF from API!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="pat")
    async def pat(self, ctx, user: Union[discord.Member, discord.User] = None):
        """Pat someone!"""
        if user is None:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Please mention someone to pat!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        if user.id == ctx.author.id:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> You can't pat yourself!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        gif_url = await self.get_gif("pat")
        
        if gif_url:
            embed = discord.Embed(
                description=f"**{ctx.author.mention}** patted **{user.mention}**!",
                color=discord.Color.from_str("#a6afe7")
            )
            embed.set_image(url=gif_url)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Failed to fetch GIF from API!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="laugh")
    async def laugh(self, ctx):
        """Laugh!"""
        gif_url = await self.get_gif("laugh")
        
        if gif_url:
            embed = discord.Embed(
                description=f"**{ctx.author.mention}** is laughing!",
                color=discord.Color.from_str("#a6afe7")
            )
            embed.set_image(url=gif_url)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Failed to fetch GIF from API!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="happy")
    async def happy(self, ctx):
        """Show happiness!"""
        gif_url = await self.get_gif("happy")
        
        if gif_url:
            embed = discord.Embed(
                description=f"**{ctx.author.mention}** is happy!",
                color=discord.Color.from_str("#a6afe7")
            )
            embed.set_image(url=gif_url)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Failed to fetch GIF from API!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)

    @commands.command(name="slap")
    async def slap(self, ctx, user: Union[discord.Member, discord.User] = None):
        """Slap someone!"""
        if user is None:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Please mention someone to slap!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        if user.id == ctx.author.id:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> You can't slap yourself!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        gif_url = await self.get_gif("slap")
        
        if gif_url:
            embed = discord.Embed(
                description=f"**{ctx.author.mention}** slapped **{user.mention}**!",
                color=discord.Color.from_str("#a6afe7")
            )
            embed.set_image(url=gif_url)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Failed to fetch GIF from API!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="punch")
    async def punch(self, ctx, user: Union[discord.Member, discord.User] = None):
        """Punch someone!"""
        if user is None:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Please mention someone to punch!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        if user.id == ctx.author.id:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> You can't punch yourself!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        gif_url = await self.get_gif("punch")
        
        if gif_url:
            embed = discord.Embed(
                description=f"**{ctx.author.mention}** punched **{user.mention}**!",
                color=discord.Color.from_str("#a6afe7")
            )
            embed.set_image(url=gif_url)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Failed to fetch GIF from API!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="poke")
    async def poke(self, ctx, user: Union[discord.Member, discord.User] = None):
        """Poke someone!"""
        if user is None:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Please mention someone to poke!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        if user.id == ctx.author.id:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> You can't poke yourself!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        gif_url = await self.get_gif("poke")
        
        if gif_url:
            embed = discord.Embed(
                description=f"**{ctx.author.mention}** poked **{user.mention}**!",
                color=discord.Color.from_str("#a6afe7")
            )
            embed.set_image(url=gif_url)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Failed to fetch GIF from API!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="tickle")
    async def tickle(self, ctx, user: Union[discord.Member, discord.User] = None):
        """Tickle someone!"""
        if user is None:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Please mention someone to tickle!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        if user.id == ctx.author.id:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> You can't tickle yourself!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        gif_url = await self.get_gif("tickle")
        
        if gif_url:
            embed = discord.Embed(
                description=f"**{ctx.author.mention}** tickled **{user.mention}**!",
                color=discord.Color.from_str("#a6afe7")
            )
            embed.set_image(url=gif_url)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Failed to fetch GIF from API!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="bite")
    async def bite(self, ctx, user: Union[discord.Member, discord.User] = None):
        """Bite someone!"""
        if user is None:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Please mention someone to bite!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        if user.id == ctx.author.id:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> You can't bite yourself!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        gif_url = await self.get_gif("bite")
        
        if gif_url:
            embed = discord.Embed(
                description=f"**{ctx.author.mention}** bit **{user.mention}**!",
                color=discord.Color.from_str("#a6afe7")
            )
            embed.set_image(url=gif_url)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Failed to fetch GIF from API!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="cuddle")
    async def cuddle(self, ctx, user: Union[discord.Member, discord.User] = None):
        """Cuddle someone!"""
        if user is None:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Please mention someone to cuddle!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        if user.id == ctx.author.id:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> You can't cuddle yourself!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        gif_url = await self.get_gif("cuddle")
        
        if gif_url:
            embed = discord.Embed(
                description=f"**{ctx.author.mention}** cuddled **{user.mention}**!",
                color=discord.Color.from_str("#a6afe7")
            )
            embed.set_image(url=gif_url)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Failed to fetch GIF from API!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="feed")
    async def feed(self, ctx, user: Union[discord.Member, discord.User] = None):
        """Feed someone!"""
        if user is None:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Please mention someone to feed!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        if user.id == ctx.author.id:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> You can't feed yourself!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        gif_url = await self.get_gif("feed")
        
        if gif_url:
            embed = discord.Embed(
                description=f"**{ctx.author.mention}** fed **{user.mention}**!",
                color=discord.Color.from_str("#a6afe7")
            )
            embed.set_image(url=gif_url)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Failed to fetch GIF from API!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="wave")
    async def wave(self, ctx, user: Union[discord.Member, discord.User] = None):
        """Wave at someone!"""
        if user is None:
            gif_url = await self.get_gif("wave")
            
            if gif_url:
                embed = discord.Embed(
                    description=f"**{ctx.author.mention}** is waving!",
                    color=discord.Color.from_str("#a6afe7")
                )
                embed.set_image(url=gif_url)
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(
                    description="<:deny:1429468818094424075> Failed to fetch GIF from API!",
                    color=discord.Color.from_str("#a6afe7")
                )
                await ctx.send(embed=embed)
            return
        
        if user.id == ctx.author.id:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> You can't wave at yourself!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        gif_url = await self.get_gif("wave")
        
        if gif_url:
            embed = discord.Embed(
                description=f"**{ctx.author.mention}** waved at **{user.mention}**!",
                color=discord.Color.from_str("#a6afe7")
            )
            embed.set_image(url=gif_url)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Failed to fetch GIF from API!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="cry")
    async def cry(self, ctx):
        """Cry!"""
        gif_url = await self.get_gif("cry")
        
        if gif_url:
            embed = discord.Embed(
                description=f"**{ctx.author.mention}** is crying!",
                color=discord.Color.from_str("#a6afe7")
            )
            embed.set_image(url=gif_url)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Failed to fetch GIF from API!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="dance")
    async def dance(self, ctx):
        """Dance!"""
        gif_url = await self.get_gif("dance")
        
        if gif_url:
            embed = discord.Embed(
                description=f"**{ctx.author.mention}** is dancing!",
                color=discord.Color.from_str("#a6afe7")
            )
            embed.set_image(url=gif_url)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Failed to fetch GIF from API!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="sleep")
    async def sleep(self, ctx):
        """Go to sleep!"""
        gif_url = await self.get_gif("sleep")
        
        if gif_url:
            embed = discord.Embed(
                description=f"**{ctx.author.mention}** is sleeping! 😴",
                color=discord.Color.from_str("#a6afe7")
            )
            embed.set_image(url=gif_url)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Failed to fetch GIF from API!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="blush")
    async def blush(self, ctx):
        """Blush!"""
        gif_url = await self.get_gif("blush")
        
        if gif_url:
            embed = discord.Embed(
                description=f"**{ctx.author.mention}** is blushing!",
                color=discord.Color.from_str("#a6afe7")
            )
            embed.set_image(url=gif_url)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Failed to fetch GIF from API!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="smug")
    async def smug(self, ctx):
        """Look smug!"""
        gif_url = await self.get_gif("smug")
        
        if gif_url:
            embed = discord.Embed(
                description=f"**{ctx.author.mention}** looks smug!",
                color=discord.Color.from_str("#a6afe7")
            )
            embed.set_image(url=gif_url)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Failed to fetch GIF from API!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="wink")
    async def wink(self, ctx, user: Union[discord.Member, discord.User] = None):
        """Wink at someone!"""
        gif_url = await self.get_gif("wink")
        
        if user is None:
            if gif_url:
                embed = discord.Embed(
                    description=f"**{ctx.author.mention}** winked!",
                    color=discord.Color.from_str("#a6afe7")
                )
                embed.set_image(url=gif_url)
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(
                    description="<:deny:1429468818094424075> Failed to fetch GIF from API!",
                    color=discord.Color.from_str("#a6afe7")
                )
                await ctx.send(embed=embed)
            return
        
        if user.id == ctx.author.id:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> You can't wink at yourself!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        if gif_url:
            embed = discord.Embed(
                description=f"**{ctx.author.mention}** winked at **{user.mention}**!",
                color=discord.Color.from_str("#a6afe7")
            )
            embed.set_image(url=gif_url)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Failed to fetch GIF from API!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="bored")
    async def bored(self, ctx):
        """Show that you're bored!"""
        gif_url = await self.get_gif("bored")
        
        if gif_url:
            embed = discord.Embed(
                description=f"**{ctx.author.mention}** is bored!",
                color=discord.Color.from_str("#a6afe7")
            )
            embed.set_image(url=gif_url)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Failed to fetch GIF from API!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="yawn")
    async def yawn(self, ctx):
        """Yawn!"""
        gif_url = await self.get_gif("yawn")
        
        if gif_url:
            embed = discord.Embed(
                description=f"**{ctx.author.mention}** is yawning!",
                color=discord.Color.from_str("#a6afe7")
            )
            embed.set_image(url=gif_url)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Failed to fetch GIF from API!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="nod")
    async def nod(self, ctx):
        """Nod!"""
        gif_url = await self.get_gif("nod")
        
        if gif_url:
            embed = discord.Embed(
                description=f"**{ctx.author.mention}** nodded!",
                color=discord.Color.from_str("#a6afe7")
            )
            embed.set_image(url=gif_url)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Failed to fetch GIF from API!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="nope")
    async def nope(self, ctx):
        """Nope!"""
        gif_url = await self.get_gif("nope")
        
        if gif_url:
            embed = discord.Embed(
                description=f"**{ctx.author.mention}** said nope!",
                color=discord.Color.from_str("#a6afe7")
            )
            embed.set_image(url=gif_url)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Failed to fetch GIF from API!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="stare")
    async def stare(self, ctx, user: Union[discord.Member, discord.User] = None):
        """Stare at someone!"""
        if user is None:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Please mention someone to stare at!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        if user.id == ctx.author.id:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> You can't stare at yourself!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        gif_url = await self.get_gif("stare")
        
        if gif_url:
            embed = discord.Embed(
                description=f"**{ctx.author.mention}** is staring at **{user.mention}**!",
                color=discord.Color.from_str("#a6afe7")
            )
            embed.set_image(url=gif_url)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Failed to fetch GIF from API!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="handhold")
    async def handhold(self, ctx, user: Union[discord.Member, discord.User] = None):
        """Hold hands with someone!"""
        if user is None:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Please mention someone to hold hands with!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        if user.id == ctx.author.id:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> You can't hold hands with yourself!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        gif_url = await self.get_gif("handhold")
        
        if gif_url:
            embed = discord.Embed(
                description=f"**{ctx.author.mention}** is holding hands with **{user.mention}**!",
                color=discord.Color.from_str("#a6afe7")
            )
            embed.set_image(url=gif_url)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Failed to fetch GIF from API!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="highfive")
    async def highfive(self, ctx, user: Union[discord.Member, discord.User] = None):
        """High five someone!"""
        if user is None:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Please mention someone to high five!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        if user.id == ctx.author.id:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> You can't high five yourself!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        gif_url = await self.get_gif("highfive")
        
        if gif_url:
            embed = discord.Embed(
                description=f"**{ctx.author.mention}** high fived **{user.mention}**!",
                color=discord.Color.from_str("#a6afe7")
            )
            embed.set_image(url=gif_url)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Failed to fetch GIF from API!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="nom")
    async def nom(self, ctx):
        """Nom nom nom!"""
        gif_url = await self.get_gif("nom")
        
        if gif_url:
            embed = discord.Embed(
                description=f"**{ctx.author.mention}** is eating! Nom nom!",
                color=discord.Color.from_str("#a6afe7")
            )
            embed.set_image(url=gif_url)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Failed to fetch GIF from API!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="pout")
    async def pout(self, ctx):
        """Pout!"""
        gif_url = await self.get_gif("pout")
        
        if gif_url:
            embed = discord.Embed(
                description=f"**{ctx.author.mention}** is pouting!",
                color=discord.Color.from_str("#a6afe7")
            )
            embed.set_image(url=gif_url)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Failed to fetch GIF from API!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="shrug")
    async def shrug(self, ctx):
        """Shrug!"""
        gif_url = await self.get_gif("shrug")
        
        if gif_url:
            embed = discord.Embed(
                description=f"**{ctx.author.mention}** shrugged!",
                color=discord.Color.from_str("#a6afe7")
            )
            embed.set_image(url=gif_url)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Failed to fetch GIF from API!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="thumbsup")
    async def thumbsup(self, ctx):
        """Give a thumbs up!"""
        gif_url = await self.get_gif("thumbsup")
        
        if gif_url:
            embed = discord.Embed(
                description=f"**{ctx.author.mention}** gave a thumbs up!",
                color=discord.Color.from_str("#a6afe7")
            )
            embed.set_image(url=gif_url)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Failed to fetch GIF from API!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)

    @commands.command(name="8ball", aliases=["eightball"])
    async def eightball(self, ctx, *, question: str = None):
        """Ask the magic 8ball a question"""
        if question is None:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Please ask a question!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        response = random.choice(self.eightball_responses)
        
        embed = discord.Embed(
            title="🎱 Magic 8Ball",
            description=f"**Question:** {question}\n**Answer:** {response}",
            color=discord.Color.from_str("#a6afe7")
        )
        embed.set_footer(text=f"Asked by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)
    
    @commands.command(name="choose", aliases=["choice", "pick"])
    async def choose(self, ctx, *choices):
        """Choose between multiple options (separate with spaces or use quotes for multi-word options)"""
        if len(choices) < 2:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Please provide at least 2 options to choose from!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        choice = random.choice(choices)
        
        embed = discord.Embed(
            title="🤔 I choose...",
            description=f"**{choice}**",
            color=discord.Color.from_str("#a6afe7")
        )
        embed.set_footer(text=f"Chosen from {len(choices)} options")
        await ctx.send(embed=embed)
    
    @commands.command(name="rate")
    async def rate(self, ctx, *, thing: str = None):
        """Rate something from 0 to 10"""
        if thing is None:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Please provide something to rate!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        rating = random.randint(0, 10)
        
        # Generate star display
        filled_stars = "⭐" * rating
        empty_stars = "☆" * (10 - rating)
        stars = filled_stars + empty_stars
        
        embed = discord.Embed(
            title="⭐ Rating",
            description=f"I'd rate **{thing}** a **{rating}/10**!\n{stars}",
            color=discord.Color.from_str("#a6afe7")
        )
        await ctx.send(embed=embed)
    
    @commands.command(name="gayrate", aliases=["gay"])
    async def gayrate(self, ctx, user: Union[discord.Member, discord.User] = None):
        """Check how gay someone is (just for fun!)"""
        target = user or ctx.author
        
        # Completely random rating
        percentage = random.randint(0, 100)
        
        # Progress bar
        filled = "█" * (percentage // 10)
        empty = "░" * (10 - (percentage // 10))
        bar = filled + empty
        
        embed = discord.Embed(
            title="🏳️‍🌈 Gay Rate",
            description=f"{target.mention} is **{percentage}%** gay!\n`{bar}` {percentage}%",
            color=discord.Color.from_str("#a6afe7")
        )
        await ctx.send(embed=embed)
    
    @commands.command(name="simprate", aliases=["simp"])
    async def simprate(self, ctx, user: Union[discord.Member, discord.User] = None):
        """Check how much of a simp someone is"""
        target = user or ctx.author
        
        # Completely random rating
        percentage = random.randint(0, 100)
        
        # Progress bar
        filled = "█" * (percentage // 10)
        empty = "░" * (10 - (percentage // 10))
        bar = filled + empty
        
        embed = discord.Embed(
            title="💝 Simp Rate",
            description=f"{target.mention} is **{percentage}%** simp!\n`{bar}` {percentage}%",
            color=discord.Color.from_str("#a6afe7")
        )
        await ctx.send(embed=embed)
    
    @commands.command(name="ship")
    async def ship(self, ctx, user1: Union[discord.Member, discord.User], user2: Union[discord.Member, discord.User] = None):
        """Ship two people together and see their compatibility"""
        if user2 is None:
            user2 = ctx.author
        
        # Completely random compatibility
        compatibility = random.randint(0, 100)
        
        # Progress bar
        filled = "❤️" * (compatibility // 10)
        empty = "🖤" * (10 - (compatibility // 10))
        bar = filled + empty
        
        # Compatibility message
        if compatibility >= 90:
            message = "Perfect match! 💕"
        elif compatibility >= 70:
            message = "Great compatibility! 💖"
        elif compatibility >= 50:
            message = "Not bad! 💗"
        elif compatibility >= 30:
            message = "Could work... 💔"
        else:
            message = "Yikes... 💔"
        
        # Ship name (first half of user1 + second half of user2)
        name1 = user1.display_name
        name2 = user2.display_name
        ship_name = name1[:len(name1)//2] + name2[len(name2)//2:]
        
        embed = discord.Embed(
            title=f"💘 {ship_name}",
            description=f"{user1.mention} 💕 {user2.mention}\n\n**Compatibility:** {compatibility}%\n{bar}\n\n{message}",
            color=discord.Color.from_str("#a6afe7")
        )
        await ctx.send(embed=embed)
    
    @commands.command(name="pp", aliases=["ppsize"])
    async def pp(self, ctx, user: Union[discord.Member, discord.User] = None):
        """Check pp size (just for fun!)"""
        target = user or ctx.author
        
        # Completely random size
        size = random.randint(0, 15)
        
        pp = "8" + "=" * size + "D"
        
        embed = discord.Embed(
            title="🍆 PP Size",
            description=f"{target.mention}'s pp:\n`{pp}`\n**Size:** {size} inches",
            color=discord.Color.from_str("#a6afe7")
        )
        await ctx.send(embed=embed)
    
    @commands.command(name="reverse")
    async def reverse(self, ctx, *, text: str = None):
        """Reverse text"""
        if text is None:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Please provide text to reverse!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        reversed_text = text[::-1]
        
        embed = discord.Embed(
            title="🔄 Reversed Text",
            description=reversed_text,
            color=discord.Color.from_str("#a6afe7")
        )
        await ctx.send(embed=embed)
    
    @commands.command(name="emojify")
    async def emojify(self, ctx, *, text: str = None):
        """Convert text to emoji letters"""
        if text is None:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Please provide text to emojify!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        emoji_map = {
            'a': '🇦', 'b': '🇧', 'c': '🇨', 'd': '🇩', 'e': '🇪',
            'f': '🇫', 'g': '🇬', 'h': '🇭', 'i': '🇮', 'j': '🇯',
            'k': '🇰', 'l': '🇱', 'm': '🇲', 'n': '🇳', 'o': '🇴',
            'p': '🇵', 'q': '🇶', 'r': '🇷', 's': '🇸', 't': '🇹',
            'u': '🇺', 'v': '🇻', 'w': '🇼', 'x': '🇽', 'y': '🇾',
            'z': '🇿', ' ': '   '
        }
        
        emojified = ''.join(emoji_map.get(char.lower(), char) for char in text)
        
        if len(emojified) > 2000:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Text is too long to emojify!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        await ctx.send(emojified)
    
    @commands.command(name="roast")
    async def roast(self, ctx, user: Union[discord.Member, discord.User] = None):
        """Roast someone (or yourself)"""
        target = user or ctx.author
        
        roasts = [
            "I'd agree with you but then we'd both be wrong.",
            "You're not stupid; you just have bad luck thinking.",
            "If laughter is the best medicine, your face must be curing the world.",
            "I'm not saying you're dumb, I'm just saying you've got bad luck when it comes to thinking.",
            "You bring everyone so much joy... when you leave the room.",
            "I'd explain it to you, but I don't have any crayons with me.",
            "You're like a cloud. When you disappear, it's a beautiful day.",
            "I'd give you a nasty look, but you've already got one.",
            "You're proof that evolution CAN go in reverse.",
            "I'm not insulting you, I'm describing you.",
        ]
        
        roast = random.choice(roasts)
        
        embed = discord.Embed(
            title="🔥 Roasted!",
            description=f"{target.mention}, {roast}",
            color=discord.Color.from_str("#a6afe7")
        )
        await ctx.send(embed=embed)
    
    @commands.command(name="compliment")
    async def compliment(self, ctx, user: Union[discord.Member, discord.User] = None):
        """Give someone a compliment"""
        target = user or ctx.author
        
        compliments = [
            "You're an awesome friend!",
            "You light up the room!",
            "You're a smart cookie!",
            "You've got an awesome sense of humor!",
            "You're really something special!",
            "You're a great listener!",
            "You're so thoughtful!",
            "You have the best laugh!",
            "You're incredibly talented!",
            "You're one of a kind!",
            "You're really inspiring!",
            "You make everyone around you happier!",
        ]
        
        compliment = random.choice(compliments)
        
        embed = discord.Embed(
            title="💖 Compliment",
            description=f"{target.mention}, {compliment}",
            color=discord.Color.from_str("#a6afe7")
        )
        await ctx.send(embed=embed)

    # Error handlers for new commands
    @slap.error
    @punch.error
    @poke.error
    @tickle.error
    @bite.error
    @cuddle.error
    @feed.error
    @wave.error
    @wink.error
    @stare.error
    @handhold.error
    @highfive.error
    async def interaction_error(self, ctx, error):
        if isinstance(error, commands.MemberNotFound):
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Member not found!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.UserNotFound):
            embed = discord.Embed(
                description="<:deny:1429468818094424075> User not found!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)

    @commands.command(name='roblox', help='Shows a Roblox user profile by username or user ID')
    async def roblox(self, ctx, *, user_input: str):
        async with ctx.typing():
            try:
                async with aiohttp.ClientSession() as session:
                    user_id = None
                    
                    # Check if input is a user ID (numeric)
                    if user_input.isdigit():
                        user_id = int(user_input)
                    else:
                        # Try using the username directly via POST request
                        usernames_url = "https://users.roblox.com/v1/usernames/users"
                        payload = {
                            "usernames": [user_input],
                            "excludeBannedUsers": False
                        }
                        headers = {
                            "Content-Type": "application/json"
                        }
                        
                        async with session.post(usernames_url, json=payload, headers=headers) as response:
                            if response.status != 200:
                                return await ctx.send(embed=discord.Embed(
                                    description="❌ Failed to fetch Roblox data!",
                                    color=discord.Color.from_str("#a6afe7")
                                ))
                            
                            data = await response.json()
                            
                            if not data.get('data') or len(data['data']) == 0:
                                return await ctx.send(embed=discord.Embed(
                                    description=f"❌ Roblox user `{user_input}` not found!",
                                    color=discord.Color.from_str("#a6afe7")
                                ))
                            
                            user_id = data['data'][0]['id']
                    
                    # Now fetch user info using the user ID
                    user_url = f"https://users.roblox.com/v1/users/{user_id}"
                    async with session.get(user_url) as response:
                        if response.status != 200:
                            return await ctx.send(embed=discord.Embed(
                                description=f"❌ Roblox user with ID `{user_id}` not found!",
                                color=discord.Color.from_str("#a6afe7")
                            ))
                        
                        user_data = await response.json()
                        username = user_data.get('name')
                        display_name = user_data.get('displayName')
                        description = user_data.get('description', 'No description')
                        created = user_data.get('created', 'Unknown')
                        is_banned = user_data.get('isBanned', False)
                    
                    # Get avatar thumbnail
                    thumbnail_url = f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={user_id}&size=150x150&format=Png"
                    async with session.get(thumbnail_url) as response:
                        thumbnail_data = await response.json()
                        avatar_url = thumbnail_data['data'][0]['imageUrl'] if thumbnail_data.get('data') else None
                    
                    # Get friends count
                    friends_url = f"https://friends.roblox.com/v1/users/{user_id}/friends/count"
                    async with session.get(friends_url) as response:
                        friends_data = await response.json()
                        friends_count = friends_data.get('count', 0)
                    
                    # Get followers count
                    followers_url = f"https://friends.roblox.com/v1/users/{user_id}/followers/count"
                    async with session.get(followers_url) as response:
                        followers_data = await response.json()
                        followers_count = followers_data.get('count', 0)
                    
                    # Get following count
                    following_url = f"https://friends.roblox.com/v1/users/{user_id}/followings/count"
                    async with session.get(following_url) as response:
                        following_data = await response.json()
                        following_count = following_data.get('count', 0)
                
                # Create embed with profile link
                embed = discord.Embed(
                    title=f"{display_name} (@{username})",
                    description=description[:256] if description else "No description",
                    color=discord.Color.from_str("#a6afe7"),
                    url=f"https://www.roblox.com/users/{user_id}/profile"
                )
                
                if avatar_url:
                    embed.set_thumbnail(url=avatar_url)
                
                embed.add_field(name="User ID", value=f"{user_id}", inline=True)
                embed.add_field(name="Created", value=f"<t:{int(datetime.datetime.fromisoformat(created.replace('Z', '+00:00')).timestamp())}:D>", inline=True)
                embed.add_field(name="Connections", value=f"{friends_count:,}", inline=True)
                embed.add_field(name="Followers", value=f"{followers_count:,}", inline=True)
                embed.add_field(name="Following", value=f"{following_count:,}", inline=True)
                
                embed.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.display_avatar.url)
                
                await ctx.send(embed=embed)
                
            except Exception as e:
                await ctx.send(embed=discord.Embed(
                    description=f"❌ An error occurred: {str(e)}",
                    color=discord.Color.from_str("#a6afe7")
                ))

    @commands.command(name='tiktok', aliases=["tt"])
    async def tiktok_profile(self, ctx, url: str):
        """Show TikTok info from a profile"""
        
        # Ensure URL is properly formatted
        if not url.startswith('http'):
            url = f'https://www.tiktok.com/@{url.lstrip("@")}'
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=10) as response:
                    if response.status != 200:
                        await ctx.send(f"Failed to fetch profile (Status: {response.status})")
                        return
                    
                    html = await response.text()
                    
                    # Extract JSON data from HTML
                    match = re.search(r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">(.*?)</script>', html, re.DOTALL)
                    
                    if not match:
                        await ctx.send("Could not find profile data in page")
                        return
                    
                    data = json.loads(match.group(1))
                    user_info = data.get('__DEFAULT_SCOPE__', {}).get('webapp.user-detail', {}).get('userInfo', {})
                    if not user_info:
                        await ctx.send("Profile not found or is private")
                        return
                    
                    user = user_info.get('user', {})
                    stats = user_info.get('stats', {})
                    
                    embed = discord.Embed(
                        title=f"@{user.get('uniqueId', 'Unknown')}",
                        description=user.get('signature', 'No bio'),
                        color=0xa6afe7
                    )
                    
                    # Set profile picture as thumbnail
                    avatar_url = user.get('avatarLarger') or user.get('avatarMedium') or user.get('avatarThumb')
                    if avatar_url:
                        embed.set_thumbnail(url=avatar_url)
                    
                    embed.add_field(name="Followers", value=f"{stats.get('followerCount', 0):,}")
                    embed.add_field(name="Following", value=f"{stats.get('followingCount', 0):,}")
                    embed.add_field(name="Likes", value=f"{stats.get('heartCount', 0):,}")
                    
                    await ctx.send(embed=embed)
                        
        except json.JSONDecodeError:
            await ctx.send("Failed to parse profile data")
        except Exception as e:
            await ctx.send(f"Error: {str(e)}")
            
    @commands.command(name='tictactoe', aliases=['ttt'])
    async def tictactoe(self, ctx, opponent: discord.Member):
        # Prevent playing against bots
        if opponent.bot:
            await ctx.send('You cannot play against bots!')
            return
        
        # Prevent playing against yourself
        if opponent.id == ctx.author.id:
            await ctx.send('You cannot play against yourself!')
            return

        # Create the game
        view = TicTacToeView(ctx.author, opponent, self.color)
        
        embed = discord.Embed(
            title='🎮 Tic Tac Toe',
            description=f'{ctx.author.mention} (🔵 X) vs {opponent.mention} (🔴 O)\n\n**Current Turn:** {ctx.author.mention} (X)',
            color=self.color
        )
        
        await ctx.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(Fun(bot))