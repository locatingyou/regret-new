import discord
from discord.ext import commands, tasks
import aiosqlite
import os
import sqlite3
from datetime import datetime, timedelta

class TicketView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.current_page = 0
        self.pages = [
            {
                "title": "Command: ticket • Ticket Module",
                "description": "Create and manage support tickets",
                "syntax": f"{ctx.prefix}ticket [subcommand]",
                "example": f"{ctx.prefix}ticket create Bug Report",
                "permissions": "Varies by subcommand",
                "aliases": "t"
            },
            {
                "title": "Command: ticket create • Ticket Module",
                "description": "Create a new support ticket",
                "syntax": f"{ctx.prefix}ticket create [title]",
                "example": f"{ctx.prefix}t create Login Issue",
                "permissions": "None",
                "aliases": "new, open"
            },
            {
                "title": "Command: ticket close • Ticket Module",
                "description": "Close the current ticket channel",
                "syntax": f"{ctx.prefix}ticket close [reason]",
                "example": f"{ctx.prefix}t close Issue resolved",
                "permissions": "Manage Channels or ticket owner",
                "aliases": None
            },
            {
                "title": "Command: ticket add • Ticket Module",
                "description": "Add a member to the ticket",
                "syntax": f"{ctx.prefix}ticket add [member]",
                "example": f"{ctx.prefix}t add @user",
                "permissions": "Manage Channels or ticket owner",
                "aliases": None
            },
            {
                "title": "Command: ticket remove • Ticket Module",
                "description": "Remove a member from the ticket",
                "syntax": f"{ctx.prefix}ticket remove [member]",
                "example": f"{ctx.prefix}t remove @user",
                "permissions": "Manage Channels or ticket owner",
                "aliases": "kick"
            },
            {
                "title": "Command: ticket setup • Ticket Module",
                "description": "Setup the ticket system with a category and support role",
                "syntax": f"{ctx.prefix}ticket setup [category] [support_role]",
                "example": f"{ctx.prefix}t setup",
                "permissions": "Administrator",
                "aliases": None
            },
            {
                "title": "Command: ticket list • Ticket Module",
                "description": "List all open tickets in the server",
                "syntax": f"{ctx.prefix}ticket list",
                "example": f"{ctx.prefix}t list",
                "permissions": "Manage Channels",
                "aliases": "all"
            },
            {
                "title": "Command: ticket claim • Ticket Module",
                "description": "Claim a ticket and assign yourself",
                "syntax": f"{ctx.prefix}ticket claim",
                "example": f"{ctx.prefix}t claim",
                "permissions": "Support role",
                "aliases": None
            }
        ]
    
    def create_embed(self):
        page = self.pages[self.current_page]
        embed = discord.Embed(
            title=page["title"],
            description=page["description"],
            color=0xa6afe7
        )
        
        embed.add_field(
            name="",
            value=f"```js\nSyntax: {page['syntax']}\nExample: {page['example']}\n```",
            inline=False
        )
        
        embed.add_field(
            name="Permissions",
            value=page["permissions"],
            inline=False
        )
        
        if page["aliases"]:
            embed.set_footer(text=f"Aliases: {page['aliases']} • Page {self.current_page + 1}/{len(self.pages)}")
        else:
            embed.set_footer(text=f"Page {self.current_page + 1}/{len(self.pages)}")
        
        return embed
    
    @discord.ui.button(label="", style=discord.ButtonStyle.secondary, emoji="<:left:1429466193139339355>")
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This is not your menu!", ephemeral=True)
            return
        
        self.current_page = (self.current_page - 1) % len(self.pages)
        await interaction.response.edit_message(embed=self.create_embed(), view=self)
    
    @discord.ui.button(label="", style=discord.ButtonStyle.secondary, emoji="<:right:1429466191784706088>")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This is not your menu!", ephemeral=True)
            return
        
        self.current_page = (self.current_page + 1) % len(self.pages)
        await interaction.response.edit_message(embed=self.create_embed(), view=self)
    
    @discord.ui.button(label="", style=discord.ButtonStyle.secondary, emoji="<:close:1429466190408974496>")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This is not your menu!", ephemeral=True)
            return
        
        await interaction.message.delete()
    
    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(view=self)
        except:
            pass

class TicketModal(discord.ui.Modal, title="Create a Ticket"):
    ticket_title = discord.ui.TextInput(
        label="Ticket Title",
        placeholder="Enter a brief description of your issue...",
        required=True,
        max_length=100
    )
    
    description = discord.ui.TextInput(
        label="Description",
        placeholder="Provide more details about your issue...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000
    )
    
    def __init__(self, cog):
        super().__init__()
        self.cog = cog
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        config = await self.cog.get_ticket_config(interaction.guild.id)
        
        if not config:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Ticket system is not set up!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)
        
        category = interaction.guild.get_channel(config['category_id'])
        support_role = interaction.guild.get_role(config['support_role_id'])
        
        if not category:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Ticket category not found!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)
        
        ticket_number = await self.cog.increment_ticket_counter(interaction.guild.id)
        
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        
        ticket_channel = await interaction.guild.create_text_channel(
            name=f"ticket-{ticket_number}",
            category=category,
            overwrites=overwrites
        )
        
        ticket_id = await self.cog.create_ticket_db(
            interaction.guild.id,
            ticket_channel.id,
            interaction.user.id,
            ticket_number,
            str(self.ticket_title)
        )
        
        await self.cog.log_ticket_action(ticket_id, interaction.user.id, "created", str(self.ticket_title))
        
        embed = discord.Embed(
            title=f"Ticket #{ticket_number}",
            description=f"**Title:** {self.ticket_title}\n**Description:** {self.description}\n**Created by:** {interaction.user.mention}",
            color=discord.Color.from_str("#a6afe7")
        )
        embed.add_field(
            name="Support",
            value="A support team member will be with you shortly.\nTo close this ticket, use the close button or command.",
            inline=False
        )
        
        await ticket_channel.send(content=interaction.user.mention, embed=embed)
        
        confirm_embed = discord.Embed(
            description=f"<:approve:1429468807348486305> Your ticket has been created! {ticket_channel.mention}",
            color=discord.Color.from_str("#a6afe7")
        )
        await interaction.followup.send(embed=confirm_embed, ephemeral=True)


class TicketPanelView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog
    
    @discord.ui.button(label="Create Ticket", style=discord.ButtonStyle.primary, emoji="🎫", custom_id="create_ticket_button")
    async def create_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = TicketModal(self.cog)
        await interaction.response.send_modal(modal)


class AutoRoleView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.current_page = 0
        self.pages = [
            {
                "title": "Command: autorole • AutoRole Module",
                "description": "Automatically assign roles to new members",
                "syntax": f"{ctx.prefix}autorole [subcommand]",
                "example": f"{ctx.prefix}autorole add @role",
                "permissions": "Manage Roles",
                "aliases": "ar"
            },
            {
                "title": "Command: autorole add • AutoRole Module",
                "description": "Add a role to be automatically assigned to new members",
                "syntax": f"{ctx.prefix}autorole add [role]",
                "example": f"{ctx.prefix}ar add @Member",
                "permissions": "Manage Roles",
                "aliases": None
            },
            {
                "title": "Command: autorole remove • AutoRole Module",
                "description": "Remove a role from auto assignment",
                "syntax": f"{ctx.prefix}autorole remove [role]",
                "example": f"{ctx.prefix}ar remove @Member",
                "permissions": "Manage Roles",
                "aliases": "delete, del"
            },
            {
                "title": "Command: autorole list • AutoRole Module",
                "description": "List all auto roles for this server",
                "syntax": f"{ctx.prefix}autorole list",
                "example": f"{ctx.prefix}ar list",
                "permissions": "Manage Roles",
                "aliases": "show"
            },
            {
                "title": "Command: autorole clear • AutoRole Module",
                "description": "Remove all auto roles from this server",
                "syntax": f"{ctx.prefix}autorole clear",
                "example": f"{ctx.prefix}ar clear",
                "permissions": "Manage Roles",
                "aliases": "reset"
            }
        ]
    
    def create_embed(self):
        page = self.pages[self.current_page]
        embed = discord.Embed(
            title=page["title"],
            description=page["description"],
            color=0xa6afe7
        )
        
        embed.add_field(
            name="",
            value=f"```js\nSyntax: {page['syntax']}\nExample: {page['example']}\n```",
            inline=False
        )
        
        embed.add_field(
            name="Permissions",
            value=page["permissions"],
            inline=False
        )
        
        if page["aliases"]:
            embed.set_footer(text=f"Aliases: {page['aliases']} • Page {self.current_page + 1}/{len(self.pages)}")
        else:
            embed.set_footer(text=f"Page {self.current_page + 1}/{len(self.pages)}")
        
        return embed
    
    @discord.ui.button(label="", style=discord.ButtonStyle.secondary, emoji="<:left:1429466193139339355>")
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This is not your menu!", ephemeral=True)
            return
        
        self.current_page = (self.current_page - 1) % len(self.pages)
        await interaction.response.edit_message(embed=self.create_embed(), view=self)
    
    @discord.ui.button(label="", style=discord.ButtonStyle.secondary, emoji="<:right:1429466191784706088>")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This is not your menu!", ephemeral=True)
            return
        
        self.current_page = (self.current_page + 1) % len(self.pages)
        await interaction.response.edit_message(embed=self.create_embed(), view=self)
    
    @discord.ui.button(label="", style=discord.ButtonStyle.secondary, emoji="<:close:1429466190408974496>")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This is not your menu!", ephemeral=True)
            return
        
        await interaction.message.delete()
    
    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(view=self)
        except:
            pass


