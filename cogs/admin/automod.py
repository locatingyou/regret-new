import discord
from discord.ext import commands
from datetime import datetime, timedelta
import aiosqlite


class AutoMod(commands.Cog):
    """Auto moderation management and logging"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "data/automod.db"
        self.bot.loop.create_task(self.setup_db())
    
    async def setup_db(self):
        """Initialize the database"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS automod_config (
                    guild_id INTEGER PRIMARY KEY,
                    log_channel_id INTEGER
                )
            """)
            await db.commit()
    
    async def get_log_channel(self, guild_id):
        """Get the log channel for a guild"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT log_channel_id FROM automod_config WHERE guild_id = ?",
                (guild_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None
    
    async def set_log_channel(self, guild_id, channel_id):
        """Set the log channel for a guild"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO automod_config (guild_id, log_channel_id)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET log_channel_id = excluded.log_channel_id
            """, (guild_id, channel_id))
            await db.commit()
    
    async def send_log(self, guild, embed):
        """Send a log embed to the configured channel"""
        log_channel_id = await self.get_log_channel(guild.id)
        if log_channel_id:
            log_channel = guild.get_channel(log_channel_id)
            if log_channel:
                try:
                    await log_channel.send(embed=embed)
                except:
                    pass
    
    @commands.Cog.listener()
    async def on_automod_rule_create(self, rule: discord.AutoModRule):
        """Called when an AutoMod rule is created"""
        embed = discord.Embed(
            title="✅ New AutoMod Rule Created",
            description=f"**{rule.name}** is now protecting your server!",
            color=discord.Color.from_str("#a6afe7"),
            timestamp=datetime.utcnow()
        )
        
        status = "🟢 Active" if rule.enabled else "🔴 Inactive"
        embed.add_field(name="Status", value=status, inline=True)
        
        if rule.creator:
            embed.add_field(name="Created by", value=rule.creator.mention, inline=True)
        
        embed.set_footer(text=f"Rule ID: {rule.id}")
        
        await self.send_log(rule.guild, embed)
    
    @commands.Cog.listener()
    async def on_automod_rule_update(self, rule: discord.AutoModRule):
        """Called when an AutoMod rule is updated"""
        embed = discord.Embed(
            title="🔧 AutoMod Rule Updated",
            description=f"Changes made to **{rule.name}**",
            color=discord.Color.from_str("#a6afe7"),
            timestamp=datetime.utcnow()
        )
        
        status = "🟢 Active" if rule.enabled else "🔴 Inactive"
        embed.add_field(name="Current Status", value=status, inline=True)
        
        embed.set_footer(text=f"Rule ID: {rule.id}")
        
        await self.send_log(rule.guild, embed)
    
    @commands.Cog.listener()
    async def on_automod_rule_delete(self, rule: discord.AutoModRule):
        """Called when an AutoMod rule is deleted"""
        embed = discord.Embed(
            title="🗑️ AutoMod Rule Removed",
            description=f"**{rule.name}** has been deleted",
            color=discord.Color.from_str("#a6afe7"),
            timestamp=datetime.utcnow()
        )
        
        embed.set_footer(text=f"Rule ID: {rule.id}")
        
        await self.send_log(rule.guild, embed)
    
    @commands.Cog.listener()
    async def on_automod_action(self, execution: discord.AutoModAction):
        """Called when an AutoMod action is executed"""
        member = execution.member
        
        # Determine action emoji and description
        action_type = str(execution.action.type).replace("AutoModAction.", "").lower()
        action_emoji = {
            "block_message": "🚫",
            "send_alert_message": "⚠️",
            "timeout": "⏱️"
        }.get(action_type, "⚡")
        
        action_desc = {
            "block_message": "Message blocked",
            "send_alert_message": "Alert sent",
            "timeout": "User timed out"
        }.get(action_type, "Action taken")
        
        embed = discord.Embed(
            title=f"{action_emoji} AutoMod Action",
            description=f"**{action_desc}** by rule: {execution.rule_trigger_type}",
            color=discord.Color.from_str("#a6afe7"),
            timestamp=datetime.utcnow()
        )
        
        if member:
            embed.set_author(name=str(member), icon_url=member.display_avatar.url)
            embed.add_field(name="User", value=member.mention, inline=True)
        
        if execution.channel:
            embed.add_field(name="Channel", value=execution.channel.mention, inline=True)
        
        if execution.matched_keyword:
            embed.add_field(name="Triggered by", value=f"`{execution.matched_keyword}`", inline=False)
        
        await self.send_log(execution.guild, embed)
    
    @commands.group(name="automod", aliases=["am"], invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def automod(self, ctx):
        """Manage Discord's AutoMod system"""
        
        # Define all subcommand pages
        pages = [
            {
                "title": "Command: automod • AutoMod Module",
                "description": "Manage Discord's AutoMod rules and logging",
                "syntax": "Syntax: ;automod [subcommand]",
                "example": None
            },
            {
                "title": "Command: automod rules • AutoMod Module",
                "description": "View all AutoMod rules in the server",
                "syntax": "Syntax: ;automod rules",
                "example": "Example: ;automod rules"
            },
            {
                "title": "Command: automod view • AutoMod Module",
                "description": "View detailed information about a specific rule",
                "syntax": "Syntax: ;automod view <number>",
                "example": "Example: ;automod view 1"
            },
            {
                "title": "Command: automod block • AutoMod Module",
                "description": "Create a rule to block specific words or phrases",
                "syntax": "Syntax: ;automod block <words>",
                "example": "Example: ;automod block badword1 badword2"
            },
            {
                "title": "Command: automod spam • AutoMod Module",
                "description": "Enable anti-spam protection",
                "syntax": "Syntax: ;automod spam",
                "example": "Example: ;automod spam"
            },
            {
                "title": "Command: automod mentions • AutoMod Module",
                "description": "Block mass mentions (mention spam)",
                "syntax": "Syntax: ;automod mentions [limit]",
                "example": "Example: ;automod mentions 5"
            },
            {
                "title": "Command: automod on • AutoMod Module",
                "description": "Enable a disabled AutoMod rule",
                "syntax": "Syntax: ;automod on <number>",
                "example": "Example: ;automod on 1"
            },
            {
                "title": "Command: automod off • AutoMod Module",
                "description": "Disable an active AutoMod rule",
                "syntax": "Syntax: ;automod off <number>",
                "example": "Example: ;automod off 1"
            },
            {
                "title": "Command: automod delete • AutoMod Module",
                "description": "Permanently delete an AutoMod rule",
                "syntax": "Syntax: ;automod delete <number>",
                "example": "Example: ;automod delete 1"
            },
            {
                "title": "Command: automod logs • AutoMod Module",
                "description": "Set the channel where AutoMod actions are logged",
                "syntax": "Syntax: ;automod logs <channel>",
                "example": "Example: ;automod logs #mod-logs"
            },
            {
                "title": "Command: automod logs • AutoMod Module",
                "description": "Rempve the channel where AutoMod actions are logged",
                "syntax": "Syntax: ;automod removelog <channel>",
                "example": "Example: ;automod removelog #mod-logs"
            }
        ]
        
        current_page = 0
        
        def create_embed(page_index):
            page = pages[page_index]
            embed = discord.Embed(
                title=page["title"],
                description=page["description"],
                color=discord.Color.from_str("#a6afe7")
            )
            
            # Add syntax and example
            syntax_text = f"```js\n{page['syntax']}\n"
            if page["example"]:
                syntax_text += f"{page['example']}\n"
            syntax_text += "```"
            embed.add_field(name="", value=syntax_text, inline=False)
            
            # Permissions
            embed.add_field(
                name="Permissions",
                value="Manage Server",
                inline=False
            )
            
            # Get aliases based on page
            aliases_map = {
                1: "list, all",
                2: "info, show",
                3: "keyword, word",
                4: "antispam",
                5: "mentionspam",
                6: "enable, activate",
                7: "disable, deactivate",
                8: "remove, del",
                9: "setlog, logging"
            }
            
            aliases = aliases_map.get(page_index, "am")
            
            # Footer
            embed.set_footer(
                text=f"Aliases: {aliases} • Page {page_index + 1}/{len(pages)}",
                icon_url=ctx.author.display_avatar.url
            )
            
            return embed
        
        def create_view(page_index):
            view = discord.ui.View(timeout=60)
            
            # Previous button
            prev_button = discord.ui.Button(
                style=discord.ButtonStyle.secondary,
                emoji="<:left:1429560648563687525>",
                custom_id="prev"
            )
            
            # Next button
            next_button = discord.ui.Button(
                style=discord.ButtonStyle.secondary,
                emoji="<:right:1429560663843278878>",
                custom_id="next"
            )
            
            # Close button
            close_button = discord.ui.Button(
                style=discord.ButtonStyle.secondary,
                emoji="<:close:1429560709078974514>",
                custom_id="close"
            )
            
            async def prev_callback(interaction):
                nonlocal current_page
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("You cannot control this menu.", ephemeral=True)
                    return
                current_page = (current_page - 1) % len(pages)
                await interaction.response.edit_message(embed=create_embed(current_page), view=create_view(current_page))
            
            async def next_callback(interaction):
                nonlocal current_page
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("You cannot control this menu.", ephemeral=True)
                    return
                current_page = (current_page + 1) % len(pages)
                await interaction.response.edit_message(embed=create_embed(current_page), view=create_view(current_page))
            
            async def close_callback(interaction):
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("You cannot control this menu.", ephemeral=True)
                    return
                await interaction.message.delete()
            
            prev_button.callback = prev_callback
            next_button.callback = next_callback
            close_button.callback = close_callback
            
            view.add_item(prev_button)
            view.add_item(next_button)
            view.add_item(close_button)
            
            return view
        
        await ctx.send(embed=create_embed(current_page), view=create_view(current_page))
    
    @automod.command(name="rules", aliases=["list", "all"])
    @commands.has_permissions(manage_guild=True)
    async def automod_rules(self, ctx):
        """View all AutoMod rules (simple list)"""
        try:
            rules = await ctx.guild.fetch_automod_rules()
        except discord.Forbidden:
            await ctx.send("❌ I need **Manage Server** permission to view AutoMod rules!")
            return
        
        if not rules:
            embed = discord.Embed(
                title="📋 AutoMod Rules",
                description="No AutoMod rules found. Create them in Server Settings > AutoMod!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(
            title=f"🛡️ AutoMod Rules for {ctx.guild.name}",
            description=f"You have **{len(rules)}** AutoMod rule(s)",
            color=discord.Color.from_str("#a6afe7")
        )
        
        for i, rule in enumerate(rules, 1):
            status = "🟢 On" if rule.enabled else "🔴 Off"
            embed.add_field(
                name=f"{i}. {rule.name}",
                value=f"Status: {status}",
                inline=False
            )
        
        embed.set_footer(text=f"Use {ctx.prefix}automod view <number> to see details")
        await ctx.send(embed=embed)
    
    @automod.command(name="view", aliases=["info", "show"])
    @commands.has_permissions(manage_guild=True)
    async def automod_view(self, ctx, rule_number: int):
        """View details about a specific rule by number"""
        try:
            rules = await ctx.guild.fetch_automod_rules()
        except discord.Forbidden:
            await ctx.send("❌ I need **Manage Server** permission to view AutoMod rules!")
            return
        
        if not rules:
            await ctx.send("❌ No AutoMod rules found!")
            return
        
        if rule_number < 1 or rule_number > len(rules):
            await ctx.send(f"❌ Invalid rule number! Choose between 1 and {len(rules)}")
            return
        
        rule = list(rules)[rule_number - 1]
        
        status = "🟢 Active" if rule.enabled else "🔴 Inactive"
        
        embed = discord.Embed(
            title=f"📝 {rule.name}",
            description=f"Rule #{rule_number}",
            color=discord.Color.from_str("#a6afe7")
        )
        
        embed.add_field(name="Status", value=status, inline=True)
        
        # Simplify trigger type
        if hasattr(rule, 'trigger_type') and rule.trigger_type:
            trigger = str(rule.trigger_type).replace("AutoModRuleTriggerType.", "").replace("_", " ").title()
            embed.add_field(name="Watches for", value=trigger, inline=True)
        
        # Show actions in simple terms
        if rule.actions:
            action_list = []
            for action in rule.actions:
                action_type = str(action.type).replace("AutoModAction.", "").lower()
                if "block" in action_type:
                    action_list.append("🚫 Block messages")
                elif "alert" in action_type:
                    action_list.append("⚠️ Send alerts")
                elif "timeout" in action_type:
                    action_list.append("⏱️ Timeout users")
            
            if action_list:
                embed.add_field(name="Actions", value="\n".join(action_list), inline=False)
        
        # Show exempt info if any
        exempt_info = []
        if rule.exempt_roles:
            exempt_info.append(f"🛡️ {len(rule.exempt_roles)} exempt role(s)")
        if rule.exempt_channels:
            exempt_info.append(f"📢 {len(rule.exempt_channels)} exempt channel(s)")
        
        if exempt_info:
            embed.add_field(name="Exemptions", value="\n".join(exempt_info), inline=False)
        
        embed.set_footer(text=f"Use {ctx.prefix}automod {'off' if rule.enabled else 'on'} {rule_number} to toggle")
        
        await ctx.send(embed=embed)
    
    @automod.command(name="on", aliases=["enable", "activate"])
    @commands.has_permissions(manage_guild=True)
    async def automod_on(self, ctx, rule_number: int):
        """Turn on an AutoMod rule by number"""
        try:
            rules = await ctx.guild.fetch_automod_rules()
        except discord.Forbidden:
            await ctx.send("❌ I need **Manage Server** permission to manage AutoMod rules!")
            return
        
        if not rules:
            await ctx.send("❌ No AutoMod rules found!")
            return
        
        if rule_number < 1 or rule_number > len(rules):
            await ctx.send(f"❌ Invalid rule number! Choose between 1 and {len(rules)}")
            return
        
        rule = list(rules)[rule_number - 1]
        
        if rule.enabled:
            await ctx.send(f"ℹ️ **{rule.name}** is already active!")
            return
        
        try:
            await rule.edit(enabled=True)
            
            embed = discord.Embed(
                title="✅ Rule Activated",
                description=f"**{rule.name}** is now protecting your server!",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
            
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to edit AutoMod rules!")
    
    @automod.command(name="off", aliases=["disable", "deactivate"])
    @commands.has_permissions(manage_guild=True)
    async def automod_off(self, ctx, rule_number: int):
        """Turn off an AutoMod rule by number"""
        try:
            rules = await ctx.guild.fetch_automod_rules()
        except discord.Forbidden:
            await ctx.send("❌ I need **Manage Server** permission to manage AutoMod rules!")
            return
        
        if not rules:
            await ctx.send("❌ No AutoMod rules found!")
            return
        
        if rule_number < 1 or rule_number > len(rules):
            await ctx.send(f"❌ Invalid rule number! Choose between 1 and {len(rules)}")
            return
        
        rule = list(rules)[rule_number - 1]
        
        if not rule.enabled:
            await ctx.send(f"ℹ️ **{rule.name}** is already inactive!")
            return
        
        try:
            await rule.edit(enabled=False)
            
            embed = discord.Embed(
                title="⏸️ Rule Deactivated",
                description=f"**{rule.name}** has been turned off",
                color=discord.Color.from_str("#a6afe7")
            )
            await ctx.send(embed=embed)
            
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to edit AutoMod rules!")
    
    @automod.command(name="logs", aliases=["setlog", "logging"])
    @commands.has_permissions(manage_guild=True)
    async def automod_logs(self, ctx, channel: discord.TextChannel):
        """Set where AutoMod actions should be logged"""
        await self.set_log_channel(ctx.guild.id, channel.id)
        
        embed = discord.Embed(
            title="✅ Logging Configured",
            description=f"AutoMod actions will now be logged in {channel.mention}",
            color=discord.Color.from_str("#a6afe7")
        )
        
        embed.set_footer(text="💡 Test it by triggering an AutoMod rule!")
        
        await ctx.send(embed=embed)
    
    @automod.command(name="block", aliases=["keyword", "word"])
    @commands.has_permissions(manage_guild=True)
    async def automod_block(self, ctx, *, words: str):
        """Create a rule to block specific words or phrases"""
        try:
            # Split words by comma or space
            keyword_list = [w.strip() for w in words.replace(',', ' ').split() if w.strip()]
            
            if not keyword_list:
                await ctx.send("❌ Please provide at least one word to block!")
                return
            
            # Create the automod rule
            rule = await ctx.guild.create_automod_rule(
                name=f"Block: {', '.join(keyword_list[:3])}{'...' if len(keyword_list) > 3 else ''}",
                event_type=discord.AutoModRuleEventType.message_send,
                trigger=discord.AutoModTrigger(
                    type=discord.AutoModRuleTriggerType.keyword,
                    keyword_filter=keyword_list
                ),
                actions=[
                    discord.AutoModRuleAction(),  # defaults to block_message
                    discord.AutoModRuleAction(channel_id=ctx.channel.id)  # send_alert_message
                ],
                enabled=True,
                reason=f"Created by {ctx.author}"
            )
            
            embed = discord.Embed(
                title="✅ Keyword Filter Created",
                description=f"Now blocking **{len(keyword_list)}** word(s)/phrase(s)",
                color=discord.Color.from_str("#a6afe7")
            )
            
            words_preview = ", ".join(keyword_list[:10])
            if len(keyword_list) > 10:
                words_preview += f" (+{len(keyword_list) - 10} more)"
            
            embed.add_field(name="Blocked Words", value=f"`{words_preview}`", inline=False)
            embed.add_field(name="Status", value="🟢 Active", inline=True)
            embed.add_field(name="Action", value="🚫 Block & Alert", inline=True)
            
            embed.set_footer(text=f"Rule ID: {rule.id}")
            
            await ctx.send(embed=embed)
            
        except discord.Forbidden:
            await ctx.send("❌ I need **Manage Server** permission to create AutoMod rules!")
        except discord.HTTPException as e:
            await ctx.send(f"❌ Failed to create rule: {e}")
    
    @automod.command(name="spam", aliases=["antispam"])
    @commands.has_permissions(manage_guild=True)
    async def automod_spam(self, ctx):
        """Create a rule to block spam messages"""
        try:
            # Create spam protection rule
            rule = await ctx.guild.create_automod_rule(
                name="Anti-Spam Protection",
                event_type=discord.AutoModRuleEventType.message_send,
                trigger=discord.AutoModTrigger(
                    type=discord.AutoModRuleTriggerType.spam
                ),
                actions=[
                    discord.AutoModRuleAction(),  # defaults to block_message
                    discord.AutoModRuleAction(duration=datetime.timedelta(seconds=60))  # timeout
                ],
                enabled=True,
                reason=f"Created by {ctx.author}"
            )
            
            embed = discord.Embed(
                title="✅ Anti-Spam Protection Enabled",
                description="Spam messages will now be blocked automatically",
                color=discord.Color.from_str("#a6afe7")
            )
            
            embed.add_field(name="Status", value="🟢 Active", inline=True)
            embed.add_field(name="Action", value="🚫 Block & ⏱️ Timeout (60s)", inline=True)
            
            embed.set_footer(text=f"Rule ID: {rule.id}")
            
            await ctx.send(embed=embed)
            
        except discord.Forbidden:
            await ctx.send("❌ I need **Manage Server** permission to create AutoMod rules!")
        except discord.HTTPException as e:
            await ctx.send(f"❌ Failed to create rule: {e}")
    
    @automod.command(name="mentions", aliases=["mentionspam"])
    @commands.has_permissions(manage_guild=True)
    async def automod_mentions(self, ctx, limit: int = 5):
        """Create a rule to block mass mentions"""
        if limit < 1 or limit > 50:
            await ctx.send("❌ Mention limit must be between 1 and 50!")
            return
        
        try:
            # Create mention spam rule
            rule = await ctx.guild.create_automod_rule(
                name=f"Block {limit}+ Mentions",
                event_type=discord.AutoModRuleEventType.message_send,
                trigger=discord.AutoModTrigger(
                    type=discord.AutoModRuleTriggerType.mention_spam,
                    mention_total_limit=limit
                ),
                actions=[
                    discord.AutoModRuleAction(),  # defaults to block_message
                    discord.AutoModRuleAction(duration=datetime.timedelta(seconds=300))  # timeout (5 min)
                ],
                enabled=True,
                reason=f"Created by {ctx.author}"
            )
            
            embed = discord.Embed(
                title="✅ Mention Spam Protection Enabled",
                description=f"Messages with **{limit}+** mentions will be blocked",
                color=discord.Color.from_str("#a6afe7")
            )
            
            embed.add_field(name="Status", value="🟢 Active", inline=True)
            embed.add_field(name="Action", value="🚫 Block & ⏱️ Timeout (5m)", inline=True)
            
            embed.set_footer(text=f"Rule ID: {rule.id}")
            
            await ctx.send(embed=embed)
            
        except discord.Forbidden:
            await ctx.send("❌ I need **Manage Server** permission to create AutoMod rules!")
        except discord.HTTPException as e:
            await ctx.send(f"❌ Failed to create rule: {e}")
    
    @automod.command(name="delete", aliases=["remove", "del"])
    @commands.has_permissions(manage_guild=True)
    async def automod_delete(self, ctx, rule_number: int):
        """Delete an AutoMod rule by number"""
        try:
            rules = await ctx.guild.fetch_automod_rules()
        except discord.Forbidden:
            await ctx.send("❌ I need **Manage Server** permission to manage AutoMod rules!")
            return
        
        if not rules:
            await ctx.send("❌ No AutoMod rules found!")
            return
        
        if rule_number < 1 or rule_number > len(rules):
            await ctx.send(f"❌ Invalid rule number! Choose between 1 and {len(rules)}")
            return
        
        rule = list(rules)[rule_number - 1]
        rule_name = rule.name
        
        try:
            await rule.delete(reason=f"Deleted by {ctx.author}")
            
            embed = discord.Embed(
                title="🗑️ Rule Deleted",
                description=f"**{rule_name}** has been permanently removed",
                color=discord.Color.from_str("#a6afe7")
            )
            
            embed.set_footer(text="This action cannot be undone")
            
            await ctx.send(embed=embed)
            
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to delete AutoMod rules!")
        except discord.HTTPException as e:
            await ctx.send(f"❌ Failed to create rule: {e}")

    @automod.command(name="removelog", aliases=["rmlog", "rlog"])
    @commands.has_permissions(manage_guild=True)
    async def automod_removelog(self, ctx):
        """Remove the AutoMod log channel"""
        log_channel_id = await self.get_log_channel(ctx.guild.id)
        
        if not log_channel_id:
            await ctx.send("❌ No log channel is currently set!")
            return
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM automod_config WHERE guild_id = ?",
                (ctx.guild.id,)
            )
            await db.commit()
        
        embed = discord.Embed(
            title="✅ Logging Disabled",
            description="AutoMod actions will no longer be logged",
            color=discord.Color.from_str("#a6afe7")
        )
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(AutoMod(bot))
