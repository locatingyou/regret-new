import discord
from discord.ext import commands
from datetime import timedelta
import asyncio
from typing import Union
import sqlite3
import os
import json
import re

class HelpView(discord.ui.View):
    """View for navigating through command help pages"""
    
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
        """Close the help menu"""
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

class Moderation(commands.Cog):
    """Server moderation and management commands"""
    
    def __init__(self, bot):
        self.bot = bot
        self.purple = discord.Color.from_str("#a6afe7")
        self.approve = "<:approve:1429468807348486305>"
        self.deny = "<:deny:1429468818094424075>"
        self.db_path = "data/autoreact.db"
        os.makedirs("data", exist_ok=True)
        self.db = sqlite3.connect(self.db_path)
        self.cursor = self.db.cursor()
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS autoreacts (
                guild_id INTEGER,
                trigger TEXT,
                emoji TEXT,
                strict INTEGER
            )
        """)
        self.db.commit()
        
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
    
    def create_command_help_embed(self, command, ctx, page_num=None, total_pages=None):
        """Create help embed for a command"""
        cog_name = command.cog.qualified_name if command.cog else "No category"
        
        title = f"Command: {command.qualified_name} • {cog_name} Module"
        
        embed = discord.Embed(
            title=title,
            description=command.help or "No description provided",
            color=discord.Color.from_str("#a6afe7")
        )
        
        # Add syntax and example
        syntax = f"Syntax: {ctx.prefix}{command.qualified_name}"
        if command.signature:
            syntax += f" {command.signature}"
        
        example = f"Example: {ctx.prefix}{command.qualified_name}"
        
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
        footer_text = f"Aliases: {aliases_text}"
        
        # Add page info if provided
        if page_num is not None and total_pages is not None:
            footer_text += f" • Page {page_num}/{total_pages}"
        
        embed.set_footer(
            text=footer_text,
            icon_url=self.bot.user.display_avatar.url if self.bot.user else None
        )
        
        return embed

    async def send_group_help(self, ctx, group_command):
        """Send help for a group command with subcommands and navigation buttons"""
        pages = []
        
        # Get all subcommands
        subcommands = list(group_command.commands)
        
        # Add the main group command as the first page
        main_embed = self.create_command_help_embed(group_command, ctx, 1, len(subcommands) + 1)
        pages.append(main_embed)
        
        # Add each subcommand as a separate page
        for idx, subcommand in enumerate(subcommands, start=2):
            embed = self.create_command_help_embed(subcommand, ctx, idx, len(subcommands) + 1)
            pages.append(embed)
        
        # Create view with navigation buttons
        view = HelpView(ctx, pages)
        message = await ctx.send(embed=pages[0], view=view)
        view.message = message
    
    @commands.command(name="ban", aliases=["b", "deport"])
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def ban(self, ctx, user: Union[discord.Member, discord.User] = None, *, reason="No reason provided"):
        """Ban a user from the server."""
        
        if user is None:
            embed = self.create_command_help_embed(ctx, ctx.command)
            return await ctx.send(embed=embed)
        
        # Check if user is a member in the server
        member = ctx.guild.get_member(user.id)
        
        if member:
            if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
                return await ctx.send("<:deny:1429468818094424075> You cannot ban someone with a higher or equal role!")
            
            if member == ctx.author:
                return await ctx.send("<:deny:1429468818094424075> You cannot ban yourself!")
            
            if member == ctx.guild.owner:
                return await ctx.send("<:deny:1429468818094424075> You cannot ban the server owner!")
        
        try:
            # Try to send DM before banning
            dm_sent = False
            try:
                dm_embed = discord.Embed(
                    title="🔨 You Have Been Banned",
                    description=f"You have been banned from **{ctx.guild.name}**",
                    color=discord.Color.from_str("#a6afe7")
                )
                
                dm_embed.add_field(name="Reason", value=reason, inline=False)
                dm_embed.add_field(name="Moderator", value=str(ctx.author), inline=False)
                
                if ctx.guild.icon:
                    dm_embed.set_thumbnail(url=ctx.guild.icon.url)
                
                dm_embed.set_footer(text=f"Server: {ctx.guild.name}")
                dm_embed.timestamp = discord.utils.utcnow()
                
                await user.send(embed=dm_embed)
                dm_sent = True
            except (discord.Forbidden, discord.HTTPException):
                # User has DMs disabled or bot can't send DMs
                pass
            
            # Perform the ban
            await ctx.guild.ban(user, reason=f"{reason} | Banned by {ctx.author}")
            
            response = f"<:approve:1429468807348486305> **{user}** has been banned."
            if not dm_sent:
                response += "\n*Note: Could not send DM to user.*"
            
            embed = discord.Embed(description=response, color=discord.Color.from_str("#a6afe7"))
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"<:deny:1429468818094424075> Failed to ban user: {e}")
    
    @commands.command(name="unban", aliases=["ub"])
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def unban(self, ctx, user_id: int = None, *, reason="No reason provided"):
        """Unban a user by their ID."""
        
        if user_id is None:
            embed = self.create_command_help_embed(ctx, ctx.command)
            return await ctx.send(embed=embed)
        
        try:
            user = await self.bot.fetch_user(user_id)
            await ctx.guild.unban(user, reason=f"{reason} | Unbanned by {ctx.author}")
            embed = discord.Embed(description=f"<:approve:1429468807348486305> **{user}** has been unbanned.", color=discord.Color.from_str("#a6afe7"))
            await ctx.send(embed=embed)
        except discord.NotFound:
            await ctx.send("<:deny:1429468818094424075> User not found or not banned!")
        except Exception as e:
            await ctx.send(f"<:deny:1429468818094424075> Failed to unban user: {e}")
    
    @commands.command(name="kick", aliases=["k"])
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member = None, *, reason="No reason provided"):
        """Kick a user from the server."""
        
        if member is None:
            embed = self.create_command_help_embed(ctx, ctx.command)
            return await ctx.send(embed=embed)
        
        if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            return await ctx.send("<:deny:1429468818094424075> You cannot kick someone with a higher or equal role!")
        
        if member == ctx.author:
            return await ctx.send("<:deny:1429468818094424075> You cannot kick yourself!")
        
        if member == ctx.guild.owner:
            return await ctx.send("<:deny:1429468818094424075> You cannot kick the server owner!")
        
        try:
            # Try to send DM before kicking
            dm_sent = False
            try:
                dm_embed = discord.Embed(
                    title="👢 You Have Been Kicked",
                    description=f"You have been kicked from **{ctx.guild.name}**",
                    color=discord.Color.from_str("#a6afe7")
                )
                
                dm_embed.add_field(name="Reason", value=reason, inline=False)
                dm_embed.add_field(name="Moderator", value=str(ctx.author), inline=False)
                
                if ctx.guild.icon:
                    dm_embed.set_thumbnail(url=ctx.guild.icon.url)
                
                dm_embed.set_footer(text=f"Server: {ctx.guild.name}")
                dm_embed.timestamp = discord.utils.utcnow()
                
                await member.send(embed=dm_embed)
                dm_sent = True
            except (discord.Forbidden, discord.HTTPException):
                # User has DMs disabled or bot can't send DMs
                pass
            
            # Perform the kick
            await member.kick(reason=f"{reason} | Kicked by {ctx.author}")
            
            response = f"<:approve:1429468807348486305> **{member}** has been kicked."
            if not dm_sent:
                response += "\n*Note: Could not send DM to user.*"
            
            embed = discord.Embed(description=response, color=discord.Color.from_str("#a6afe7"))
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"<:deny:1429468818094424075> Failed to kick user: {e}")
    
    @commands.command(name="mute", aliases=["m", "timeout"])
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    async def mute(self, ctx, member: discord.Member = None, duration: str = None, *, reason="No reason provided"):
        """Mute a user (timeout). Usage: !mute @user 10m reason"""
        
        if member is None:
            embed = self.create_command_help_embed(ctx, ctx.command)
            return await ctx.send(embed=embed)
        
        if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            return await ctx.send("<:deny:1429468818094424075> You cannot mute someone with a higher or equal role!")
        
        if member == ctx.author:
            return await ctx.send("<:deny:1429468818094424075> You cannot mute yourself!")
        
        if member == ctx.guild.owner:
            return await ctx.send("<:deny:1429468818094424075> You cannot mute the server owner!")
        
        # Parse duration
        if duration:
            time_units = {
                's': 1, 'm': 60, 'h': 3600, 'd': 86400
            }
            
            try:
                time_value = int(duration[:-1])
                time_unit = duration[-1].lower()
                
                if time_unit not in time_units:
                    return await ctx.send("<:deny:1429468818094424075> Invalid time format! Use: 10s, 5m, 2h, 1d")
                
                seconds = time_value * time_units[time_unit]
                
                if seconds > 2419200:  # 28 days max
                    return await ctx.send("<:deny:1429468818094424075> Duration cannot exceed 28 days!")
                
                timeout_duration = timedelta(seconds=seconds)
            except (ValueError, IndexError):
                return await ctx.send("<:deny:1429468818094424075> Invalid time format! Use: 10s, 5m, 2h, 1d")
        else:
            timeout_duration = timedelta(minutes=5)  # Default 5 minutes
        
        try:
            await member.timeout(timeout_duration, reason=f"{reason} | Muted by {ctx.author}")
            embed = discord.Embed(description=f"🔇 **{member}** has been muted for **{timeout_duration}**.", color=discord.Color.from_str("#a6afe7"))
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"<:deny:1429468818094424075> Failed to mute user: {e}")
    
    @commands.command(name="unmute", aliases=["um", "untimeout"])
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    async def unmute(self, ctx, member: discord.Member = None, *, reason="No reason provided"):
        """Unmute a user (remove timeout)."""
        
        if member is None:
            embed = self.create_command_help_embed(ctx, ctx.command)
            return await ctx.send(embed=embed)
        
        try:
            await member.timeout(None, reason=f"{reason} | Unmuted by {ctx.author}")
            embed = discord.Embed(description=f"🔊 **{member}** has been unmuted.", color=discord.Color.from_str("#a6afe7"))
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"<:deny:1429468818094424075> Failed to unmute user: {e}")
    
    @commands.command(name="lock")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def lock(self, ctx, channel: discord.TextChannel = None, *, reason="No reason provided"):
        """Lock a channel."""
        
        channel = channel or ctx.channel
        
        try:
            await channel.set_permissions(
                ctx.guild.default_role,
                send_messages=False,
                reason=f"{reason} | Locked by {ctx.author}"
            )
            await ctx.send(f"🔒 {channel.mention} has been locked.")
        except Exception as e:
            await ctx.send(f"<:deny:1429468818094424075> Failed to lock channel: {e}")
    
    @commands.command(name="unlock")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def unlock(self, ctx, channel: discord.TextChannel = None, *, reason="No reason provided"):
        """Unlock a channel."""
        
        channel = channel or ctx.channel
        
        try:
            await channel.set_permissions(
                ctx.guild.default_role,
                send_messages=None,
                reason=f"{reason} | Unlocked by {ctx.author}"
            )
            await ctx.send(f"🔓 {channel.mention} has been unlocked.")
        except Exception as e:
            await ctx.send(f"<:deny:1429468818094424075> Failed to unlock channel: {e}")
    
    @commands.command(name="purge", aliases=["clear", "clean", "c"])
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def purge(self, ctx, member: discord.Member = None, amount: int = None):
        """Delete multiple messages."""
        
        if amount is None:
            embed = self.create_command_help_embed(ctx, ctx.command)
            return await ctx.send(embed=embed)
        
        if amount < 1:
            return await ctx.send("<:deny:1429468818094424075> Amount must be at least 1!")
        
        if amount > 100:
            return await ctx.send("<:deny:1429468818094424075> Amount cannot exceed 100!")
        
        try:
            # If a member is mentioned, only delete their messages
            if member:
                def check(m):
                    return m.author.id == member.id
                
                deleted = await ctx.channel.purge(limit=amount + 1, check=check)
                msg = await ctx.send(f"<:approve:1429468807348486305> Deleted {len(deleted) - 1} messages from {member.mention}.")
            else:
                # Delete all messages
                deleted = await ctx.channel.purge(limit=amount + 1)
                msg = await ctx.send(f"<:approve:1429468807348486305> Deleted {len(deleted) - 1} messages.")
            
            await asyncio.sleep(3)
            await msg.delete()
        except Exception as e:
            await ctx.send(f"<:deny:1429468818094424075> Failed to purge messages: {e}")
    
    @commands.command(name="botclear", aliases=["bc", "clearbots"])
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def botclear(self, ctx, amount: int = 50):
        """Delete bot messages and their triggers"""
        
        if amount < 1:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Amount must be at least 1!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        if amount > 100:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Amount cannot exceed 100!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        try:
            def is_bot_or_command(message):
                # Check if message is from a bot
                if message.author.bot:
                    return True
                # Check if message is a command trigger (starts with prefix)
                if message.content.startswith(ctx.prefix):
                    return True
                return False
            
            deleted = await ctx.channel.purge(limit=amount, check=is_bot_or_command)
            embed = discord.Embed(
                description=f"<:approve:1429468807348486305> Deleted **{len(deleted)}** bot messages and commands",
                color=discord.Color.from_str("#a6afe7")
            )
            msg = await ctx.send(embed=embed)
            await msg.delete(delay=3)
        except discord.Forbidden:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> I don't have permission to delete messages!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                description=f"<:deny:1429468818094424075> An error occurred: {str(e)}",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="slowmode", aliases=["slow"])
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def slowmode(self, ctx, seconds: int = None, channel: discord.TextChannel = None):
        """Set slowmode for a channel. Use 0 to disable."""
        
        if seconds is None:
            embed = self.create_command_help_embed(ctx, ctx.command)
            return await ctx.send(embed=embed)
        
        channel = channel or ctx.channel
        
        if seconds < 0 or seconds > 21600:
            return await ctx.send("<:deny:1429468818094424075> Slowmode must be between 0 and 21600 seconds (6 hours)!")
        
        try:
            await channel.edit(slowmode_delay=seconds)
            if seconds == 0:
                await ctx.send(f"<:approve:1429468807348486305> Slowmode disabled in {channel.mention}.")
            else:
                await ctx.send(f"<:approve:1429468807348486305> Slowmode set to **{seconds}s** in {channel.mention}.")
        except Exception as e:
            await ctx.send(f"<:deny:1429468818094424075> Failed to set slowmode: {e}")

    @commands.command(name="nuke")
    @commands.has_permissions(manage_channels=True)
    async def nuke(self, ctx):
        """Nuke the current channel"""
        
        # Get the current channel
        channel = ctx.channel
        position = channel.position
        
        # Clone the channel
        new_channel = await channel.clone(reason=f"Channel nuked by {ctx.author}")
        
        # Move the new channel to the original position
        await new_channel.edit(position=position)
        
        # Delete the old channel
        await channel.delete()
        
        # Send confirmation in the new channel
        embed = discord.Embed(
            description=f"<:approve:1429468807348486305> Channel has been nuked by {ctx.author.mention}",
            color=discord.Color.from_str("#a6afe7")
        )
        await new_channel.send(embed=embed)

    @commands.command(name="rmute", aliases=["reactmute"])
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def rmute(self, ctx, member: discord.Member = None, *, reason: str = "No reason provided"):
        """Mute a member from adding reactions"""
        
        if member is None:
            embed = self.create_command_help_embed(ctx, ctx.command)
            return await ctx.send(embed=embed)
        
        if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> You cannot mute someone with an equal or higher role!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        if member.top_role >= ctx.guild.me.top_role:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> I cannot mute someone with an equal or higher role than me!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        # Look for or create the rmuted role
        rmuted_role = discord.utils.get(ctx.guild.roles, name="rmuted")
        
        if not rmuted_role:
            try:
                rmuted_role = await ctx.guild.create_role(
                    name="rmuted",
                    reason="React mute role created"
                )
                
                # Set permissions for all channels
                for channel in ctx.guild.channels:
                    try:
                        await channel.set_permissions(
                            rmuted_role,
                            add_reactions=False,
                            reason="Setting up rmuted role permissions"
                        )
                    except:
                        pass
                
            except discord.Forbidden:
                embed = discord.Embed(
                    description="<:deny:1429468818094424075> I don't have permission to create roles!",
                    color=discord.Color.from_str("#a6afe7")
                )
                return await ctx.send(embed=embed)
        
        # Check if member already has the role
        if rmuted_role in member.roles:
            embed = discord.Embed(
                description=f"<:deny:1429468818094424075> **{member}** is already reaction muted!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        try:
            await member.add_roles(rmuted_role, reason=f"{reason} | React muted by {ctx.author}")
            embed = discord.Embed(
                description=f"<:approve:1429468807348486305> **{member}** has been reaction muted\n**Reason:** {reason}",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
        except discord.Forbidden:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> I don't have permission to assign roles!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                description=f"<:deny:1429468818094424075> An error occurred: {str(e)}",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="unrmute", aliases=["unreactmute"])
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def unrmute(self, ctx, member: discord.Member = None, *, reason: str = "No reason provided"):
        """Remove reaction mute from a member"""
        
        if member is None:
            embed = self.create_command_help_embed(ctx, ctx.command)
            return await ctx.send(embed=embed)
        
        rmuted_role = discord.utils.get(ctx.guild.roles, name="rmuted")
        
        if not rmuted_role:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> The rmuted role doesn't exist!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        if rmuted_role not in member.roles:
            embed = discord.Embed(
                description=f"<:deny:1429468818094424075> **{member}** is not reaction muted!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        try:
            await member.remove_roles(rmuted_role, reason=f"{reason} | React mute removed by {ctx.author}")
            embed = discord.Embed(
                description=f"<:approve:1429468807348486305> **{member}**'s reaction mute has been removed\n**Reason:** {reason}",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
        except discord.Forbidden:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> I don't have permission to remove roles!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                description=f"<:deny:1429468818094424075> An error occurred: {str(e)}",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="imute", aliases=["imagemute"])
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def imute(self, ctx, member: discord.Member = None, *, reason: str = "No reason provided"):
        """Mute a member from posting images/attachments"""
        
        if member is None:
            embed = self.create_command_help_embed(ctx, ctx.command)
            return await ctx.send(embed=embed)
        
        if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> You cannot mute someone with an equal or higher role!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        if member.top_role >= ctx.guild.me.top_role:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> I cannot mute someone with an equal or higher role than me!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        # Look for or create the imuted role
        imuted_role = discord.utils.get(ctx.guild.roles, name="imuted")
        
        if not imuted_role:
            try:
                imuted_role = await ctx.guild.create_role(
                    name="imuted",
                    reason="Image mute role created"
                )
                
                # Set permissions for all channels
                for channel in ctx.guild.channels:
                    try:
                        await channel.set_permissions(
                            imuted_role,
                            attach_files=False,
                            embed_links=False,
                            reason="Setting up imuted role permissions"
                        )
                    except:
                        pass
                
            except discord.Forbidden:
                embed = discord.Embed(
                    description="<:deny:1429468818094424075> I don't have permission to create roles!",
                    color=discord.Color.from_str("#a6afe7")
                )
                return await ctx.send(embed=embed)
        
        # Check if member already has the role
        if imuted_role in member.roles:
            embed = discord.Embed(
                description=f"<:deny:1429468818094424075> **{member}** is already image muted!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        try:
            await member.add_roles(imuted_role, reason=f"{reason} | Image muted by {ctx.author}")
            embed = discord.Embed(
                description=f"<:approve:1429468807348486305> **{member}** has been image muted\n**Reason:** {reason}",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
        except discord.Forbidden:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> I don't have permission to assign roles!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                description=f"<:deny:1429468818094424075> An error occurred: {str(e)}",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="unimute", aliases=["unimagemute"])
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def unimute(self, ctx, member: discord.Member = None, *, reason: str = "No reason provided"):
        """Remove image mute from a member"""
        
        if member is None:
            embed = self.create_command_help_embed(ctx, ctx.command)
            return await ctx.send(embed=embed)
        
        imuted_role = discord.utils.get(ctx.guild.roles, name="imuted")
        
        if not imuted_role:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> The imuted role doesn't exist!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        if imuted_role not in member.roles:
            embed = discord.Embed(
                description=f"<:deny:1429468818094424075> **{member}** is not image muted!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        try:
            await member.remove_roles(imuted_role, reason=f"{reason} | Image mute removed by {ctx.author}")
            embed = discord.Embed(
                description=f"<:approve:1429468807348486305> **{member}**'s image mute has been removed\n**Reason:** {reason}",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
        except discord.Forbidden:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> I don't have permission to remove roles!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                description=f"<:deny:1429468818094424075> An error occurred: {str(e)}",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)

    @commands.group(name="role", aliases=["r"], invoke_without_command=True)
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def role(self, ctx, member: discord.Member = None, role: discord.Role = None):
        """Add or remove a role from a member"""
        
        # Show help with navigation if no arguments provided
        if member is None or role is None:
            await self.send_group_help(ctx, ctx.command)
            return
        
        if role.position >= ctx.guild.me.top_role.position:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> I cannot manage this role as it's higher than or equal to my highest role!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        if role.position >= ctx.author.top_role.position and ctx.author != ctx.guild.owner:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> You cannot manage this role as it's higher than or equal to your highest role!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        try:
            if role in member.roles:
                await member.remove_roles(role, reason=f"Role removed by {ctx.author}")
                embed = discord.Embed(
                    description=f"<:approve:1429468807348486305> Removed {role.mention} from {member.mention}",
                    color=discord.Color.from_str("#a6afe7")
                )
            else:
                await member.add_roles(role, reason=f"Role added by {ctx.author}")
                embed = discord.Embed(
                    description=f"<:approve:1429468807348486305> Added {role.mention} to {member.mention}",
                    color=discord.Color.from_str("#a6afe7")
                )
            await ctx.send(embed=embed)
        except discord.Forbidden:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> I don't have permission to manage this role!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                description=f"<:deny:1429468818094424075> An error occurred: {str(e)}",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
    
    @role.command(name="create", aliases=["add"])
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def role_create(self, ctx, *, name: str):
        """Create a new role"""
        
        try:
            new_role = await ctx.guild.create_role(
                name=name,
                reason=f"Role created by {ctx.author}"
            )
            embed = discord.Embed(
                description=f"<:approve:1429468807348486305> Created role {new_role.mention}",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
        except discord.Forbidden:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> I don't have permission to create roles!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                description=f"<:deny:1429468818094424075> An error occurred: {str(e)}",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
    
    @role.command(name="delete", aliases=["remove"])
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def role_delete(self, ctx, *, role: discord.Role):
        """Delete a role"""
        
        if role.position >= ctx.guild.me.top_role.position:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> I cannot delete this role as it's higher than or equal to my highest role!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        if role.position >= ctx.author.top_role.position and ctx.author != ctx.guild.owner:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> You cannot delete this role as it's higher than or equal to your highest role!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        try:
            role_name = role.name
            await role.delete(reason=f"Role deleted by {ctx.author}")
            embed = discord.Embed(
                description=f"<:approve:1429468807348486305> Deleted role **{role_name}**",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
        except discord.Forbidden:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> I don't have permission to delete this role!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                description=f"<:deny:1429468818094424075> An error occurred: {str(e)}",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
    
    @role.command(name="hoist")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def role_hoist(self, ctx, role: discord.Role):
        """Toggle role hoisting."""
        
        # Check if bot can manage this role
        if role >= ctx.guild.me.top_role:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> I cannot manage this role because it's higher than or equal to my highest role!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        # Check if user can manage this role
        if role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> You cannot manage this role because it's higher than or equal to your highest role!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        # Toggle current state
        new_state = not role.hoist
        
        # Update role
        try:
            await role.edit(hoist=new_state, reason=f"Hoist toggled by {ctx.author}")
            
            state_text = "enabled" if new_state else "disabled"
            embed = discord.Embed(
                description=f"<:approve:1429468807348486305> Successfully **{state_text}** hoisting for {role.mention}",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
        except discord.Forbidden:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> I don't have permission to manage this role!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
        except discord.HTTPException as e:
            embed = discord.Embed(
                description=f"<:deny:1429468818094424075> An error occurred: {str(e)}",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)

    @role.command(name="color", aliases=["colour"])
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def role_color(self, ctx, role: discord.Role, color: str):
        """Change a role's color (hex format like #ff0000)"""
        
        if role.position >= ctx.guild.me.top_role.position:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> I cannot edit this role as it's higher than or equal to my highest role!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        if role.position >= ctx.author.top_role.position and ctx.author != ctx.guild.owner:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> You cannot edit this role as it's higher than or equal to your highest role!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        try:
            # Convert hex to discord.Color
            if color.startswith('#'):
                color = color[1:]
            color_int = int(color, 16)
            new_color = discord.Color(color_int)
            
            await role.edit(color=new_color, reason=f"Role color changed by {ctx.author}")
            embed = discord.Embed(
                description=f"<:approve:1429468807348486305> Changed {role.mention} color to `#{color}`",
                color=new_color
            )
            await ctx.send(embed=embed)
        except ValueError:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Invalid color format! Use hex format like `#ff0000`",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
        except discord.Forbidden:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> I don't have permission to edit this role!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                description=f"<:deny:1429468818094424075> An error occurred: {str(e)}",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
    
    @role.command(name="rename")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def role_rename(self, ctx, role: discord.Role, *, new_name: str):
        """Rename a role"""
        
        if role.position >= ctx.guild.me.top_role.position:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> I cannot edit this role as it's higher than or equal to my highest role!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        if role.position >= ctx.author.top_role.position and ctx.author != ctx.guild.owner:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> You cannot edit this role as it's higher than or equal to your highest role!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        try:
            old_name = role.name
            await role.edit(name=new_name, reason=f"Role renamed by {ctx.author}")
            embed = discord.Embed(
                description=f"<:approve:1429468807348486305> Renamed **{old_name}** to {role.mention}",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
        except discord.Forbidden:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> I don't have permission to edit this role!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                description=f"<:deny:1429468818094424075> An error occurred: {str(e)}",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="picperms")
    @commands.has_permissions(manage_roles=True)
    async def picperms(self, ctx, member: discord.Member, channel: discord.TextChannel = None):
        """Toggle a member's permission to upload attachments in a specific channel"""
        
        # Use current channel if none specified
        if channel is None:
            channel = ctx.channel
        
        # Check if bot has permission to manage channel permissions
        if not channel.permissions_for(ctx.guild.me).manage_permissions:
            embed = discord.Embed(
                description=f"{self.deny} I don't have `Manage Permissions` in {channel.mention}.",
                color=self.purple
            )
            await ctx.send(embed=embed)
            return
        
        try:
            # Check current permission state
            overwrite = channel.overwrites_for(member)
            current_state = overwrite.attach_files
            
            # Toggle the permission
            if current_state is True:
                # Remove/disable the permission
                await channel.set_permissions(
                    member,
                    attach_files=False,
                    reason=f"Picperms disabled by {ctx.author}"
                )
                action = "disabled"
            else:
                # Enable the permission
                await channel.set_permissions(
                    member,
                    attach_files=True,
                    reason=f"Picperms enabled by {ctx.author}"
                )
                action = "enabled"
            
            # Create success embed
            embed = discord.Embed(
                description=f"{self.approve} **{action}** picperms for {member.mention} in {channel.mention}",
                color=self.purple
            )
            await ctx.send(embed=embed)
            
        except discord.Forbidden:
            # Create error embed for missing permissions
            embed = discord.Embed(
                description=f"{self.deny} I don't have permission to modify channel permissions.",
                color=self.purple
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            # Create error embed for other errors
            embed = discord.Embed(
                description=f"{self.deny} An error occurred: {str(e)}",
                color=self.purple
            )
            await ctx.send(embed=embed)
    
    @picperms.error
    async def picperms_error(self, ctx, error):
        """Error handler for picperms command"""
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                description=f"{self.deny} You need the `Manage Roles` permission to use this command.",
                color=self.purple
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                description=f"{self.deny} Please specify a member. Usage: `{ctx.prefix}picperms <member> [channel]`",
                color=self.purple
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.MemberNotFound):
            embed = discord.Embed(
                description=f"{self.deny} Could not find that member. Please mention them or use their ID.",
                color=self.purple
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.ChannelNotFound):
            embed = discord.Embed(
                description=f"{self.deny} Could not find that channel. Please mention it or use its ID.",
                color=self.purple
            )
            await ctx.send(embed=embed)
        else:
            # Log unexpected errors
            embed = discord.Embed(
                description=f"{self.deny} An error occurred: {str(error)}",
                color=self.purple
            )
            await ctx.send(embed=embed)    
    
    @commands.group(invoke_without_command=True)
    async def autoreact(self, ctx):
        """Manage autoreact triggers."""
        await ctx.send("Usage: `,autoreact add <trigger> <emoji> [--not_strict]` | `,autoreact remove <trigger>` | `,autoreact list`")

    @autoreact.command()
    @commands.has_permissions(manage_guild=True)
    async def add(self, ctx, trigger: str, emoji: str, *, flags=None):
        """Add an autoreact trigger (requires Manage Guild)."""
        strict = 1
        if flags and "--not_strict" in flags:
            strict = 0

        guild_id = ctx.guild.id

        # Check if trigger exists
        self.cursor.execute("SELECT * FROM autoreacts WHERE guild_id = ? AND trigger = ?", (guild_id, trigger.lower()))
        if self.cursor.fetchone():
            return await ctx.send("That trigger already exists in this server.")

        self.cursor.execute(
            "INSERT INTO autoreacts (guild_id, trigger, emoji, strict) VALUES (?, ?, ?, ?)",
            (guild_id, trigger.lower(), emoji, strict)
        )
        self.db.commit()

        await ctx.send(f"✅ Added autoreact for trigger `{trigger}` → {emoji} ({'not strict' if strict == 0 else 'strict'})")

    @autoreact.command()
    @commands.has_permissions(manage_guild=True)
    async def remove(self, ctx, trigger: str):
        """Remove an autoreact trigger (requires Manage Guild)."""
        guild_id = ctx.guild.id

        self.cursor.execute("SELECT * FROM autoreacts WHERE guild_id = ? AND trigger = ?", (guild_id, trigger.lower()))
        if not self.cursor.fetchone():
            return await ctx.send("No such trigger found in this server.")

        self.cursor.execute("DELETE FROM autoreacts WHERE guild_id = ? AND trigger = ?", (guild_id, trigger.lower()))
        self.db.commit()

        await ctx.send(f"❌ Removed autoreact for `{trigger}`.")

    @autoreact.command()
    async def list(self, ctx):
        """List all autoreact triggers for this server."""
        guild_id = ctx.guild.id
        self.cursor.execute("SELECT trigger, emoji, strict FROM autoreacts WHERE guild_id = ?", (guild_id,))
        rows = self.cursor.fetchall()

        if not rows:
            return await ctx.send("No autoreact triggers set for this server.")

        desc = ""
        for trigger, emoji, strict in rows:
            desc += f"**{trigger}** → {emoji} ({'not strict' if strict == 0 else 'strict'})\n"

        embed = discord.Embed(
            title=f"Autoreact Triggers ({len(rows)})",
            description=desc,
            color=self.color
        )
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        guild_id = message.guild.id
        self.cursor.execute("SELECT trigger, emoji, strict FROM autoreacts WHERE guild_id = ?", (guild_id,))
        rows = self.cursor.fetchall()

        for trigger, emoji, strict in rows:
            try:
                if strict == 1 and message.content.lower() == trigger:
                    await message.add_reaction(emoji)
                elif strict == 0 and trigger in message.content.lower():
                    await message.add_reaction(emoji)
            except discord.HTTPException:
                pass

    @commands.command(name="createembed", aliases=["ce"])
    @commands.has_permissions(manage_guild=True)
    async def createembed(self, ctx, *, raw_json: str):
        await ctx.message.delete()
        codeblock_match = re.match(r"^```(?:json)?\s*([\s\S]+?)\s*```$", raw_json.strip(), re.IGNORECASE)
        if codeblock_match:
            raw_json = codeblock_match.group(1)

        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as e:
            return await ctx.send(f"❌ Invalid JSON: `{e}`")

        if not isinstance(data, dict) or "embeds" not in data or not isinstance(data["embeds"], list):
            return await ctx.send("❌ JSON must be an object with an `embeds` key that is a list of embed objects.")

        embeds_to_send = []
        for embed_obj in data["embeds"]:
            if not isinstance(embed_obj, dict):
                continue
            embed = discord.Embed()
            if "title" in embed_obj:
                embed.title = str(embed_obj["title"])
            if "description" in embed_obj:
                embed.description = str(embed_obj["description"])
            if "url" in embed_obj:
                embed.url = str(embed_obj["url"])
            if "color" in embed_obj:
                try:
                    col = int(embed_obj["color"])
                    if col < 0:
                        col = 0
                    elif col > 0xFFFFFF:
                        col = 0xFFFFFF
                    embed.color = discord.Color(col)
                except (TypeError, ValueError):
                    pass
            if "author" in embed_obj and isinstance(embed_obj["author"], dict):
                author = embed_obj["author"]
                name = author.get("name")
                url = author.get("url")
                icon_url = author.get("icon_url") or author.get("iconURL") or author.get("icon")
                try:
                    embed.set_author(name=str(name) if name is not None else discord.Embed.Empty,
                                     url=str(url) if url else None,
                                     icon_url=str(icon_url) if icon_url else None)
                except Exception:
                    pass
            if "thumbnail" in embed_obj:
                thumb = embed_obj["thumbnail"]
                thumb_url = None
                if isinstance(thumb, dict):
                    thumb_url = thumb.get("url")
                elif isinstance(thumb, str):
                    thumb_url = thumb
                if thumb_url:
                    try:
                        embed.set_thumbnail(url=str(thumb_url))
                    except Exception:
                        pass
            if "image" in embed_obj:
                img = embed_obj["image"]
                img_url = None
                if isinstance(img, dict):
                    img_url = img.get("url")
                elif isinstance(img, str):
                    img_url = img
                if img_url:
                    try:
                        embed.set_image(url=str(img_url))
                    except Exception:
                        pass
            if "footer" in embed_obj and isinstance(embed_obj["footer"], dict):
                footer = embed_obj["footer"]
                text = footer.get("text", "")
                icon = footer.get("icon_url") or footer.get("iconURL") or footer.get("icon")
                try:
                    embed.set_footer(text=str(text), icon_url=str(icon) if icon else None)
                except Exception:
                    pass
            if "fields" in embed_obj and isinstance(embed_obj["fields"], list):
                for f in embed_obj["fields"]:
                    try:
                        if not isinstance(f, dict):
                            continue
                        name = str(f.get("name", "\u200b"))
                        value = str(f.get("value", "\u200b"))
                        inline = bool(f.get("inline", False))
                        embed.add_field(name=name, value=value, inline=inline)
                    except Exception:
                        continue
            embeds_to_send.append(embed)
            if len(embeds_to_send) >= 10:
                break
        if not embeds_to_send:
            return await ctx.send("❌ No valid embeds were parsed from that JSON.")
        try:
            await ctx.send(embeds=embeds_to_send)
        except discord.HTTPException as e:
            await ctx.send(f"❌ Failed to send embeds: `{e}`")
    @createembed.error
    async def createembed_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You need the **Manage Guild** permission to use this command.")
        else:
            raise error

    @ban.error
    @unban.error
    @kick.error
    @mute.error
    @unmute.error
    @lock.error
    @unlock.error
    @purge.error
    @botclear.error
    @slowmode.error
    async def moderation_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("<:deny:1429468818094424075> You don't have permission to use this command!")
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send("<:deny:1429468818094424075> I don't have permission to do that!")
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send("<:deny:1429468818094424075> Member not found!")
        elif isinstance(error, commands.UserNotFound):
            await ctx.send("<:deny:1429468818094424075> User not found!")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("<:deny:1429468818094424075> Invalid argument provided!")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"<:deny:1429468818094424075> Missing required argument: {error.param.name}")

async def setup(bot):
    await bot.add_cog(Moderation(bot))