class VoiceMasterView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.current_page = 0
        self.pages = [
            {
                "title": "Command: voicemaster • VoiceMaster Module",
                "description": "Administrator and channel management commands",
                "syntax": f"{ctx.prefix}voicemaster [subcommand]",
                "example": f"{ctx.prefix}voicemaster setup",
                "permissions": "Varies by subcommand",
                "aliases": "vm"
            },
            {
                "title": "Command: voicemaster setup • VoiceMaster Module",
                "description": "Setup VoiceMaster with a join-to-create channel",
                "syntax": f"{ctx.prefix}voicemaster setup [category]",
                "example": f"{ctx.prefix}voicemaster setup",
                "permissions": "Administrator",
                "aliases": None
            },
            {
                "title": "Command: voicemaster remove • VoiceMaster Module",
                "description": "Remove VoiceMaster configuration",
                "syntax": f"{ctx.prefix}voicemaster remove",
                "example": f"{ctx.prefix}voicemaster remove",
                "permissions": "Administrator",
                "aliases": None
            },
            {
                "title": "Command: voicemaster lock • VoiceMaster Module",
                "description": "Lock your temporary voice channel",
                "syntax": f"{ctx.prefix}voicemaster lock",
                "example": f"{ctx.prefix}vm lock",
                "permissions": "Must own the voice channel",
                "aliases": None
            },
            {
                "title": "Command: voicemaster unlock • VoiceMaster Module",
                "description": "Unlock your temporary voice channel",
                "syntax": f"{ctx.prefix}voicemaster unlock",
                "example": f"{ctx.prefix}vm unlock",
                "permissions": "Must own the voice channel",
                "aliases": None
            },
            {
                "title": "Command: voicemaster rename • VoiceMaster Module",
                "description": "Rename your temporary voice channel",
                "syntax": f"{ctx.prefix}voicemaster rename [name]",
                "example": f"{ctx.prefix}vm rename My Channel",
                "permissions": "Must own the voice channel",
                "aliases": None
            },
            {
                "title": "Command: voicemaster limit • VoiceMaster Module",
                "description": "Set user limit for your temporary voice channel",
                "syntax": f"{ctx.prefix}voicemaster limit [number]",
                "example": f"{ctx.prefix}vm limit 5",
                "permissions": "Must own the voice channel",
                "aliases": None
            },
            {
                "title": "Command: voicemaster permit • VoiceMaster Module",
                "description": "Allow a user to join your locked voice channel",
                "syntax": f"{ctx.prefix}voicemaster permit [member]",
                "example": f"{ctx.prefix}vm permit @user",
                "permissions": "Must own the voice channel",
                "aliases": None
            },
            {
                "title": "Command: voicemaster reject • VoiceMaster Module",
                "description": "Prevent a user from joining your voice channel",
                "syntax": f"{ctx.prefix}voicemaster reject [member]",
                "example": f"{ctx.prefix}vm reject @user",
                "permissions": "Must own the voice channel",
                "aliases": None
            },
            {
                "title": "Command: voicemaster claim • VoiceMaster Module",
                "description": "Claim ownership of a voice channel if the owner left",
                "syntax": f"{ctx.prefix}voicemaster claim",
                "example": f"{ctx.prefix}vm claim",
                "permissions": "Must be in the voice channel",
                "aliases": None
            }
        ]
    
    def create_embed(self):
        page = self.pages[self.current_page]
        embed = discord.Embed(
            title=page["title"],
            description=page["description"],
            color=0xa6afe7
        )
        
        embed.add_field(
            name="",
            value=f"```js\nSyntax: {page['syntax']}\nExample: {page['example']}\n```",
            inline=False
        )
        
        embed.add_field(
            name="Permissions",
            value=page["permissions"],
            inline=False
        )
        
        if page["aliases"]:
            embed.set_footer(text=f"Aliases: {page['aliases']} • Page {self.current_page + 1}/{len(self.pages)}")
        else:
            embed.set_footer(text=f"Page {self.current_page + 1}/{len(self.pages)}")
        
        return embed
    
    @discord.ui.button(label="", style=discord.ButtonStyle.secondary, emoji="<:left:1429466193139339355>")
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This is not your menu!", ephemeral=True)
            return
        
        self.current_page = (self.current_page - 1) % len(self.pages)
        await interaction.response.edit_message(embed=self.create_embed(), view=self)
    
    @discord.ui.button(label="", style=discord.ButtonStyle.secondary, emoji="<:right:1429466191784706088>")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This is not your menu!", ephemeral=True)
            return
        
        self.current_page = (self.current_page + 1) % len(self.pages)
        await interaction.response.edit_message(embed=self.create_embed(), view=self)
    
    @discord.ui.button(label="", style=discord.ButtonStyle.secondary, emoji="<:close:1429466190408974496>")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This is not your menu!", ephemeral=True)
            return
        
        await interaction.message.delete()
    
    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(view=self)
        except:
            pass

class JailView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.current_page = 0
        self.pages = [
            {
                "title": "Command: jail • Jail Module",
                "description": "Jail a member temporarily or indefinitely",
                "syntax": f"{ctx.prefix}jail [member] [duration] [reason]",
                "example": f"{ctx.prefix}jail @user 1h Spamming",
                "permissions": "Moderate Members",
                "aliases": None
            },
            {
                "title": "Command: jail setup • Jail Module",
                "description": "Setup the jail system (creates jail role and channel)",
                "syntax": f"{ctx.prefix}jail setup",
                "example": f"{ctx.prefix}jail setup",
                "permissions": "Administrator",
                "aliases": None
            },
            {
                "title": "Command: unjail • Jail Module",
                "description": "Unjail a member and restore their roles",
                "syntax": f"{ctx.prefix}unjail [member]",
                "example": f"{ctx.prefix}unjail @user",
                "permissions": "Moderate Members",
                "aliases": None
            },
            {
                "title": "Command: jailinfo • Jail Module",
                "description": "Get information about jailed members",
                "syntax": f"{ctx.prefix}jailinfo [member]",
                "example": f"{ctx.prefix}jailinfo @user",
                "permissions": "Moderate Members",
                "aliases": None
            }
        ]
    
    def create_embed(self):
        page = self.pages[self.current_page]
        embed = discord.Embed(
            title=page["title"],
            description=page["description"],
            color=0xa6afe7
        )
        
        embed.add_field(
            name="",
            value=f"```js\nSyntax: {page['syntax']}\nExample: {page['example']}\n```",
            inline=False
        )
        
        embed.add_field(
            name="Permissions",
            value=page["permissions"],
            inline=False
        )
        
        if page["aliases"]:
            embed.set_footer(text=f"Aliases: {page['aliases']} • Page {self.current_page + 1}/{len(self.pages)}")
        else:
            embed.set_footer(text=f"Page {self.current_page + 1}/{len(self.pages)}")
        
        return embed
    
    @discord.ui.button(label="", style=discord.ButtonStyle.secondary, emoji="<:left:1429466193139339355>")
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This is not your menu!", ephemeral=True)
            return
        
        self.current_page = (self.current_page - 1) % len(self.pages)
        await interaction.response.edit_message(embed=self.create_embed(), view=self)
    
    @discord.ui.button(label="", style=discord.ButtonStyle.secondary, emoji="<:right:1429466191784706088>")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This is not your menu!", ephemeral=True)
            return
        
        self.current_page = (self.current_page + 1) % len(self.pages)
        await interaction.response.edit_message(embed=self.create_embed(), view=self)
    
    @discord.ui.button(label="", style=discord.ButtonStyle.secondary, emoji="<:close:1429466190408974496>")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This is not your menu!", ephemeral=True)
            return
        
        await interaction.message.delete()
    
    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(view=self)
        except:
            pass

