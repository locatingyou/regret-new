import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone
from typing import Union
import asyncio
import psutil
import os
import math
import platform

class RolesView(discord.ui.View):
    """View for navigating through roles pages"""
    
    def __init__(self, ctx, pages, timeout=180):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.pages = pages
        self.current_page = 0
        self.message = None
        
        # Update button states
        self.update_buttons()
    
    def update_buttons(self):
        """Update button states based on current page"""
        self.previous_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == len(self.pages) - 1
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Check if the user clicking the button is the command author"""
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("<:deny:1429468818094424075> You cannot use this menu!", ephemeral=True)
            return False
        return True
    
    @discord.ui.button(emoji="<:left:1429466193139339355>", style=discord.ButtonStyle.secondary, custom_id="previous")
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to previous page"""
        self.current_page = max(0, self.current_page - 1)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
    
    @discord.ui.button(emoji="<:right:1429466191784706088>", style=discord.ButtonStyle.secondary, custom_id="next")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to next page"""
        self.current_page = min(len(self.pages) - 1, self.current_page + 1)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
    
    @discord.ui.button(emoji="<:close:1429466190408974496>", style=discord.ButtonStyle.secondary, custom_id="close")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Close the roles menu"""
        await interaction.response.defer()
        await self.message.delete()
        self.stop()
    
    async def on_timeout(self):
        """Called when the view times out"""
        try:
            for item in self.children:
                item.disabled = True
            await self.message.edit(view=self)
        except:
            pass

