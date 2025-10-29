import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import sqlite3
from typing import Union, Optional

class LastFM(commands.Cog):
    """Last.fm music tracking commands"""
    
    def __init__(self, bot):
        self.bot = bot
        self.api_key = "6abec07ee15561daaed04bf6bc1afa55"  # Get one from https://www.last.fm/api/account/create
        self.api_url = "http://ws.audioscrobbler.com/2.0/"
        self.db_path = "data/lastfm.db"
        self.init_db()
    
    def init_db(self):
        """Initialize the SQLite database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                discord_id INTEGER PRIMARY KEY,
                lastfm_username TEXT NOT NULL
            )
        ''')
        conn.commit()
        conn.close()
    
    def get_lastfm_user(self, discord_id):
        """Get Last.fm username from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT lastfm_username FROM users WHERE discord_id = ?', (discord_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    
    def set_lastfm_user(self, discord_id, lastfm_username):
        """Set Last.fm username in database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO users (discord_id, lastfm_username)
            VALUES (?, ?)
        ''', (discord_id, lastfm_username))
        conn.commit()
        conn.close()
    
    def get_command_permissions(self, command):
        """Extract permissions from command checks"""
        permissions = []
        if hasattr(command, 'checks') and command.checks:
            for check in command.checks:
                check_str = str(check)
                if 'has_permissions' in check_str:
                    if hasattr(check, '__closure__') and check.__closure__:
                        for cell in check.__closure__:
                            if hasattr(cell.cell_contents, 'items'):
                                for key, value in cell.cell_contents.items():
                                    if value:
                                        permissions.append(key.replace('_', ' ').title())
                elif 'is_owner' in check_str:
                    permissions.append("Bot Owner")
        return ", ".join(permissions) if permissions else "None"
    
    def create_command_help_embed(self, ctx, command):
        """Create help embed for a command"""
        cog_name = command.cog.qualified_name if command.cog else "No category"
        
        embed = discord.Embed(
            title=f"Command: {command.name} • {cog_name}",
            description=command.help or "No description provided",
            color=discord.Color.from_str("#495678")
        )
        
        # Add syntax and example
        syntax = f"Syntax: {ctx.prefix}{command.name}"
        if command.signature:
            syntax += f" {command.signature}"
        
        example = f"Example: {ctx.prefix}{command.name}"
        
        embed.add_field(
            name="",
            value=f"```js\n{syntax}\n{example}\n```",
            inline=False
        )
        
        # Add permissions
        permissions = self.get_command_permissions(command)
        embed.add_field(
            name="Permissions",
            value=permissions,
            inline=False
        )
        
        # Add aliases
        aliases_text = "none" if not command.aliases else ", ".join(command.aliases)
        embed.set_footer(
            text=f"Aliases: {aliases_text}",
            icon_url=self.bot.user.display_avatar.url if self.bot.user else None
        )
        
        return embed
    
    async def fetch_lastfm(self, method, params):
        """Fetch data from Last.fm API"""
        params.update({
            'method': method,
            'api_key': self.api_key,
            'format': 'json'
        })
        
        async with aiohttp.ClientSession() as session:
            async with session.get(self.api_url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                return None
    
    async def create_nowplaying_embed(self, target_user, lastfm_username):
        """Create the now playing embed (shared logic)"""
        # Fetch recent tracks
        data = await self.fetch_lastfm('user.getrecenttracks', {
            'user': lastfm_username,
            'limit': 1
        })
        
        if not data or 'recenttracks' not in data:
            return discord.Embed(
                description="❌ Failed to fetch Last.fm data!",
                color=discord.Color.from_str("#495678")
            )
        
        tracks = data['recenttracks'].get('track', [])
        if not tracks:
            return discord.Embed(
                description=f"❌ **{lastfm_username}** hasn't listened to anything recently!",
                color=discord.Color.from_str("#495678")
            )
        
        # Get the most recent track
        track = tracks[0] if isinstance(tracks, list) else tracks
        
        # Check if currently playing
        is_now_playing = '@attr' in track and track['@attr'].get('nowplaying') == 'true'
        
        artist = track['artist']['#text'] if isinstance(track['artist'], dict) else track['artist']
        song = track['name']
        album = track['album']['#text'] if 'album' in track else 'Unknown Album'
        
        # Get album art
        images = track.get('image', [])
        image_url = None
        for img in images:
            if img['size'] == 'extralarge' and img['#text']:
                image_url = img['#text']
                break
        
        # Fetch user info for scrobble count
        user_data = await self.fetch_lastfm('user.getinfo', {'user': lastfm_username})
        scrobbles = user_data.get('user', {}).get('playcount', 'Unknown') if user_data else 'Unknown'
        
        # Get track and artist URLs
        track_url = track.get('url', f"https://www.last.fm/music/{artist.replace(' ', '+')}/_/{song.replace(' ', '+')}")
        artist_url = f"https://www.last.fm/music/{artist.replace(' ', '+')}"
        
        # Get album URL
        album_encoded = album.replace(' ', '+')
        artist_encoded = artist.replace(' ', '+')
        album_url = f"https://www.last.fm/music/{artist_encoded}/{album_encoded}"
        
        # Format the description with track and album
        description = (
            f"**Track:** [`{song}`]({track_url}) - [`{artist}`]({artist_url})\n"
            f"**Album:** [`{album}`]({album_url})"
        )
        
        # Create embed
        embed = discord.Embed(
            description=description,
            color=discord.Color.from_str("#495678")
        )
        
        embed.set_author(
            name=lastfm_username,
            icon_url=target_user.display_avatar.url
        )
        
        # Set thumbnail
        if image_url:
            embed.set_thumbnail(url=image_url)
        
        return embed
    
    @commands.command(name="fm", aliases=["np", "nowplaying"])
    async def nowplaying(self, ctx, user: Union[discord.Member, discord.User] = None):
        """Show what you or another user is currently listening to on Last.fm"""
        
        target_user = user or ctx.author
        lastfm_username = self.get_lastfm_user(target_user.id)
        
        if not lastfm_username:
            if target_user == ctx.author:
                embed = discord.Embed(
                    description=f"❌ You haven't set your Last.fm username! Use `{ctx.prefix}fmset <username>`",
                    color=discord.Color.from_str("#495678")
                )
            else:
                embed = discord.Embed(
                    description=f"❌ **{target_user.name}** hasn't set their Last.fm username!",
                    color=discord.Color.from_str("#495678")
                )
            return await ctx.send(embed=embed)
        
        embed = await self.create_nowplaying_embed(target_user, lastfm_username)
        await ctx.send(embed=embed)
    
    @app_commands.command(name="fm", description="Show what you or another user is currently listening to on Last.fm")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def fm_slash(self, interaction: discord.Interaction, user: Optional[discord.User] = None):
        """Show what you or another user is currently listening to on Last.fm (slash command)"""
        
        target_user = user or interaction.user
        lastfm_username = self.get_lastfm_user(target_user.id)
        
        if not lastfm_username:
            if target_user == interaction.user:
                embed = discord.Embed(
                    description="❌ You haven't set your Last.fm username! Use `/fmset <username>`",
                    color=discord.Color.from_str("#495678")
                )
            else:
                embed = discord.Embed(
                    description=f"❌ **{target_user.name}** hasn't set their Last.fm username!",
                    color=discord.Color.from_str("#495678")
                )
            return await interaction.response.send_message(embed=embed)
        
        embed = await self.create_nowplaying_embed(target_user, lastfm_username)
        await interaction.response.send_message(embed=embed)
    
    @commands.command(name="fmset", aliases=["setfm", "fmlogin"])
    async def set_lastfm(self, ctx, username: str = None):
        """Set your Last.fm username"""
        
        if username is None:
            embed = self.create_command_help_embed(ctx, ctx.command)
            return await ctx.send(embed=embed)
        
        # Verify the username exists
        data = await self.fetch_lastfm('user.getinfo', {'user': username})
        
        if not data or 'error' in data:
            embed = discord.Embed(
                description=f"❌ Last.fm user **{username}** not found!",
                color=discord.Color.from_str("#495678")
            )
            return await ctx.send(embed=embed)
        
        # Save to database
        self.set_lastfm_user(ctx.author.id, username)
        
        embed = discord.Embed(
            description=f"✅ Your Last.fm username has been set to **{username}**",
            color=discord.Color.from_str("#495678")
        )
        await ctx.send(embed=embed)
    
    @commands.command(name="fmremove", aliases=["removefm", "unfm"])
    async def remove_lastfm(self, ctx):
        """Remove your Last.fm username"""
        
        lastfm_username = self.get_lastfm_user(ctx.author.id)
        
        if not lastfm_username:
            embed = discord.Embed(
                description="❌ You don't have a Last.fm username set!",
                color=discord.Color.from_str("#495678")
            )
            return await ctx.send(embed=embed)
        
        # Remove from database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM users WHERE discord_id = ?', (ctx.author.id,))
        conn.commit()
        conn.close()
        
        embed = discord.Embed(
            description="✅ Your Last.fm username has been removed",
            color=discord.Color.from_str("#495678")
        )
        await ctx.send(embed=embed)
    
    @commands.command(name="fmtop", aliases=["toptracks", "fmtracks"])
    async def top_tracks(self, ctx, user: Union[discord.Member, discord.User] = None, period: str = "overall"):
        """Show top tracks (periods: overall, 7day, 1month, 3month, 6month, 12month)"""
        
        target_user = user or ctx.author
        lastfm_username = self.get_lastfm_user(target_user.id)
        
        if not lastfm_username:
            if target_user == ctx.author:
                embed = discord.Embed(
                    description=f"❌ You haven't set your Last.fm username! Use `{ctx.prefix}fmset <username>`",
                    color=discord.Color.from_str("#495678")
                )
            else:
                embed = discord.Embed(
                    description=f"❌ **{target_user.name}** hasn't set their Last.fm username!",
                    color=discord.Color.from_str("#495678")
                )
            return await ctx.send(embed=embed)
        
        # Validate period
        valid_periods = ["overall", "7day", "1month", "3month", "6month", "12month"]
        if period not in valid_periods:
            period = "overall"
        
        # Fetch top tracks
        data = await self.fetch_lastfm('user.gettoptracks', {
            'user': lastfm_username,
            'period': period,
            'limit': 10
        })
        
        if not data or 'toptracks' not in data:
            embed = discord.Embed(
                description="❌ Failed to fetch Last.fm data!",
                color=discord.Color.from_str("#495678")
            )
            return await ctx.send(embed=embed)
        
        tracks = data['toptracks'].get('track', [])
        if not tracks:
            embed = discord.Embed(
                description=f"❌ **{lastfm_username}** hasn't listened to anything!",
                color=discord.Color.from_str("#495678")
            )
            return await ctx.send(embed=embed)
        
        # Build track list
        track_list = ""
        for i, track in enumerate(tracks[:10], 1):
            artist = track['artist']['name']
            song = track['name']
            plays = track['playcount']
            track_list += f"`{i}.` **{song}** by {artist} ({plays} plays)\n"
        
        period_names = {
            "overall": "Overall",
            "7day": "Last 7 Days",
            "1month": "Last Month",
            "3month": "Last 3 Months",
            "6month": "Last 6 Months",
            "12month": "Last Year"
        }
        
        embed = discord.Embed(
            title=f"Top Tracks - {period_names.get(period, period)}",
            description=track_list,
            color=discord.Color.from_str("#495678")
        )
        
        embed.set_author(
            name=f"{target_user.name} ({lastfm_username})",
            icon_url=target_user.display_avatar.url
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="fmartists", aliases=["topartists", "fmta"])
    async def top_artists(self, ctx, user: Union[discord.Member, discord.User] = None, period: str = "overall"):
        """Show top artists (periods: overall, 7day, 1month, 3month, 6month, 12month)"""
        
        target_user = user or ctx.author
        lastfm_username = self.get_lastfm_user(target_user.id)
        
        if not lastfm_username:
            if target_user == ctx.author:
                embed = discord.Embed(
                    description=f"❌ You haven't set your Last.fm username! Use `{ctx.prefix}fmset <username>`",
                    color=discord.Color.from_str("#495678")
                )
            else:
                embed = discord.Embed(
                    description=f"❌ **{target_user.name}** hasn't set their Last.fm username!",
                    color=discord.Color.from_str("#495678")
                )
            return await ctx.send(embed=embed)
        
        # Validate period
        valid_periods = ["overall", "7day", "1month", "3month", "6month", "12month"]
        if period not in valid_periods:
            period = "overall"
        
        # Fetch top artists
        data = await self.fetch_lastfm('user.gettopartists', {
            'user': lastfm_username,
            'period': period,
            'limit': 10
        })
        
        if not data or 'topartists' not in data:
            embed = discord.Embed(
                description="❌ Failed to fetch Last.fm data!",
                color=discord.Color.from_str("#495678")
            )
            return await ctx.send(embed=embed)
        
        artists = data['topartists'].get('artist', [])
        if not artists:
            embed = discord.Embed(
                description=f"❌ **{lastfm_username}** hasn't listened to anything!",
                color=discord.Color.from_str("#495678")
            )
            return await ctx.send(embed=embed)
        
        # Build artist list
        artist_list = ""
        for i, artist in enumerate(artists[:10], 1):
            name = artist['name']
            plays = artist['playcount']
            artist_list += f"`{i}.` **{name}** ({plays} plays)\n"
        
        period_names = {
            "overall": "Overall",
            "7day": "Last 7 Days",
            "1month": "Last Month",
            "3month": "Last 3 Months",
            "6month": "Last 6 Months",
            "12month": "Last Year"
        }
        
        embed = discord.Embed(
            title=f"Top Artists - {period_names.get(period, period)}",
            description=artist_list,
            color=discord.Color.from_str("#495678")
        )
        
        embed.set_author(
            name=f"{target_user.name} ({lastfm_username})",
            icon_url=target_user.display_avatar.url
        )
        
        await ctx.send(embed=embed)
    
    # Error handlers
    @nowplaying.error
    @set_lastfm.error
    @remove_lastfm.error
    @top_tracks.error
    @top_artists.error
    async def lastfm_error(self, ctx, error):
        if isinstance(error, commands.MemberNotFound):
            await ctx.send("❌ Member not found!")
        elif isinstance(error, commands.UserNotFound):
            await ctx.send("❌ User not found!")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ Invalid argument provided!")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Missing required argument: {error.param.name}")


async def setup(bot):
    await bot.add_cog(LastFM(bot))