# ==================== MAIN COG ====================

class Configuration(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "data/configuration.db"
        self.temp_channels = {}
        self.purple = discord.Color.from_str("#a6afe7")
        self.approve = "<:approve:1429468807348486305>"
        self.deny = "<:deny:1429468818094424075>"
        self.bot.loop.create_task(self.setup_db())
        self.check_jail_timers.start()
    
    def cog_unload(self):
        """Cancel tasks when cog is unloaded"""
        self.check_jail_timers.cancel()
    
    async def cog_load(self):
        """Add persistent view when cog loads"""
        self.bot.add_view(TicketPanelView(self))
    
    async def setup_db(self):
        """Initialize the database"""
        os.makedirs("data", exist_ok=True)
        
        async with aiosqlite.connect(self.db_path) as db:
            # Voicemaster configuration
            await db.execute("""
                CREATE TABLE IF NOT EXISTS voicemaster_config (
                    guild_id INTEGER PRIMARY KEY,
                    join_channel_id INTEGER,
                    category_id INTEGER,
                    channel_name TEXT DEFAULT '🎤 {user}''s channel'
                )
            """)
            
            # Temporary voice channels
            await db.execute("""
                CREATE TABLE IF NOT EXISTS temp_channels (
                    channel_id INTEGER PRIMARY KEY,
                    guild_id INTEGER,
                    owner_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Autoroles
            await db.execute("""
                CREATE TABLE IF NOT EXISTS autoroles (
                    guild_id TEXT NOT NULL,
                    role_id INTEGER NOT NULL,
                    PRIMARY KEY (guild_id, role_id)
                )
            """)
            
            # Ticket configuration
            await db.execute("""
                CREATE TABLE IF NOT EXISTS ticket_config (
                    guild_id INTEGER PRIMARY KEY,
                    category_id INTEGER,
                    support_role_id INTEGER,
                    ticket_counter INTEGER DEFAULT 0,
                    panel_channel_id INTEGER,
                    panel_message_id INTEGER
                )
            """)
            
            # Tickets
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    ticket_number INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT DEFAULT 'open',
                    claimed_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    closed_at TIMESTAMP
                )
            """)
            
            # Ticket logs
            await db.execute("""
                CREATE TABLE IF NOT EXISTS ticket_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    details TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (ticket_id) REFERENCES tickets (id)
                )
            """)
            
            # Jailed users
            await db.execute("""
                CREATE TABLE IF NOT EXISTS jailed_users (
                    guild_id INTEGER,
                    user_id INTEGER,
                    roles TEXT,
                    jailed_at INTEGER,
                    release_time INTEGER,
                    reason TEXT,
                    jailed_by INTEGER,
                    PRIMARY KEY (guild_id, user_id)
                )
            """)
            
            # Jailed users
            await db.execute("""
                CREATE TABLE IF NOT EXISTS aliases (
                    guild_id INTEGER NOT NULL,
                    alias TEXT NOT NULL,
                    real_command TEXT NOT NULL,
                    PRIMARY KEY (guild_id, alias)
                )
            """)
            
            await db.commit()
    
    
    # ==================== VOICEMASTER METHODS ====================
    
    async def get_guild_config(self, guild_id):
        """Get voicemaster config for a specific guild"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT join_channel_id, category_id, channel_name FROM voicemaster_config WHERE guild_id = ?",
                (guild_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        'join_channel_id': row[0],
                        'category_id': row[1],
                        'channel_name': row[2]
                    }
                return None
    
    async def set_guild_config(self, guild_id, join_channel_id, category_id, channel_name):
        """Set voicemaster config for a guild"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO voicemaster_config (guild_id, join_channel_id, category_id, channel_name)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    join_channel_id = excluded.join_channel_id,
                    category_id = excluded.category_id,
                    channel_name = excluded.channel_name
            """, (guild_id, join_channel_id, category_id, channel_name))
            await db.commit()
    
    async def remove_guild_config(self, guild_id):
        """Remove voicemaster config for a guild"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM voicemaster_config WHERE guild_id = ?", (guild_id,))
            await db.commit()
    
    async def add_temp_channel(self, channel_id, guild_id, owner_id):
        """Add a temporary channel to the database"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO temp_channels (channel_id, guild_id, owner_id) VALUES (?, ?, ?)",
                (channel_id, guild_id, owner_id)
            )
            await db.commit()
        self.temp_channels[channel_id] = owner_id
    
    async def remove_temp_channel(self, channel_id):
        """Remove a temporary channel from the database"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM temp_channels WHERE channel_id = ?", (channel_id,))
            await db.commit()
        if channel_id in self.temp_channels:
            del self.temp_channels[channel_id]
    
    async def get_temp_channel_owner(self, channel_id):
        """Get the owner of a temporary channel"""
        if channel_id in self.temp_channels:
            return self.temp_channels[channel_id]
        
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT owner_id FROM temp_channels WHERE channel_id = ?",
                (channel_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    self.temp_channels[channel_id] = row[0]
                    return row[0]
                return None
    
    # ==================== AUTOROLE METHODS ====================
    
    async def get_autoroles(self, guild_id):
        """Get all autorole IDs for a guild"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT role_id FROM autoroles WHERE guild_id = ?",
                (str(guild_id),)
            ) as cursor:
                return [row[0] for row in await cursor.fetchall()]
    
    async def add_autorole(self, guild_id, role_id):
        """Add an autorole for a guild"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute(
                    "INSERT INTO autoroles (guild_id, role_id) VALUES (?, ?)",
                    (str(guild_id), role_id)
                )
                await db.commit()
                return True
            except aiosqlite.IntegrityError:
                return False
    
    async def remove_autorole(self, guild_id, role_id):
        """Remove an autorole for a guild"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM autoroles WHERE guild_id = ? AND role_id = ?",
                (str(guild_id), role_id)
            )
            await db.commit()
            return cursor.rowcount > 0
    
    async def clear_autoroles(self, guild_id):
        """Clear all autoroles for a guild"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM autoroles WHERE guild_id = ?",
                (str(guild_id),)
            )
            await db.commit()
            return cursor.rowcount > 0
    
    # ==================== TICKET METHODS ====================
    
    async def get_ticket_config(self, guild_id):
        """Get ticket configuration for a guild"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT category_id, support_role_id, ticket_counter, panel_channel_id, panel_message_id FROM ticket_config WHERE guild_id = ?",
                (guild_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        'category_id': row[0],
                        'support_role_id': row[1],
                        'ticket_counter': row[2],
                        'panel_channel_id': row[3],
                        'panel_message_id': row[4]
                    }
                return None
    
    async def set_ticket_config(self, guild_id, category_id, support_role_id, panel_channel_id=None, panel_message_id=None):
        """Set ticket configuration for a guild"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO ticket_config (guild_id, category_id, support_role_id, ticket_counter, panel_channel_id, panel_message_id)
                VALUES (?, ?, ?, 0, ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    category_id = excluded.category_id,
                    support_role_id = excluded.support_role_id,
                    panel_channel_id = excluded.panel_channel_id,
                    panel_message_id = excluded.panel_message_id
            """, (guild_id, category_id, support_role_id, panel_channel_id, panel_message_id))
            await db.commit()
    
    async def increment_ticket_counter(self, guild_id):
        """Increment and return the next ticket number"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE ticket_config SET ticket_counter = ticket_counter + 1 WHERE guild_id = ?",
                (guild_id,)
            )
            await db.commit()
            
            async with db.execute(
                "SELECT ticket_counter FROM ticket_config WHERE guild_id = ?",
                (guild_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 1
    
    async def create_ticket_db(self, guild_id, channel_id, user_id, ticket_number, title):
        """Create a ticket in the database"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO tickets (guild_id, channel_id, user_id, ticket_number, title, status)
                VALUES (?, ?, ?, ?, ?, 'open')
            """, (guild_id, channel_id, user_id, ticket_number, title))
            await db.commit()
            return cursor.lastrowid
    
    async def get_ticket_by_channel(self, channel_id):
        """Get ticket info by channel ID"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT id, guild_id, user_id, ticket_number, title, status, claimed_by FROM tickets WHERE channel_id = ? AND status = 'open'",
                (channel_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        'id': row[0],
                        'guild_id': row[1],
                        'user_id': row[2],
                        'ticket_number': row[3],
                        'title': row[4],
                        'status': row[5],
                        'claimed_by': row[6]
                    }
                return None
    
    async def close_ticket_db(self, ticket_id):
        """Close a ticket in the database"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE tickets SET status = 'closed', closed_at = CURRENT_TIMESTAMP WHERE id = ?",
                (ticket_id,)
            )
            await db.commit()
    
    async def claim_ticket_db(self, ticket_id, user_id):
        """Claim a ticket"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE tickets SET claimed_by = ? WHERE id = ?",
                (user_id, ticket_id)
            )
            await db.commit()
    
    async def get_all_open_tickets(self, guild_id):
        """Get all open tickets for a guild"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT id, channel_id, user_id, ticket_number, title, claimed_by FROM tickets WHERE guild_id = ? AND status = 'open'",
                (guild_id,)
            ) as cursor:
                return await cursor.fetchall()
    
    async def log_ticket_action(self, ticket_id, user_id, action, details=None):
        """Log a ticket action"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO ticket_logs (ticket_id, user_id, action, details) VALUES (?, ?, ?, ?)",
                (ticket_id, user_id, action, details)
            )
            await db.commit()
    
    # ==================== JAIL METHODS ====================
    
    def get_jail_role(self, guild):
        """Get the jail role"""
        return discord.utils.get(guild.roles, name="Jailed")
    
    async def create_jail_role(self, guild):
        """Create the jail role with proper permissions"""
        try:
            jail_role = await guild.create_role(
                name="Jailed",
                color=discord.Color.dark_gray(),
                reason="Jail system role creation"
            )
            
            # Set permissions for all channels
            for channel in guild.channels:
                await channel.set_permissions(
                    jail_role,
                    send_messages=False,
                    add_reactions=False,
                    speak=False,
                    connect=False,
                    view_channel=False
                )
            
            return jail_role
        except Exception as e:
            print(f"Error creating jail role: {e}")
            return None
    
    async def setup_jail_channel(self, guild, jail_role):
        """Setup or get the jail channel"""
        jail_channel = discord.utils.get(guild.text_channels, name="jail")
        
        if not jail_channel:
            try:
                jail_channel = await guild.create_text_channel(
                    name="jail",
                    reason="Jail system channel creation"
                )
                
                await jail_channel.set_permissions(
                    guild.default_role,
                    view_channel=False
                )
                await jail_channel.set_permissions(
                    jail_role,
                    view_channel=True,
                    send_messages=True,
                    read_messages=True,
                    read_message_history=True
                )
            except Exception as e:
                print(f"Error creating jail channel: {e}")
                return None
        
        return jail_channel
    
    def parse_duration(self, duration_str):
        """Parse duration string (e.g., '1h', '30m', '1d') to timestamp"""
        try:
            time_units = {
                's': 1,
                'm': 60,
                'h': 3600,
                'd': 86400,
                'w': 604800
            }
            
            unit = duration_str[-1].lower()
            if unit not in time_units:
                return None
            
            amount = int(duration_str[:-1])
            seconds = amount * time_units[unit]
            
            release_time = datetime.utcnow() + timedelta(seconds=seconds)
            return int(release_time.timestamp())
        except:
            return None
    
    @tasks.loop(minutes=1)
    async def check_jail_timers(self):
        """Check for expired jail timers"""
        current_time = int(datetime.utcnow().timestamp())
        
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                'SELECT * FROM jailed_users WHERE release_time IS NOT NULL AND release_time <= ?',
                (current_time,)
            ) as cursor:
                expired = await cursor.fetchall()
        
        for jail_data in expired:
            guild = self.bot.get_guild(jail_data[0])
            if guild:
                member_to_unjail = guild.get_member(jail_data[1])
                if member_to_unjail:
                    try:
                        # Remove jail role
                        jail_role = self.get_jail_role(guild)
                        if jail_role and jail_role in member_to_unjail.roles:
                            await member_to_unjail.remove_roles(jail_role, reason="Jail time expired")
                        
                        # Restore roles
                        roles_str = jail_data[2]
                        if roles_str:
                            role_ids = roles_str.split(',')
                            roles_to_add = []
                            for role_id in role_ids:
                                role = guild.get_role(int(role_id))
                                if role:
                                    roles_to_add.append(role)
                            
                            if roles_to_add:
                                await member_to_unjail.add_roles(*roles_to_add, reason="Jail time expired")
                        
                        # Remove from database
                        async with aiosqlite.connect(self.db_path) as db:
                            await db.execute(
                                'DELETE FROM jailed_users WHERE guild_id = ? AND user_id = ?',
                                (guild.id, member_to_unjail.id)
                            )
                            await db.commit()
                        
                        # Notify in jail channel
                        jail_channel = discord.utils.get(guild.text_channels, name="jail")
                        if jail_channel:
                            embed = discord.Embed(
                                description=f"{self.approve} {member_to_unjail.mention} has been automatically unjailed.",
                                color=self.purple
                            )
                            await jail_channel.send(embed=embed)
                    
                    except Exception as e:
                        print(f"Error auto-unjailing {member_to_unjail}: {e}")
    
    @check_jail_timers.before_loop
    async def before_check_jail_timers(self):
        await self.bot.wait_until_ready()

        
    def add_alias(self, guild_id: int, alias: str, real_command: str):
        """Add or update an alias in the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO aliases (guild_id, alias, real_command)
            VALUES (?, ?, ?)
        ''', (guild_id, alias, real_command))
        conn.commit()
        conn.close()
    
    def remove_alias(self, guild_id: int, alias: str) -> bool:
        """Remove an alias from the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            DELETE FROM aliases WHERE guild_id = ? AND alias = ?
        ''', (guild_id, alias))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return deleted
    
    def get_alias(self, guild_id: int, alias: str) -> str:
        """Get the real command for an alias"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT real_command FROM aliases WHERE guild_id = ? AND alias = ?
        ''', (guild_id, alias))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    
    def get_all_aliases(self, guild_id: int) -> list:
        """Get all aliases for a guild"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT alias, real_command FROM aliases WHERE guild_id = ?
            ORDER BY alias
        ''', (guild_id,))
        results = cursor.fetchall()
        conn.close()
        return results
    
    # ==================== EVENT LISTENERS ====================
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Handle voice state updates for join-to-create"""
        # User joined a voice channel
        if after.channel and after.channel != before.channel:
            config = await self.get_guild_config(member.guild.id)
            
            if config and after.channel.id == config['join_channel_id']:
                category = self.bot.get_channel(config['category_id'])
                if not category:
                    return
                
                channel_name = config['channel_name'].replace('{user}', member.display_name)
                
                try:
                    temp_channel = await member.guild.create_voice_channel(
                        name=channel_name,
                        category=category,
                        reason=f"VoiceMaster: Created by {member}"
                    )
                    
                    await member.move_to(temp_channel)
                    await self.add_temp_channel(temp_channel.id, member.guild.id, member.id)
                    
                except discord.Forbidden:
                    pass
                except discord.HTTPException:
                    pass
        
        # User left a voice channel
        if before.channel and before.channel != after.channel:
            owner_id = await self.get_temp_channel_owner(before.channel.id)
            
            if owner_id:
                if len(before.channel.members) == 0:
                    try:
                        await before.channel.delete(reason="VoiceMaster: Empty temporary channel")
                        await self.remove_temp_channel(before.channel.id)
                    except discord.Forbidden:
                        pass
                    except discord.HTTPException:
                        pass
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Give auto roles to new members"""
        role_ids = await self.get_autoroles(member.guild.id)
        
        if not role_ids:
            return
        
        roles_to_add = []
        for role_id in role_ids:
            role = member.guild.get_role(role_id)
            if role and role < member.guild.me.top_role:
                roles_to_add.append(role)
        
        if roles_to_add:
            try:
                await member.add_roles(*roles_to_add, reason="Auto role")
            except discord.Forbidden:
                pass
            except discord.HTTPException:
                pass
    
    # ==================== TICKET COMMANDS ====================
    
    @commands.group(name="ticket", aliases=["t"], invoke_without_command=True)
    async def ticket(self, ctx):
        """Ticket system commands"""
        view = TicketView(ctx)
        view.message = await ctx.send(embed=view.create_embed(), view=view)
    
    @ticket.command(name="setup")
    @commands.has_permissions(administrator=True)
    async def ticket_setup(self, ctx, category: discord.CategoryChannel = None, support_role: discord.Role = None):
        """Setup the ticket system"""
        if not category:
            category = await ctx.guild.create_category(name="📩 Tickets")
        
        if not support_role:
            support_role = discord.utils.get(ctx.guild.roles, name="Support")
            if not support_role:
                support_role = await ctx.guild.create_role(name="Support", color=discord.Color.blue())
        
        # Create panel channel
        panel_channel = await ctx.guild.create_text_channel(
            name="panel",
            category=category,
            topic="Click the button below to create a support ticket"
        )
        
        # Create panel embed
        panel_embed = discord.Embed(
            title="🎫 Support Tickets",
            description="Need help? Click the button below to create a support ticket!\n\nOur support team will assist you as soon as possible.",
            color=discord.Color.from_str("#a6afe7")
        )
        panel_embed.add_field(
            name="How to create a ticket",
            value="1. Click the **Create Ticket** button below\n2. Fill out the form with your issue details\n3. Wait for a support team member to assist you",
            inline=False
        )
        panel_embed.set_footer(text=f"{ctx.guild.name} Support System")
        
        # Send panel message with button
        view = TicketPanelView(self)
        panel_message = await panel_channel.send(embed=panel_embed, view=view)
        
        # Save configuration
        await self.set_ticket_config(
            ctx.guild.id, 
            category.id, 
            support_role.id, 
            panel_channel.id, 
            panel_message.id
        )
        
        embed = discord.Embed(
            title="<:approve:1429468807348486305> Ticket System Setup Complete",
            description="The ticket system has been configured!",
            color=discord.Color.from_str("#a6afe7")
        )
        
        embed.add_field(name="Category", value=category.mention, inline=False)
        embed.add_field(name="Support Role", value=support_role.mention, inline=False)
        embed.add_field(name="Panel Channel", value=panel_channel.mention, inline=False)
        
        await ctx.send(embed=embed)
    
    @ticket.command(name="create", aliases=["new", "open"])
    async def ticket_create(self, ctx, *, title: str):
        """Create a new ticket"""
        config = await self.get_ticket_config(ctx.guild.id)
        
        if not config:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Ticket system is not set up! Ask an admin to run the setup command.",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        category = ctx.guild.get_channel(config['category_id'])
        support_role = ctx.guild.get_role(config['support_role_id'])
        
        if not category:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Ticket category not found! Please run setup again.",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        ticket_number = await self.increment_ticket_counter(ctx.guild.id)
        
        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            ctx.author: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            ctx.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        
        ticket_channel = await ctx.guild.create_text_channel(
            name=f"ticket-{ticket_number}",
            category=category,
            overwrites=overwrites
        )
        
        ticket_id = await self.create_ticket_db(
            ctx.guild.id,
            ticket_channel.id,
            ctx.author.id,
            ticket_number,
            title
        )
        
        await self.log_ticket_action(ticket_id, ctx.author.id, "created", title)
        
        embed = discord.Embed(
            title=f"Ticket #{ticket_number}",
            description=f"**Title:** {title}\n**Created by:** {ctx.author.mention}",
            color=discord.Color.from_str("#a6afe7")
        )
        embed.add_field(
            name="Support",
            value=f"A support team member will be with you shortly.\nTo close this ticket, use `{ctx.prefix}ticket close`",
            inline=False
        )
        
        await ticket_channel.send(content=ctx.author.mention, embed=embed)
        
        confirm_embed = discord.Embed(
            description=f"<:approve:1429468807348486305> Your ticket has been created! {ticket_channel.mention}",
            color=discord.Color.from_str("#a6afe7")
        )
        await ctx.send(embed=confirm_embed)
    
    @ticket.command(name="close")
    async def ticket_close(self, ctx, *, reason: str = "No reason provided"):
        """Close a ticket"""
        ticket = await self.get_ticket_by_channel(ctx.channel.id)
        
        if not ticket:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> This is not a ticket channel!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        if ctx.author.id != ticket['user_id'] and not ctx.author.guild_permissions.manage_channels:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> You don't have permission to close this ticket!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        await self.close_ticket_db(ticket['id'])
        await self.log_ticket_action(ticket['id'], ctx.author.id, "closed", reason)
        
        embed = discord.Embed(
            title="Ticket Closed",
            description=f"**Closed by:** {ctx.author.mention}\n**Reason:** {reason}",
            color=discord.Color.from_str("#a6afe7")
        )
        embed.set_footer(text="This channel will be deleted in 5 seconds...")
        
        await ctx.send(embed=embed)
        await discord.utils.sleep_until(discord.utils.utcnow() + timedelta(seconds=5))
        await ctx.channel.delete(reason=f"Ticket closed by {ctx.author}")
    
    @ticket.command(name="add")
    async def ticket_add(self, ctx, member: discord.Member):
        """Add a member to the ticket"""
        ticket = await self.get_ticket_by_channel(ctx.channel.id)
        
        if not ticket:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> This is not a ticket channel!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        if ctx.author.id != ticket['user_id'] and not ctx.author.guild_permissions.manage_channels:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> You don't have permission to add members!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        await ctx.channel.set_permissions(member, read_messages=True, send_messages=True)
        await self.log_ticket_action(ticket['id'], ctx.author.id, "added_member", f"Added {member.id}")
        
        embed = discord.Embed(
            description=f"<:approve:1429468807348486305> {member.mention} has been added to the ticket!",
            color=discord.Color.from_str("#a6afe7")
        )
        await ctx.send(embed=embed)
    
    @ticket.command(name="remove", aliases=["kick"])
    async def ticket_remove(self, ctx, member: discord.Member):
        """Remove a member from the ticket"""
        ticket = await self.get_ticket_by_channel(ctx.channel.id)
        
        if not ticket:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> This is not a ticket channel!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        if ctx.author.id != ticket['user_id'] and not ctx.author.guild_permissions.manage_channels:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> You don't have permission to remove members!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        await ctx.channel.set_permissions(member, overwrite=None)
        await self.log_ticket_action(ticket['id'], ctx.author.id, "removed_member", f"Removed {member.id}")
        
        embed = discord.Embed(
            description=f"<:approve:1429468807348486305> {member.mention} has been removed from the ticket!",
            color=discord.Color.from_str("#a6afe7")
        )
        await ctx.send(embed=embed)
    
    @ticket.command(name="claim")
    async def ticket_claim(self, ctx):
        """Claim a ticket"""
        ticket = await self.get_ticket_by_channel(ctx.channel.id)
        
        if not ticket:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> This is not a ticket channel!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        config = await self.get_ticket_config(ctx.guild.id)
        support_role = ctx.guild.get_role(config['support_role_id']) if config else None
        
        if support_role and support_role not in ctx.author.roles and not ctx.author.guild_permissions.manage_channels:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> You need the support role to claim tickets!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        if ticket['claimed_by']:
            claimer = ctx.guild.get_member(ticket['claimed_by'])
            embed = discord.Embed(
                description=f"<:deny:1429468818094424075> This ticket is already claimed by {claimer.mention if claimer else 'someone'}!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        await self.claim_ticket_db(ticket['id'], ctx.author.id)
        await self.log_ticket_action(ticket['id'], ctx.author.id, "claimed")
        
        embed = discord.Embed(
            description=f"<:approve:1429468807348486305> {ctx.author.mention} has claimed this ticket!",
            color=discord.Color.from_str("#a6afe7")
        )
        await ctx.send(embed=embed)
    
    @ticket.command(name="list", aliases=["all"])
    @commands.has_permissions(manage_channels=True)
    async def ticket_list(self, ctx):
        """List all open tickets"""
        tickets = await self.get_all_open_tickets(ctx.guild.id)
        
        if not tickets:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> There are no open tickets!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        embed = discord.Embed(
            title=f"Open Tickets in {ctx.guild.name}",
            color=discord.Color.from_str("#a6afe7")
        )
        
        for ticket in tickets[:10]:
            ticket_id, channel_id, user_id, ticket_number, title, claimed_by = ticket
            channel = ctx.guild.get_channel(channel_id)
            user = ctx.guild.get_member(user_id)
            
            claimer = ""
            if claimed_by:
                claimer_member = ctx.guild.get_member(claimed_by)
                claimer = f"\n**Claimed by:** {claimer_member.mention if claimer_member else 'Unknown'}"
            
            embed.add_field(
                name=f"Ticket #{ticket_number}",
                value=f"**Title:** {title}\n**Creator:** {user.mention if user else 'Unknown'}\n**Channel:** {channel.mention if channel else 'Deleted'}{claimer}",
                inline=False
            )
        
        embed.set_footer(text=f"Total: {len(tickets)} open ticket(s)")
        await ctx.send(embed=embed)
    
    # ==================== VOICEMASTER COMMANDS ====================
    
    @commands.group(name="voicemaster", aliases=["vm"], invoke_without_command=True)
    async def voicemaster(self, ctx):
        """VoiceMaster configuration commands"""
        view = VoiceMasterView(ctx)
        view.message = await ctx.send(embed=view.create_embed(), view=view)
    
    @voicemaster.command(name="setup")
    @commands.has_permissions(administrator=True)
    async def vm_setup(self, ctx, category: discord.CategoryChannel = None):
        """Setup VoiceMaster in a category"""
        if not category:
            category = await ctx.guild.create_category(name="regret's vm")
        
        join_channel = await ctx.guild.create_voice_channel(
            name="j2c",
            category=category
        )
        
        await self.set_guild_config(
            ctx.guild.id,
            join_channel.id,
            category.id,
            "{user}'s channel"
        )
        
        embed = discord.Embed(
            title="<:approve:1429468807348486305> VoiceMaster Setup Complete",
            description=f"Join-to-create channel created in {category.mention}",
            color=discord.Color.from_str("#a6afe7")
        )
        
        embed.add_field(name="Join Channel", value=join_channel.mention, inline=False)
        embed.add_field(name="Category", value=category.mention, inline=False)
        
        await ctx.send(embed=embed)
    
    @voicemaster.command(name="remove")
    @commands.has_permissions(administrator=True)
    async def vm_remove(self, ctx):
        """Remove VoiceMaster configuration"""
        config = await self.get_guild_config(ctx.guild.id)
        
        if not config:
            embed = discord.Embed(
                description="VoiceMaster is not configured for this server!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
            return
        
        join_channel = ctx.guild.get_channel(config['join_channel_id'])
        if join_channel:
            try:
                await join_channel.delete()
            except:
                pass
        
        await self.remove_guild_config(ctx.guild.id)
        
        embed = discord.Embed(
            description="<:approve:1429468807348486305> VoiceMaster configuration has been removed from this server",
            color=discord.Color.from_str("#a6afe7")
        )
        
        await ctx.send(embed=embed)
    
    @voicemaster.command(name="lock")
    async def lock(self, ctx):
        """Lock your temporary voice channel"""
        if not ctx.author.voice or not ctx.author.voice.channel:
            embed = discord.Embed(
                description="You must be in a voice channel!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
            return
        
        channel = ctx.author.voice.channel
        owner_id = await self.get_temp_channel_owner(channel.id)
        
        if not owner_id or owner_id != ctx.author.id:
            embed = discord.Embed(
                description="You don't own this voice channel!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
            return
        
        await channel.set_permissions(ctx.guild.default_role, connect=False)
        embed = discord.Embed(
            description=f"🔒 Locked {channel.mention}",
            color=discord.Color.from_str("#a6afe7")
        )
        await ctx.send(embed=embed)
    
    @voicemaster.command(name="unlock")
    async def unlock(self, ctx):
        """Unlock your temporary voice channel"""
        if not ctx.author.voice or not ctx.author.voice.channel:
            embed = discord.Embed(
                description="You must be in a voice channel!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
            return
        
        channel = ctx.author.voice.channel
        owner_id = await self.get_temp_channel_owner(channel.id)
        
        if not owner_id or owner_id != ctx.author.id:
            embed = discord.Embed(
                description="You don't own this voice channel!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
            return
        
        await channel.set_permissions(ctx.guild.default_role, connect=None)
        embed = discord.Embed(
            description=f"🔓 Unlocked {channel.mention}",
            color=discord.Color.from_str("#a6afe7")
        )
        await ctx.send(embed=embed)
    
    @voicemaster.command(name="rename")
    async def rename(self, ctx, *, name: str):
        """Rename your temporary voice channel"""
        if not ctx.author.voice or not ctx.author.voice.channel:
            embed = discord.Embed(
                description="You must be in a voice channel!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
            return
        
        channel = ctx.author.voice.channel
        owner_id = await self.get_temp_channel_owner(channel.id)
        
        if not owner_id or owner_id != ctx.author.id:
            embed = discord.Embed(
                description="You don't own this voice channel!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
            return
        
        await channel.edit(name=name)
        embed = discord.Embed(
            description=f"<:approve:1429468807348486305> Renamed channel to **{name}**",
            color=discord.Color.from_str("#a6afe7")
        )
        await ctx.send(embed=embed)
    
    @voicemaster.command(name="limit")
    async def limit(self, ctx, limit: int):
        """Set user limit for your temporary voice channel"""
        if not ctx.author.voice or not ctx.author.voice.channel:
            embed = discord.Embed(
                description="You must be in a voice channel!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
            return
        
        channel = ctx.author.voice.channel
        owner_id = await self.get_temp_channel_owner(channel.id)
        
        if not owner_id or owner_id != ctx.author.id:
            embed = discord.Embed(
                description="You don't own this voice channel!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
            return
        
        if limit < 0 or limit > 99:
            embed = discord.Embed(
                description="Limit must be between 0 and 99!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
            return
        
        await channel.edit(user_limit=limit)
        embed = discord.Embed(
            description=f"<:approve:1429468807348486305> Set user limit to **{limit}**",
            color=discord.Color.from_str("#a6afe7")
        )
        await ctx.send(embed=embed)
    
    @voicemaster.command(name="permit")
    async def permit(self, ctx, member: discord.Member):
        """Allow a user to join your locked voice channel"""
        if not ctx.author.voice or not ctx.author.voice.channel:
            embed = discord.Embed(
                description="You must be in a voice channel!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
            return
        
        channel = ctx.author.voice.channel
        owner_id = await self.get_temp_channel_owner(channel.id)
        
        if not owner_id or owner_id != ctx.author.id:
            embed = discord.Embed(
                description="You don't own this voice channel!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
            return
        
        await channel.set_permissions(member, connect=True)
        embed = discord.Embed(
            description=f"<:approve:1429468807348486305> Permitted {member.mention} to join {channel.mention}",
            color=discord.Color.from_str("#a6afe7")
        )
        await ctx.send(embed=embed)
    
    @voicemaster.command(name="reject")
    async def reject(self, ctx, member: discord.Member):
        """Prevent a user from joining your voice channel"""
        if not ctx.author.voice or not ctx.author.voice.channel:
            embed = discord.Embed(
                description="You must be in a voice channel!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
            return
        
        channel = ctx.author.voice.channel
        owner_id = await self.get_temp_channel_owner(channel.id)
        
        if not owner_id or owner_id != ctx.author.id:
            embed = discord.Embed(
                description="You don't own this voice channel!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
            return
        
        await channel.set_permissions(member, connect=False)
        
        if member.voice and member.voice.channel == channel:
            await member.move_to(None)
        
        embed = discord.Embed(
            description=f"<:approve:1429468807348486305> Rejected {member.mention} from {channel.mention}",
            color=discord.Color.from_str("#a6afe7")
        )
        await ctx.send(embed=embed)
    
    @voicemaster.command(name="claim")
    async def claim(self, ctx):
        """Claim ownership of a voice channel if the owner left"""
        if not ctx.author.voice or not ctx.author.voice.channel:
            embed = discord.Embed(
                description="You must be in a voice channel!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
            return
        
        channel = ctx.author.voice.channel
        owner_id = await self.get_temp_channel_owner(channel.id)
        
        if not owner_id:
            embed = discord.Embed(
                description="This is not a temporary voice channel!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
            return
        
        owner = ctx.guild.get_member(owner_id)
        if owner and owner.voice and owner.voice.channel == channel:
            embed = discord.Embed(
                description="The owner is still in the channel!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
            return
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE temp_channels SET owner_id = ? WHERE channel_id = ?",
                (ctx.author.id, channel.id)
            )
            await db.commit()
        
        self.temp_channels[channel.id] = ctx.author.id
        
        embed = discord.Embed(
            description=f"<:approve:1429468807348486305> You now own {channel.mention}",
            color=discord.Color.from_str("#a6afe7")
        )
        await ctx.send(embed=embed)

    @commands.group(name="autorole", aliases=["ar"], invoke_without_command=True)
    @commands.has_permissions(manage_roles=True)
    async def autorole(self, ctx):
        """Manage auto roles for new members"""
        view = AutoRoleView(ctx)
        view.message = await ctx.send(embed=view.create_embed(), view=view)
    
    @autorole.command(name="add")
    @commands.has_permissions(manage_roles=True)
    async def autorole_add(self, ctx, role: discord.Role):
        """Add a role to be given to new members automatically"""
        if role >= ctx.guild.me.top_role:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> I cannot assign this role as it's higher than or equal to my highest role!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        if role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> You cannot add a role that's higher than or equal to your highest role!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        success = await self.add_autorole(ctx.guild.id, role.id)
        
        if not success:
            embed = discord.Embed(
                description=f"<:deny:1429468818094424075> {role.mention} is already an auto role!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        embed = discord.Embed(
            description=f"✅ Successfully added {role.mention} as an auto role!",
            color=discord.Color.from_str("#a6afe7")
        )
        await ctx.send(embed=embed)
    
    @autorole.command(name="remove", aliases=["delete", "del"])
    @commands.has_permissions(manage_roles=True)
    async def autorole_remove(self, ctx, role: discord.Role):
        """Remove a role from auto roles"""
        success = await self.remove_autorole(ctx.guild.id, role.id)
        
        if not success:
            embed = discord.Embed(
                description=f"<:deny:1429468818094424075> {role.mention} is not an auto role!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        embed = discord.Embed(
            description=f"✅ Successfully removed {role.mention} from auto roles!",
            color=discord.Color.from_str("#a6afe7")
        )
        await ctx.send(embed=embed)
    
    @autorole.command(name="list", aliases=["show"])
    @commands.has_permissions(manage_roles=True)
    async def autorole_list(self, ctx):
        """List all auto roles for this server"""
        role_ids = await self.get_autoroles(ctx.guild.id)
        
        if not role_ids:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> There are no auto roles set up for this server!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        roles_list = []
        deleted_roles = []
        
        for role_id in role_ids:
            role = ctx.guild.get_role(role_id)
            if role:
                roles_list.append(role.mention)
            else:
                deleted_roles.append(role_id)
        
        for role_id in deleted_roles:
            await self.remove_autorole(ctx.guild.id, role_id)
        
        if not roles_list:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> There are no auto roles set up for this server!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        embed = discord.Embed(
            title=f"Auto Roles for {ctx.guild.name}",
            description="\n".join(roles_list),
            color=discord.Color.from_str("#a6afe7")
        )
        embed.set_footer(text=f"Total: {len(roles_list)} role(s)")
        
        await ctx.send(embed=embed)
    
    @autorole.command(name="clear", aliases=["reset"])
    @commands.has_permissions(manage_roles=True)
    async def autorole_clear(self, ctx):
        """Clear all auto roles for this server"""
        success = await self.clear_autoroles(ctx.guild.id)
        
        if not success:
            embed = discord.Embed(
                description="<:deny:1429468818094424075> There are no auto roles to clear!",
                color=discord.Color.from_str("#a6afe7")
            )
            return await ctx.send(embed=embed)
        
        embed = discord.Embed(
            description="✅ Successfully cleared all auto roles!",
            color=discord.Color.from_str("#a6afe7")
        )
        await ctx.send(embed=embed)
    
    # Error handlers
    @autorole_add.error
    @autorole_remove.error
    async def autorole_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                description="<:deny:1429468818094424075> You need **Manage Roles** permission to use this command!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.RoleNotFound):
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Role not found!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.BadArgument):
            embed = discord.Embed(
                description="<:deny:1429468818094424075> Invalid role provided!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)

    # ==================== JAIL COMMANDS ====================
    
    @commands.group(name="jail", invoke_without_command=True)
    @commands.has_permissions(moderate_members=True)
    async def jail_command(self, ctx, member: discord.Member = None, duration: str = None, *, reason: str = "No reason provided"):
        """Jail a member. Duration format: 1h, 30m, 1d, etc."""
        
        if member is None:
            view = JailView(ctx)
            view.message = await ctx.send(embed=view.create_embed(), view=view)
            return
        
        if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            embed = discord.Embed(
                description=f"{self.deny} You cannot jail someone with an equal or higher role.",
                color=self.purple
            )
            await ctx.send(embed=embed)
            return
        
        if member.id == ctx.author.id:
            embed = discord.Embed(
                description=f"{self.deny} You cannot jail yourself.",
                color=self.purple
            )
            await ctx.send(embed=embed)
            return
        
        # Get or create jail role
        jail_role = self.get_jail_role(ctx.guild)
        if not jail_role:
            embed = discord.Embed(
                description=f"{self.deny} Jail role not found. Please run `;jail setup` first.",
                color=self.purple
            )
            await ctx.send(embed=embed)
            return
        
        # Get jail channel
        jail_channel = discord.utils.get(ctx.guild.text_channels, name="jail")
        
        # Check if already jailed
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                'SELECT * FROM jailed_users WHERE guild_id = ? AND user_id = ?',
                (ctx.guild.id, member.id)
            ) as cursor:
                existing = await cursor.fetchone()
        
        if existing:
            embed = discord.Embed(
                description=f"{self.deny} {member.mention} is already jailed.",
                color=self.purple
            )
            await ctx.send(embed=embed)
            return
        
        # Store current roles
        role_ids = [str(role.id) for role in member.roles if role != ctx.guild.default_role]
        roles_str = ','.join(role_ids)
        
        # Parse duration
        release_time = None
        duration_text = "Indefinite"
        if duration:
            release_time = self.parse_duration(duration)
            if release_time:
                duration_text = duration
            else:
                embed = discord.Embed(
                    description=f"{self.deny} Invalid duration format. Use: 1h, 30m, 1d, etc.",
                    color=self.purple
                )
                await ctx.send(embed=embed)
                return
        
        try:
            # Remove all roles except @everyone
            roles_to_remove = [role for role in member.roles if role != ctx.guild.default_role]
            await member.remove_roles(*roles_to_remove, reason=f"Jailed by {ctx.author}")
            
            # Add jail role
            await member.add_roles(jail_role, reason=f"Jailed by {ctx.author}")
            
            # Store in database
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    INSERT INTO jailed_users (guild_id, user_id, roles, jailed_at, release_time, reason, jailed_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (ctx.guild.id, member.id, roles_str, int(datetime.utcnow().timestamp()), 
                      release_time, reason, ctx.author.id))
                await db.commit()
            
            # Send success message
            embed = discord.Embed(
                description=f"{self.approve} **Jailed** {member.mention} for **{duration_text}**.\n**Reason:** {reason}",
                color=self.purple
            )
            await ctx.send(embed=embed)
            
            # Notify in jail channel
            if jail_channel:
                jail_embed = discord.Embed(
                    title="You have been jailed",
                    description=f"**Reason:** {reason}\n**Duration:** {duration_text}\n**Moderator:** {ctx.author.mention}",
                    color=self.purple
                )
                await jail_channel.send(f"{member.mention}", embed=jail_embed)
        
        except discord.Forbidden:
            embed = discord.Embed(
                description=f"{self.deny} I don't have permission to manage roles for this user.",
                color=self.purple
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                description=f"{self.deny} An error occurred: {str(e)}",
                color=self.purple
            )
            await ctx.send(embed=embed)
    
    @jail_command.command(name="setup")
    @commands.has_permissions(administrator=True)
    async def jail_setup(self, ctx):
        """Setup the jail system (creates jail role and channel)"""
        
        # Check if jail role already exists
        existing_role = self.get_jail_role(ctx.guild)
        if existing_role:
            embed = discord.Embed(
                description=f"{self.deny} Jail role already exists: {existing_role.mention}",
                color=self.purple
            )
            await ctx.send(embed=embed)
            return
        
        # Check if jail channel already exists
        existing_channel = discord.utils.get(ctx.guild.text_channels, name="jail")
        if existing_channel:
            embed = discord.Embed(
                description=f"{self.deny} Jail channel already exists: {existing_channel.mention}",
                color=self.purple
            )
            await ctx.send(embed=embed)
            return
        
        try:
            # Create jail role
            jail_role = await self.create_jail_role(ctx.guild)
            if not jail_role:
                embed = discord.Embed(
                    description=f"{self.deny} Failed to create jail role.",
                    color=self.purple
                )
                await ctx.send(embed=embed)
                return
            
            # Create jail channel
            jail_channel = await self.setup_jail_channel(ctx.guild, jail_role)
            if not jail_channel:
                embed = discord.Embed(
                    description=f"{self.deny} Failed to create jail channel.",
                    color=self.purple
                )
                await ctx.send(embed=embed)
                return
            
            # Success message
            embed = discord.Embed(
                description=f"{self.approve} Jail system setup complete!\n**Role:** {jail_role.mention}\n**Channel:** {jail_channel.mention}",
                color=self.purple
            )
            await ctx.send(embed=embed)
        
        except discord.Forbidden:
            embed = discord.Embed(
                description=f"{self.deny} I don't have permission to create roles or channels.",
                color=self.purple
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                description=f"{self.deny} An error occurred: {str(e)}",
                color=self.purple
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="unjail")
    @commands.has_permissions(moderate_members=True)
    async def unjail(self, ctx, member: discord.Member):
        """Unjail a member and restore their roles"""
        
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                'SELECT * FROM jailed_users WHERE guild_id = ? AND user_id = ?',
                (ctx.guild.id, member.id)
            ) as cursor:
                jail_data = await cursor.fetchone()
        
        if not jail_data:
            embed = discord.Embed(
                description=f"{self.deny} {member.mention} is not jailed.",
                color=self.purple
            )
            await ctx.send(embed=embed)
            return
        
        roles_str = jail_data[2]
        
        try:
            # Remove jail role
            jail_role = self.get_jail_role(ctx.guild)
            if jail_role and jail_role in member.roles:
                await member.remove_roles(jail_role, reason=f"Unjailed by {ctx.author}")
            
            # Restore roles
            if roles_str:
                role_ids = roles_str.split(',')
                roles_to_add = []
                for role_id in role_ids:
                    role = ctx.guild.get_role(int(role_id))
                    if role:
                        roles_to_add.append(role)
                
                if roles_to_add:
                    await member.add_roles(*roles_to_add, reason=f"Unjailed by {ctx.author}")
            
            # Remove from database
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    'DELETE FROM jailed_users WHERE guild_id = ? AND user_id = ?',
                    (ctx.guild.id, member.id)
                )
                await db.commit()
            
            embed = discord.Embed(
                description=f"{self.approve} **Unjailed** {member.mention}.",
                color=self.purple
            )
            await ctx.send(embed=embed)
        
        except discord.Forbidden:
            embed = discord.Embed(
                description=f"{self.deny} I don't have permission to manage roles for this user.",
                color=self.purple
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                description=f"{self.deny} An error occurred: {str(e)}",
                color=self.purple
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="jailinfo")
    @commands.has_permissions(moderate_members=True)
    async def jailinfo(self, ctx, member: discord.Member = None):
        """Get information about a jailed member or list all jailed members"""
        
        if member:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    'SELECT * FROM jailed_users WHERE guild_id = ? AND user_id = ?',
                    (ctx.guild.id, member.id)
                ) as cursor:
                    jail_data = await cursor.fetchone()
            
            if not jail_data:
                embed = discord.Embed(
                    description=f"{self.deny} {member.mention} is not jailed.",
                    color=self.purple
                )
                await ctx.send(embed=embed)
                return
            
            release_time = jail_data[4]
            reason = jail_data[5]
            jailed_by = ctx.guild.get_member(jail_data[6])
            
            embed = discord.Embed(
                title=f"Jail Info - {member}",
                color=self.purple
            )
            embed.add_field(name="Jailed At", value=f"<t:{jail_data[3]}:F>", inline=False)
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Jailed By", value=jailed_by.mention if jailed_by else "Unknown", inline=False)
            
            if release_time:
                embed.add_field(name="Release Time", value=f"<t:{release_time}:R>", inline=False)
            else:
                embed.add_field(name="Duration", value="Indefinite", inline=False)
            
            await ctx.send(embed=embed)
        else:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute(
                    'SELECT * FROM jailed_users WHERE guild_id = ?',
                    (ctx.guild.id,)
                ) as cursor:
                    all_jailed = await cursor.fetchall()
            
            if not all_jailed:
                embed = discord.Embed(
                    description=f"{self.deny} No members are currently jailed.",
                    color=self.purple
                )
                await ctx.send(embed=embed)
                return
            
            embed = discord.Embed(
                title="Jailed Members",
                color=self.purple
            )
            
            for jail_data in all_jailed[:10]:  # Limit to 10
                member_obj = ctx.guild.get_member(jail_data[1])
                if member_obj:
                    release_time_val = jail_data[4]
                    if release_time_val:
                        time_text = f"<t:{release_time_val}:R>"
                    else:
                        time_text = "Indefinite"
                    
                    embed.add_field(
                        name=str(member_obj),
                        value=f"**Release:** {time_text}\n**Reason:** {jail_data[5][:50]}...",
                        inline=False
                    )
            
            if len(all_jailed) > 10:
                embed.set_footer(text=f"Showing 10 of {len(all_jailed)} jailed members")
            
            await ctx.send(embed=embed)
    
    # ==================== ERROR HANDLERS ====================
    
    @jail_command.error
    async def jail_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                description=f"{self.deny} You need the `Moderate Members` permission to use this command.",
                color=self.purple
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.MemberNotFound):
            embed = discord.Embed(
                description=f"{self.deny} Could not find that member.",
                color=self.purple
            )
            await ctx.send(embed=embed)
    
    @jail_setup.error
    async def jail_setup_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                description=f"{self.deny} You need the `Administrator` permission to use this command.",
                color=self.purple
            )
            await ctx.send(embed=embed)
    
    @unjail.error
    async def unjail_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                description=f"{self.deny} You need the `Moderate Members` permission to use this command.",
                color=self.purple
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.MemberNotFound):
            embed = discord.Embed(
                description=f"{self.deny} Could not find that member.",
                color=self.purple
            )
            await ctx.send(embed=embed)

    @commands.group(name='alias', invoke_without_command=True)
    @commands.guild_only()
    async def alias(self, ctx):
        """Alias command group"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                description="**Alias Commands**\n`,alias add <alias> <command>` - Add alias\n`,alias remove <alias>` - Remove alias\n`,alias list` - List all aliases",
                color=self.purple
            )
            await ctx.send(embed=embed)
    
    @alias.command(name='add')
    @commands.guild_only()
    async def alias_add(self, ctx, alias_name: str, *, real_command: str):
        """Add a new alias
        
        Example: ,alias add byebye ban
        """
        # Prevent creating aliases for alias commands to avoid confusion
        if real_command.startswith('alias'):
            await ctx.send("❌ You cannot create aliases for the alias command itself!")
            return
        
        self.add_alias(ctx.guild.id, alias_name, real_command)
        
        embed = discord.Embed(
            description=f"✅ Alias `{alias_name}` → `{real_command}`",
            color=self.purple
        )
        await ctx.send(embed=embed)
    
    @alias.command(name='remove', aliases=['delete', 'rm'])
    @commands.guild_only()
    async def alias_remove(self, ctx, alias_name: str):
        """Remove an alias
        
        Example: ,alias remove byebye
        """
        if self.remove_alias(ctx.guild.id, alias_name):
            embed = discord.Embed(
                description=f"✅ Removed alias: `{alias_name}`",
                color=self.purple
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"❌ Alias `{alias_name}` not found!")
    
    @alias.command(name='list')
    @commands.guild_only()
    async def alias_list(self, ctx):
        """List all aliases for the server"""
        aliases = self.get_all_aliases(ctx.guild.id)
        
        if not aliases:
            await ctx.send("No aliases configured for this server.")
            return
        
        alias_text = "\n".join([f"`{alias_name}` → `{real_command}`" for alias_name, real_command in aliases])
        
        embed = discord.Embed(
            description=f"**Aliases for {ctx.guild.name}**\n{alias_text}",
            color=self.purple
        )
        
        await ctx.send(embed=embed)
    
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """Handle command errors, specifically for aliases"""
        if isinstance(error, commands.CommandNotFound):
            # Try to find an alias
            if ctx.guild:
                # Extract the invoked command name
                prefix = ctx.prefix
                message_content = ctx.message.content[len(prefix):]
                parts = message_content.split(maxsplit=1)
                
                if parts:
                    potential_alias = parts[0]
                    args = parts[1] if len(parts) > 1 else ""
                    
                    # Check if it's an alias
                    real_command = self.get_alias(ctx.guild.id, potential_alias)
                    
                    if real_command:
                        # Create new message content with real command
                        new_content = f"{prefix}{real_command}"
                        if args:
                            new_content += f" {args}"
                        
                        # Recreate the message and process
                        ctx.message.content = new_content
                        new_ctx = await self.bot.get_context(ctx.message)
                        await self.bot.invoke(new_ctx)
                        return
            
            # If not an alias, let other error handlers deal with it
            raise error
            
async def setup(bot):
    await bot.add_cog(Configuration(bot))