class Utility(commands.Cog):
    """Utility and information commands"""
    
    def __init__(self, bot):
        self.bot = bot
        self.deleted_messages = {}
        # Store edited messages: {channel_id: {'before': message, 'after': message, 'time': datetime}}
        self.edited_messages = {}
        # Store AFK users: {user_id: {'reason': str, 'time': datetime}}
        self.afk_users = {}
        self.suggestion_channel_id = 1432034041678528663
    
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
            color=discord.Color.from_str("#a6afe7")
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
    
    @commands.command(name="avatar", aliases=["av", "pfp"])
    async def avatar(self, ctx, user: Union[discord.Member, discord.User] = None):
        """Get a user's avatar."""
        
        user = user or ctx.author
        
        embed = discord.Embed(
            title=f"{user.name}'s Avatar",
            color=discord.Color.from_str("#a6afe7")
        )
        embed.set_image(url=user.display_avatar.url)
        embed.add_field(
            name="Links",
            value=f"[PNG]({user.display_avatar.replace(format='png', size=4096).url}) • "
                  f"[JPG]({user.display_avatar.replace(format='jpg', size=4096).url}) • "
                  f"[WEBP]({user.display_avatar.replace(format='webp', size=4096).url})",
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="banner", aliases=["userbanner"])
    async def banner(self, ctx, user: Union[discord.Member, discord.User] = None):
        """Get a user's banner."""
        
        user = user or ctx.author
        
        # Fetch full user to get banner
        user = await self.bot.fetch_user(user.id)
        
        if user.banner:
            embed = discord.Embed(
                title=f"{user.name}'s Banner",
                color=discord.Color.from_str("#a6afe7")
            )
            embed.set_image(url=user.banner.url)
            embed.add_field(
                name="Links",
                value=f"[PNG]({user.banner.replace(format='png', size=4096).url}) • "
                      f"[JPG]({user.banner.replace(format='jpg', size=4096).url}) • "
                      f"[WEBP]({user.banner.replace(format='webp', size=4096).url})",
                inline=False
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description=f"<:deny:1429468818094424075> **{user.name}** doesn't have a banner!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
    
        # Slash commands for external app support
    @app_commands.command(name="avatar", description="Get a user's avatar")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def avatar_slash(self, interaction: discord.Interaction, user: Union[discord.Member, discord.User] = None):
        """Get a user's avatar (slash command)."""
        
        user = user or interaction.user
        
        embed = discord.Embed(
            title=f"{user.name}'s Avatar",
            color=discord.Color.from_str("#a6afe7")
        )
        embed.set_image(url=user.display_avatar.url)
        embed.add_field(
            name="Links",
            value=f"[PNG]({user.display_avatar.replace(format='png', size=4096).url}) • "
                  f"[JPG]({user.display_avatar.replace(format='jpg', size=4096).url}) • "
                  f"[WEBP]({user.display_avatar.replace(format='webp', size=4096).url})",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="banner", description="Get a user's banner")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def banner_slash(self, interaction: discord.Interaction, user: Union[discord.Member, discord.User] = None):
        """Get a user's banner (slash command)."""
        
        user = user or interaction.user
        
        # Fetch full user to get banner
        user = await self.bot.fetch_user(user.id)
        
        if user.banner:
            embed = discord.Embed(
                title=f"{user.name}'s Banner",
                color=discord.Color.from_str("#a6afe7")
            )
            embed.set_image(url=user.banner.url)
            embed.add_field(
                name="Links",
                value=f"[PNG]({user.banner.replace(format='png', size=4096).url}) • "
                      f"[JPG]({user.banner.replace(format='jpg', size=4096).url}) • "
                      f"[WEBP]({user.banner.replace(format='webp', size=4096).url})",
                inline=False
            )
            await interaction.response.send_message(embed=embed)
        else:
            embed = discord.Embed(
                description=f"<:deny:1429468818094424075> **{user.name}** doesn't have a banner!",
                color=discord.Color.from_str("#a6afe7")
            )
            await interaction.response.send_message(embed=embed)
    
    @commands.command(name="servericon", aliases=["guildicon", "icon"])
    async def servericon(self, ctx):
        """Get the server's icon."""
        
        if ctx.guild.icon:
            embed = discord.Embed(
                title=f"{ctx.guild.name}'s Icon",
                color=discord.Color.from_str("#a6afe7")
            )
            embed.set_image(url=ctx.guild.icon.url)
            embed.add_field(
                name="Links",
                value=f"[PNG]({ctx.guild.icon.replace(format='png', size=4096).url}) • "
                      f"[JPG]({ctx.guild.icon.replace(format='jpg', size=4096).url}) • "
                      f"[WEBP]({ctx.guild.icon.replace(format='webp', size=4096).url})",
                inline=False
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> This server doesn't have an icon!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="serverbanner", aliases=["guildbanner", "sbanner"])
    async def serverbanner(self, ctx):
        """Get the server's banner."""
        
        if ctx.guild.banner:
            embed = discord.Embed(
                title=f"{ctx.guild.name}'s Banner",
                color=discord.Color.from_str("#a6afe7")
            )
            embed.set_image(url=ctx.guild.banner.url)
            embed.add_field(
                name="Links",
                value=f"[PNG]({ctx.guild.banner.replace(format='png', size=4096).url}) • "
                      f"[JPG]({ctx.guild.banner.replace(format='jpg', size=4096).url}) • "
                      f"[WEBP]({ctx.guild.banner.replace(format='webp', size=4096).url})",
                inline=False
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> This server doesn't have a banner!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="userinfo", aliases=["ui", "whois"])
    async def userinfo(self, ctx, user: Union[discord.Member, discord.User] = None):
        """Get information about a user."""
        
        user = user or ctx.author
        
        embed = discord.Embed(
            title=f"{user.name}",
            color=discord.Color.from_str("#a6afe7")
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        
        # Basic info
        embed.add_field(name="ID", value=user.id, inline=True)
        embed.add_field(name="Created", value=f"<t:{int(user.created_at.timestamp())}:R>", inline=True)
        
        # Member-specific info
        if isinstance(user, discord.Member):
            if user.joined_at:
                embed.add_field(name="Joined", value=f"<t:{int(user.joined_at.timestamp())}:R>", inline=True)
            
            if user.premium_since:
                embed.add_field(name="Boosting Since", value=f"<t:{int(user.premium_since.timestamp())}:R>", inline=True)
            
            roles = [role.mention for role in user.roles[1:]]  # Skip @everyone
            if roles:
                embed.add_field(
                    name=f"Roles [{len(roles)}]",
                    value=" ".join(roles[:10]) + (f" (+{len(roles) - 10})" if len(roles) > 10 else ""),
                    inline=False
                )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="serverinfo", aliases=["si", "guildinfo"])
    async def serverinfo(self, ctx):
        """Get information about the current server"""
        
        guild = ctx.guild
        
        # Count members
        total_members = guild.member_count
        bots = len([m for m in guild.members if m.bot])
        humans = total_members - bots
        
        # Count channels
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        categories = len(guild.categories)
        
        # Server boost info
        boost_level = guild.premium_tier
        boost_count = guild.premium_subscription_count
        
        # Get creation date
        created_timestamp = int(guild.created_at.timestamp())
        
        embed = discord.Embed(
            title=guild.name,
            color=discord.Color.from_str("#a6afe7")
        )
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        # Server info
        server_info = f"**Owner:** {guild.owner.mention if guild.owner else 'Unknown'}\n"
        server_info += f"**Created:** <t:{created_timestamp}:R>\n"
        server_info += f"**Members:** {total_members:,} ({humans:,} humans, {bots:,} bots)"
        
        embed.add_field(
            name="Server Info",
            value=server_info,
            inline=False
        )
        
        # Channel info
        channel_info = f"**Categories:** {categories}\n"
        channel_info += f"**Text Channels:** {text_channels}\n"
        channel_info += f"**Voice Channels:** {voice_channels}"
        
        embed.add_field(
            name="Channels",
            value=channel_info,
            inline=True
        )
        
        # Boost info
        boost_info = f"**Boost Level:** {boost_level}\n"
        boost_info += f"**Boosts:** {boost_count}\n"
        boost_info += f"**Roles:** {len(guild.roles)}"
        
        embed.add_field(
            name="Other",
            value=boost_info,
            inline=True
        )
        
        embed.set_footer(text=f"Server ID: {guild.id}")
        
        await ctx.send(embed=embed)
    
    @commands.command(name="roleinfo", aliases=["ri"])
    async def roleinfo(self, ctx, *, role: discord.Role = None):
        """Get information about a role."""
        
        if role is None:
            embed = self.create_command_help_embed(ctx, ctx.command)
            return await ctx.send(embed=embed)
        
        embed = discord.Embed(
            title=role.name,
            color=role.color if role.color != discord.Color.default() else discord.Color.from_str("#a6afe7")()
        )
        
        embed.add_field(name="ID", value=role.id, inline=True)
        embed.add_field(name="Color", value=str(role.color), inline=True)
        embed.add_field(name="Position", value=role.position, inline=True)
        embed.add_field(name="Members", value=len(role.members), inline=True)
        embed.add_field(name="Mentionable", value="Yes" if role.mentionable else "No", inline=True)
        embed.add_field(name="Hoisted", value="Yes" if role.hoist else "No", inline=True)
        embed.add_field(name="Created", value=f"<t:{int(role.created_at.timestamp())}:R>", inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="ping")
    async def ping(self, ctx):
        """Check the bot's latency."""
        
        embed = discord.Embed(
            description=f"latency: `{round(self.bot.latency * 1000)}ms`",
            color=discord.Color.from_str("#a6afe7")
        )
        await ctx.send(embed=embed)
    
    @commands.command(name="uptime")
    async def uptime(self, ctx):
        """Check how long the bot has been online."""
        
        if hasattr(self.bot, 'uptime'):
            uptime = datetime.utcnow() - self.bot.uptime
            days = uptime.days
            hours, remainder = divmod(uptime.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"
            
            embed = discord.Embed(
                description=f"⏰ Uptime: **{uptime_str}**",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send("<:deny:1429468818094424075> Uptime tracking not enabled!")
    
    @commands.command(name="membercount", aliases=["mc", "members"])
    async def membercount(self, ctx):
        """Get the server's member count."""
        
        total_members = ctx.guild.member_count
        bots = sum(1 for member in ctx.guild.members if member.bot)
        humans = total_members - bots
        
        embed = discord.Embed(
            title="Member Count",
            color=discord.Color.from_str("#a6afe7")
        )
        embed.add_field(name="Total", value=total_members, inline=True)
        embed.add_field(name="Humans", value=humans, inline=True)
        embed.add_field(name="Bots", value=bots, inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="botinfo", aliases=["bi", "about"])
    async def botinfo(self, ctx):
        """Get information about the bot."""
        
        # Get bot stats
        total_commands = len(self.bot.commands)
        total_cogs = len(self.bot.cogs)
        total_users = len(self.bot.users)
        total_servers = len(self.bot.guilds)
        total_channels = sum(len(guild.channels) for guild in self.bot.guilds)
        
        # Get process info
        process = psutil.Process(os.getpid())
        
        # CPU usage
        cpu_percent = process.cpu_percent(interval=0.1)
        cpu_count = psutil.cpu_count()
        
        # Memory usage
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / (1024 ** 2)
        
        # System memory
        system_memory = psutil.virtual_memory()
        total_memory_gb = system_memory.total / (1024 ** 3)
        memory_percent = system_memory.percent
        
        # Calculate uptime
        uptime_str = "Unknown"
        if hasattr(self.bot, 'uptime'):
            uptime = datetime.utcnow() - self.bot.uptime
            days = uptime.days
            hours, remainder = divmod(uptime.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            if days > 0:
                uptime_str = f"{days}d {hours}h"
            elif hours > 0:
                uptime_str = f"{hours}h {minutes}m"
            else:
                uptime_str = f"{minutes}m {seconds}s"
        
        # Get creation date
        created_timestamp = int(self.bot.user.created_at.timestamp()) if self.bot.user else 0
        
        # Platform info
        system_platform = platform.system()
        python_version = platform.python_version()
        discord_version = discord.__version__
        
        # Build embed to match JSON format
        embed = discord.Embed(
            title="",
            description=f"Developed and maintained by **[zero](https://discord.com/channels/user/1423011606782021763)**\nUtilizing `{total_commands}` commands across `{total_cogs}` cogs.\n",
            color=discord.Color.from_str("#a6afe7")
        )
        
        # Set author with server icon
        if ctx.guild and ctx.guild.icon:
            embed.set_author(
                name=self.bot.user.name,
                icon_url=ctx.guild.icon.url
            )
        
        # Set thumbnail with bot icon
        if self.bot.user:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        
        # Bot Stats Field (condensed)
        bot_stats = f"**Bot**\n>>> **Users:** {total_users:,}\n"
        bot_stats += f"**Servers:** {total_servers:,}\n"
        bot_stats += f"**Channels:** {total_channels:,}\n"
        bot_stats += f"**Created:** <t:{created_timestamp}:R>\n"
        
        embed.add_field(
            name="",
            value=bot_stats,
            inline=True
        )
        
        # Server Stats Field (condensed)
        server_stats = f"**Server**\n>>> **Platform:** {system_platform}\n"
        server_stats += f"**Python:** {python_version}\n"
        server_stats += f"**Discord.py:** {discord_version}\n"
        server_stats += f"**CPU Cores:** {cpu_count}"
        
        embed.add_field(
            name="",
            value=server_stats,
            inline=True
        )
        
        # Machine Stats Field (condensed)
        machine_stats = f"**Machine**\n>>> **CPU Usage:** {cpu_percent:.1f}%\n"
        machine_stats += f"**Bot Memory:** {memory_mb:.1f} MB\n"
        machine_stats += f"**System Memory:** {memory_percent:.1f}%"
        
        embed.add_field(
            name="",
            value=machine_stats,
            inline=True
        )
        
        await ctx.send(embed=embed)

    @commands.command(name="roles")
    async def roles(self, ctx):
        """Display all server roles in hierarchy order (high to low)"""
        
        # Get all roles except @everyone and sort by position (highest first)
        roles = [role for role in ctx.guild.roles if role.name != "@everyone"]
        roles.sort(key=lambda r: r.position, reverse=True)
        
        if not roles:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> No roles found in this server!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        # Split roles into pages (10 per page)
        roles_per_page = 10
        total_pages = math.ceil(len(roles) / roles_per_page)
        pages = []
        
        for page_num in range(total_pages):
            start_idx = page_num * roles_per_page
            end_idx = start_idx + roles_per_page
            page_roles = roles[start_idx:end_idx]
            
            # Create embed for this page
            embed = discord.Embed(
                title=f"Roles in {ctx.guild.name}",
                color=discord.Color.from_str("#a6afe7")
            )
            
            # Build roles list for this page
            roles_text = ""
            for idx, role in enumerate(page_roles, start=start_idx + 1):
                # Get member count for this role
                member_count = len(role.members)
                
                # Format: position. role mention - member count
                roles_text += f"`{idx}.` {role.mention} - **{member_count}** members\n"
            
            embed.description = roles_text
            
            embed.set_footer(
                text=f"Page {page_num + 1}/{total_pages} • Total roles: {len(roles)} • Requested by {ctx.author}",
                icon_url=ctx.author.display_avatar.url
            )
            
            pages.append(embed)
        
        # Send with view if multiple pages, otherwise just send the embed
        if len(pages) > 1:
            view = RolesView(ctx, pages)
            message = await ctx.send(embed=pages[0], view=view)
            view.message = message
        else:
            await ctx.send(embed=pages[0])
    
    # Error handlers
    @avatar.error
    @banner.error
    @userinfo.error
    @roleinfo.error
    async def utility_error(self, ctx, error):
        if isinstance(error, commands.MemberNotFound):
            await ctx.send("<:deny:1429468818094424075> Member not found!")
        elif isinstance(error, commands.UserNotFound):
            await ctx.send("<:deny:1429468818094424075> User not found!")
        elif isinstance(error, commands.RoleNotFound):
            await ctx.send("<:deny:1429468818094424075> Role not found!")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("<:deny:1429468818094424075> Invalid argument provided!")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"<:deny:1429468818094424075> Missing required argument: {error.param.name}")
    
    @commands.Cog.listener()
    async def on_message_delete(self, message):
        """Store deleted messages for snipe command"""
        if message.author.bot:
            return
        
        self.deleted_messages[message.channel.id] = {
            'message': message,
            'time': datetime.now(timezone.utc)
        }
    
    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        """Store edited messages for editsnipe command"""
        if before.author.bot or before.content == after.content:
            return
        
        self.edited_messages[after.channel.id] = {
            'before': before,
            'after': after,
            'time': datetime.now(timezone.utc)
        }
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Check for AFK users and remove AFK status when they send a message"""
        if message.author.bot:
            return
        
        # Get the context to check if this is a command
        ctx = await self.bot.get_context(message)
        
        # Don't remove AFK if they're using the afk command
        if ctx.valid and ctx.command and ctx.command.name == 'afk':
            return
        
        # Remove AFK status if user sends a message
        if message.author.id in self.afk_users:
            afk_data = self.afk_users.pop(message.author.id)
            afk_duration = datetime.now(timezone.utc) - afk_data['time']
            
            # Calculate duration
            minutes = int(afk_duration.total_seconds() / 60)
            hours = minutes // 60
            minutes = minutes % 60
            
            if hours > 0:
                duration_str = f"{hours}h {minutes}m"
            else:
                duration_str = f"{minutes}m"
            
            try:
                await message.channel.send(
                    f"Welcome back {message.author.mention}! You were AFK for {duration_str}.",
                    delete_after=5
                )
            except:
                pass
        
        # Check if message mentions any AFK users
        for user in message.mentions:
            if user.id in self.afk_users and user.id != message.author.id:
                afk_data = self.afk_users[user.id]
                reason = afk_data['reason']
                try:
                    embed = discord.Embed(
                        description=f"<:warn:1429851523193770185> {user.mention} is currently AFK: {reason}",
                        color=discord.Color.from_str("#a6afe7")
                    )
                    await message.channel.send(embed=embed)
                except:
                    pass
    
    @commands.command(name="snipe", aliases=["s"])
    async def snipe(self, ctx):
        """Show the last deleted message in this channel"""
        if ctx.channel.id not in self.deleted_messages:
            await ctx.send("There's nothing to snipe!")
            return
        
        data = self.deleted_messages[ctx.channel.id]
        message = data['message']
        delete_time = data['time']
        
        embed = discord.Embed(
            description=message.content if message.content else "*No content*",
            color=0xa6afe7,
            timestamp=delete_time
        )
        
        embed.set_author(
            name=message.author.display_name,
            icon_url=message.author.display_avatar.url
        )
        
        # Add attachments if any
        if message.attachments:
            attachment = message.attachments[0]
            if attachment.content_type and attachment.content_type.startswith('image'):
                embed.set_image(url=attachment.url)
            else:
                embed.add_field(name="Attachment", value=f"[{attachment.filename}]({attachment.url})")
        
        embed.set_footer(text="Deleted")
        
        await ctx.send(embed=embed)
    
    @commands.command(name="editsnipe", aliases=["es"])
    async def editsnipe(self, ctx):
        """Show the last edited message in this channel"""
        if ctx.channel.id not in self.edited_messages:
            await ctx.send("There's nothing to snipe!")
            return
        
        data = self.edited_messages[ctx.channel.id]
        before = data['before']
        after = data['after']
        edit_time = data['time']
        
        embed = discord.Embed(
            color=0xa6afe7,
            timestamp=edit_time
        )
        
        embed.set_author(
            name=before.author.display_name,
            icon_url=before.author.display_avatar.url
        )
        
        embed.add_field(
            name="Before",
            value=before.content if before.content else "*No content*",
            inline=False
        )
        
        embed.add_field(
            name="After",
            value=after.content if after.content else "*No content*",
            inline=False
        )
        
        embed.set_footer(text="Edited")
        
        await ctx.send(embed=embed)
    
    @commands.command(name="clearsnipe", aliases=["cs"])
    @commands.has_permissions(manage_messages=True)
    async def clearsnipe(self, ctx):
        """Clear all sniped messages in this channel (Moderator only)"""
        cleared_count = 0
        
        if ctx.channel.id in self.deleted_messages:
            del self.deleted_messages[ctx.channel.id]
            cleared_count += 1
        
        if ctx.channel.id in self.edited_messages:
            del self.edited_messages[ctx.channel.id]
            cleared_count += 1
        
        if cleared_count == 0:
            await ctx.send("There's nothing to clear!")
        else:
            await ctx.send(f"✅ Cleared {cleared_count} sniped message(s) from this channel.")
    
    @commands.command(name="afk")
    async def afk(self, ctx, *, reason: str = "AFK"):
        """Set your AFK status"""
        self.afk_users[ctx.author.id] = {
            'reason': reason,
            'time': datetime.now(timezone.utc)
        }
        
        await ctx.send(embed=discord.Embed(description=f"💤 {ctx.author.mention} is now AFK: {reason}", color=0x495678))
    
    @commands.command(name='invite', aliases=["inv"], help='Get the bot invite link')
    async def invite(self, ctx):
        invite_link = discord.utils.oauth_url(
            self.bot.user.id,
            permissions=discord.Permissions(administrator=True)
        )
        
        embed = discord.Embed(
            description=f"Click **[here]({invite_link})** to invite the bot.",
            color=discord.Color.from_str("#495678")
        )
        await ctx.send(embed=embed)

    @commands.command(name='inrole', help='Shows all members with a specific role')
    async def inrole(self, ctx, *, role_input: str):
        # Try to find the role by mention, ID, or name
        role = None
        
        # Check if it's a mention (e.g., <@&123456789>)
        if role_input.startswith('<@&') and role_input.endswith('>'):
            role_id = int(role_input[3:-1])
            role = ctx.guild.get_role(role_id)
        # Check if it's an ID (numeric string)
        elif role_input.isdigit():
            role = ctx.guild.get_role(int(role_input))
        # Otherwise, search by name
        else:
            role = discord.utils.get(ctx.guild.roles, name=role_input)
        
        if not role:
            embed = discord.Embed(
                description=f"❌ Role not found!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        members = role.members
        
        if not members:
            embed = discord.Embed(
                description=f"❌ No members found with the role **{role.name}**",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        # Paginate members (10 per page)
        per_page = 10
        pages = []
        
        for i in range(0, len(members), per_page):
            page_members = members[i:i + per_page]
            description = ""
            
            for idx, member in enumerate(page_members, start=i + 1):
                description += f"`{idx:02d}` <@{member.id}> ({member.id})\n"
            
            pages.append(description)
        
        # Create view with buttons
        class PaginationView(discord.ui.View):
            def __init__(self, pages, author, role_name):
                super().__init__(timeout=60)
                self.pages = pages
                self.current_page = 0
                self.author = author
                self.role_name = role_name
                self.update_buttons()
            
            def update_buttons(self):
                self.children[0].disabled = self.current_page == 0
                self.children[1].disabled = self.current_page == len(self.pages) - 1
            
            async def interaction_check(self, interaction: discord.Interaction) -> bool:
                if interaction.user != self.author:
                    await interaction.response.send_message("❌ This is not your menu!", ephemeral=True)
                    return False
                return True
            
            @discord.ui.button(emoji="<:left:1429466193139339355>", style=discord.ButtonStyle.secondary)
            async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                self.current_page -= 1
                self.update_buttons()
                
                embed = discord.Embed(
                    title=f"Members with {self.role_name}",
                    description=self.pages[self.current_page],
                    color=discord.Color.from_str("#a6afe7")
                )
                embed.set_footer(text=f"Page {self.current_page + 1}/{len(self.pages)}")
                await interaction.response.edit_message(embed=embed, view=self)
            
            @discord.ui.button(emoji="<:right:1429466191784706088>", style=discord.ButtonStyle.secondary)
            async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                self.current_page += 1
                self.update_buttons()
                
                embed = discord.Embed(
                    title=f"Members with {self.role_name}",
                    description=self.pages[self.current_page],
                    color=discord.Color.from_str("#a6afe7")
                )
                embed.set_footer(text=f"Page {self.current_page + 1}/{len(self.pages)}")
                await interaction.response.edit_message(embed=embed, view=self)
            
            @discord.ui.button(emoji="<:close:1429466190408974496>", style=discord.ButtonStyle.secondary)
            async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                await interaction.message.delete()
                self.stop()
        
        # Send first page
        embed = discord.Embed(
            title=f"Members with {role.name}",
            description=pages[0],
            color=discord.Color.from_str("#a6afe7")
        )
        embed.set_footer(text=f"Page 1/{len(pages)}")
        
        if len(pages) == 1:
            await ctx.send(embed=embed)
        else:
            view = PaginationView(pages, ctx.author, role.name)
            await ctx.send(embed=embed, view=view)

    @app_commands.command(name="suggest", description="Submit a suggestion")
    @app_commands.describe(suggestion="Your suggestion")
    async def suggest(self, interaction: discord.Interaction, suggestion: str):
        """Submit a suggestion to the suggestions channel"""
        
        # Get the suggestion channel
        channel = self.bot.get_channel(self.suggestion_channel_id)
        
        if not channel:
            await interaction.response.send_message(
                "<:deny:1431626916036739072> Suggestion channel not found!", 
                ephemeral=True
            )
            return
        
        # Create the embed
        embed = discord.Embed(
            title="New Suggestion!",
            description=f"```js\n{suggestion}\n```",
            color=0xa6afe7  # Discord blurple color
        )
        
        # Add footer with user info
        embed.set_footer(
            text=f"Suggested by: {interaction.user.name} ({interaction.user.id})"
        )
        
        # Send the suggestion to the channel
        try:
            message = await channel.send(embed=embed)
            
            # Add reactions
            await message.add_reaction("<:approve:1431624157916958795>")
            await message.add_reaction("<:deny:1431626916036739072>")
            
            # Confirm to the user
            await interaction.response.send_message(
                "<:approve:1431624157916958795> Your suggestion has been submitted!", 
                ephemeral=True
            )
            
        except discord.Forbidden:
            await interaction.response.send_message(
                "<:deny:1431626916036739072> I don't have permission to send messages in the suggestion channel!", 
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"<:deny:1431626916036739072> An error occurred: {str(e)}", 
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Utility(bot))