import discord
from discord.ext import commands
import time
import sqlite3
import os
from config import COLOR, APPROVE_EMOJI, DENY_EMOJI

class Information(commands.Cog):
    """Information and utility commands"""
    
    def __init__(self, bot):
        self.bot = bot
        self.color = COLOR
        self.approve_emoji = APPROVE_EMOJI
        self.deny_emoji = DENY_EMOJI
        self.db_path = "data/disabled.db"
        self.init_database()

    def init_database(self):
        """Initialize the database and create tables if they don't exist"""
        # Create data directory if it doesn't exist
        os.makedirs("data", exist_ok=True)
        
        # Connect and create table
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS disabled_servers (
                server_id INTEGER PRIMARY KEY,
                disabled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def is_server_disabled(self, server_id):
        """Check if a server is disabled"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT server_id FROM disabled_servers WHERE server_id = ?", (server_id,))
        result = cursor.fetchone()
        conn.close()
        return result is not None

    def disable_server(self, server_id):
        """Disable a server"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO disabled_servers (server_id) VALUES (?)", (server_id,))
            conn.commit()
            success = True
        except sqlite3.IntegrityError:
            # Server already disabled
            success = False
        conn.close()
        return success

    def enable_server(self, server_id):
        """Enable a server (remove from disabled list)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM disabled_servers WHERE server_id = ?", (server_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return deleted

    def get_all_disabled_servers(self):
        """Get list of all disabled server IDs"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT server_id FROM disabled_servers")
        results = [row[0] for row in cursor.fetchall()]
        conn.close()
        return results
    
    #@commands.command(name="ping", aliases=["latency"])
    async def ping(self, ctx):
        """Shows the current latency of the bot."""
        
        # Measure typing latency
        start = time.perf_counter()
        message = await ctx.send("🏓 Pinging...")
        end = time.perf_counter()
        
        # Calculate latencies
        api_latency = round(self.bot.latency * 1000)
        typing_latency = round((end - start) * 1000)
        
        embed = discord.Embed(
            title="🏓 Pong!",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="API Latency",
            value=f"`{api_latency}ms`",
            inline=True
        )
        
        embed.add_field(
            name="Bot Latency",
            value=f"`{typing_latency}ms`",
            inline=True
        )
        
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        embed.timestamp = discord.utils.utcnow()
        
        await message.edit(content=None, embed=embed)
    
    #@commands.command(name="botinfo", aliases=["info", "about"])
    async def botinfo(self, ctx):
        """Shows information about the bot."""
        
        # Calculate bot stats
        total_members = sum(guild.member_count for guild in self.bot.guilds)
        total_channels = sum(len(guild.channels) for guild in self.bot.guilds)
        
        embed = discord.Embed(
            title=f"About {self.bot.user.name}",
            description="A powerful Discord bot built with discord.py",
            color=discord.Color.from_str("#a6afe7")
        )
        
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        
        embed.add_field(
            name="📊 Statistics",
            value=f"**Servers:** {len(self.bot.guilds)}\n"
                  f"**Users:** {total_members:,}\n"
                  f"**Channels:** {total_channels:,}",
            inline=True
        )
        
        embed.add_field(
            name="⚙️ System",
            value=f"**Latency:** {round(self.bot.latency * 1000)}ms\n"
                  f"**Discord.py:** {discord.__version__}",
            inline=True
        )
        
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        embed.timestamp = discord.utils.utcnow()
        
        await ctx.send(embed=embed)
    
    #@commands.command(name="serverinfo", aliases=["si", "server"])
    async def serverinfo(self, ctx):
        """Shows information about the current server."""
        
        guild = ctx.guild
        
        embed = discord.Embed(
            title=f"{guild.name}",
            color=discord.Color.from_str("#a6afe7")
        )
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        # Server stats
        total_text = len(guild.text_channels)
        total_voice = len(guild.voice_channels)
        total_categories = len(guild.categories)
        
        embed.add_field(
            name="📊 Server Info",
            value=f"**Owner:** {guild.owner.mention}\n"
                  f"**Created:** <t:{int(guild.created_at.timestamp())}:R>\n"
                  f"**ID:** {guild.id}",
            inline=False
        )
        
        embed.add_field(
            name="👥 Members",
            value=f"**Total:** {guild.member_count}\n"
                  f"**Humans:** {len([m for m in guild.members if not m.bot])}\n"
                  f"**Bots:** {len([m for m in guild.members if m.bot])}",
            inline=True
        )
        
        embed.add_field(
            name="💬 Channels",
            value=f"**Text:** {total_text}\n"
                  f"**Voice:** {total_voice}\n"
                  f"**Categories:** {total_categories}",
            inline=True
        )
        
        embed.add_field(
            name="🎭 Other",
            value=f"**Roles:** {len(guild.roles)}\n"
                  f"**Emojis:** {len(guild.emojis)}\n"
                  f"**Boost Level:** {guild.premium_tier}",
            inline=True
        )
        
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        embed.timestamp = discord.utils.utcnow()
        
        await ctx.send(embed=embed)
    
    #@commands.command(name="userinfo", aliases=["ui", "whois"])
    async def userinfo(self, ctx, member: discord.Member = None):
        """Shows information about a user."""
        
        member = member or ctx.author
        
        embed = discord.Embed(
            title=f"User Info - {member}",
            color=member.color if member.color != discord.Color.default() else discord.Color.from_str("#a6afe7")()
        )
        
        embed.set_thumbnail(url=member.display_avatar.url)
        
        # User info
        embed.add_field(
            name="👤 General",
            value=f"**Username:** {member.name}\n"
                  f"**Display Name:** {member.display_name}\n"
                  f"**ID:** {member.id}\n"
                  f"**Bot:** {'Yes' if member.bot else 'No'}",
            inline=False
        )
        
        # Dates
        embed.add_field(
            name="📅 Dates",
            value=f"**Created:** <t:{int(member.created_at.timestamp())}:R>\n"
                  f"**Joined:** <t:{int(member.joined_at.timestamp())}:R>",
            inline=False
        )
        
        # Roles
        roles = [role.mention for role in member.roles[1:]]  # Skip @everyone
        if roles:
            embed.add_field(
                name=f"🎭 Roles [{len(roles)}]",
                value=" ".join(roles[:10]) + (f" (+{len(roles)-10} more)" if len(roles) > 10 else ""),
                inline=False
            )
        
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        embed.timestamp = discord.utils.utcnow()
        
        await ctx.send(embed=embed)

    @commands.command(name='disable', help='Disables the bot in a specific server (Bot Owner Only)')
    @commands.is_owner()
    async def disable_server_command(self, ctx, server_id: int):
        """Disable bot functionality in a specific server"""
        # Check if server exists
        guild = self.bot.get_guild(server_id)
        
        if self.is_server_disabled(server_id):
            embed = discord.Embed(
                description=f"{self.deny_emoji} Server `{server_id}` is already disabled!",
                color=self.color
            )
            await ctx.send(embed=embed)
            return

        success = self.disable_server(server_id)
        
        if success:
            guild_name = guild.name if guild else "Unknown Server"
            embed = discord.Embed(
                title="🚫 Server Disabled",
                description=f"{self.approve_emoji} Successfully disabled bot in **{guild_name}** (`{server_id}`)",
                color=self.color
            )
            embed.add_field(name="Server ID", value=f"`{server_id}`", inline=True)
            embed.add_field(name="Status", value="❌ Disabled", inline=True)
            await ctx.send(embed=embed)
            
            # Try to leave the server if bot is in it
            if guild:
                try:
                    await guild.leave()
                    embed = discord.Embed(
                        description=f"{self.approve_emoji} Left server **{guild_name}**",
                        color=self.color
                    )
                    await ctx.send(embed=embed)
                except:
                    pass
        else:
            embed = discord.Embed(
                description=f"{self.deny_emoji} Failed to disable server.",
                color=self.color
            )
            await ctx.send(embed=embed)

    @commands.command(name='enable', help='Enables the bot in a specific server (Bot Owner Only)')
    @commands.is_owner()
    async def enable_server_command(self, ctx, server_id: int):
        """Enable bot functionality in a specific server"""
        if not self.is_server_disabled(server_id):
            embed = discord.Embed(
                description=f"{self.deny_emoji} Server `{server_id}` is not disabled!",
                color=self.color
            )
            await ctx.send(embed=embed)
            return

        success = self.enable_server(server_id)
        
        if success:
            guild = self.bot.get_guild(server_id)
            guild_name = guild.name if guild else "Unknown Server"
            embed = discord.Embed(
                title="✅ Server Enabled",
                description=f"{self.approve_emoji} Successfully enabled bot in **{guild_name}** (`{server_id}`)",
                color=self.color
            )
            embed.add_field(name="Server ID", value=f"`{server_id}`", inline=True)
            embed.add_field(name="Status", value="✅ Enabled", inline=True)
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description=f"{self.deny_emoji} Failed to enable server.",
                color=self.color
            )
            await ctx.send(embed=embed)

    @commands.command(name='disabled', help='Lists all disabled servers (Bot Owner Only)')
    @commands.is_owner()
    async def list_disabled_servers(self, ctx):
        """List all disabled servers"""
        disabled_servers = self.get_all_disabled_servers()
        
        if not disabled_servers:
            embed = discord.Embed(
                description=f"{self.approve_emoji} No servers are currently disabled.",
                color=self.color
            )
            await ctx.send(embed=embed)
            return

        description = ""
        for server_id in disabled_servers:
            guild = self.bot.get_guild(server_id)
            guild_name = guild.name if guild else "Unknown Server"
            description += f"• **{guild_name}** - `{server_id}`\n"

        embed = discord.Embed(
            title="🚫 Disabled Servers",
            description=description,
            color=self.color
        )
        embed.set_footer(text=f"Total: {len(disabled_servers)} server(s)")
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        """Check if bot joins a disabled server and leave immediately"""
        if self.is_server_disabled(guild.id):
            try:
                # Try to send a message to the system channel
                if guild.system_channel:
                    embed = discord.Embed(
                        title="🚫 Access Denied",
                        description="This bot has been disabled for this server by the bot owner.",
                        color=self.color
                    )
                    await guild.system_channel.send(embed=embed)
            except:
                pass
            
            await guild.leave()

async def setup(bot):
    await bot.add_cog(Information(bot))