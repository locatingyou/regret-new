import discord
from discord.ext import commands
import aiosqlite
import os
from datetime import datetime, timedelta

class Logging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "data/logging.db"
        self.bot.loop.create_task(self.setup_db())
        self.case_numbers = {}
        self.recent_actions = {}  # {guild_id: {"ban": {user_id: moderator_id}, "kick": {user_id: moderator_id}, ...}}
    
    async def setup_db(self):
        os.makedirs("data", exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS log_config (
                    guild_id INTEGER PRIMARY KEY,
                    log_channel_id INTEGER,
                    case_counter INTEGER DEFAULT 0
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS modlog_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    case_number INTEGER NOT NULL,
                    action_type TEXT NOT NULL,
                    moderator_id INTEGER,
                    user_id INTEGER,
                    reason TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()

    def record_action(self, guild_id, action_type, user_id, moderator_id):
        """Store which moderator performed a specific action"""
        if guild_id not in self.recent_actions:
            self.recent_actions[guild_id] = {}
        if action_type not in self.recent_actions[guild_id]:
            self.recent_actions[guild_id][action_type] = {}
        self.recent_actions[guild_id][action_type][user_id] = moderator_id

    async def get_log_channel(self, guild_id):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT log_channel_id FROM log_config WHERE guild_id = ?", (guild_id,)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None

    async def set_log_channel(self, guild_id, channel_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO log_config (guild_id, log_channel_id, case_counter)
                VALUES (?, ?, 0)
                ON CONFLICT(guild_id) DO UPDATE SET
                    log_channel_id = excluded.log_channel_id
            """, (guild_id, channel_id))
            await db.commit()

    async def increment_case_counter(self, guild_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE log_config SET case_counter = case_counter + 1 WHERE guild_id = ?", (guild_id,))
            await db.commit()
            async with db.execute("SELECT case_counter FROM log_config WHERE guild_id = ?", (guild_id,)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 1

    async def log_action(self, guild_id, case_number, action_type, moderator_id, user_id, reason):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT INTO modlog_entries (guild_id, case_number, action_type, moderator_id, user_id, reason)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (guild_id, case_number, action_type, moderator_id, user_id, reason))
            await db.commit()

    async def send_log(self, guild, action_type, moderator, user=None, reason=None, extra_info=None):
        log_channel_id = await self.get_log_channel(guild.id)
        if not log_channel_id:
            return
        
        log_channel = guild.get_channel(log_channel_id)
        if not log_channel:
            return
        
        case_number = await self.increment_case_counter(guild.id)

        if user:
            await self.log_action(
                guild.id,
                case_number,
                action_type,
                moderator.id if moderator else None,
                user.id if isinstance(user, (discord.Member, discord.User)) else None,
                reason
            )

        embed = discord.Embed(title="Modlog Entry", color=0xa6afe7)
        info_text = f"**Case #{case_number}** | {action_type}"

        if user:
            if isinstance(user, (discord.Member, discord.User)):
                info_text += f"\n**User**: {user.mention} ({user.id})"
            else:
                info_text += f"\n**User**: {user}"

        if moderator:
            info_text += f"\n**Moderator**: {moderator.mention} ({moderator.id})"
        else:
            info_text += f"\n**Moderator**: None (N/A)"

        if reason:
            info_text += f"\n**Reason**: {reason}"

        if extra_info:
            info_text += f"\n{extra_info}"

        embed.add_field(name="Information", value=info_text, inline=False)

        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            pass

    # ==================== COMMANDS ====================

    @commands.command(name="setlogs")
    @commands.has_permissions(manage_guild=True)
    async def set_logs(self, ctx, channel: discord.TextChannel):
        await self.set_log_channel(ctx.guild.id, channel.id)
        embed = discord.Embed(
            description=f"<:approve:1429468807348486305> Moderation logs will now be sent to {channel.mention}",
            color=discord.Color.from_str("#a6afe7")
        )
        await ctx.send(embed=embed)

    @commands.command(name="removelogs")
    @commands.has_permissions(manage_guild=True)
    async def remove_logs(self, ctx):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("DELETE FROM log_config WHERE guild_id = ?", (ctx.guild.id,))
            await db.commit()
            if cursor.rowcount > 0:
                embed = discord.Embed(
                    description="<:approve:1429468807348486305> Moderation logging has been disabled",
                    color=discord.Color.from_str("#a6afe7")
                )
            else:
                embed = discord.Embed(
                    description="<:deny:1429468818094424075> Moderation logging is not configured for this server",
                    color=discord.Color.from_str("#a6afe7")
                )
        await ctx.send(embed=embed)

    # ==================== EVENT LISTENERS ====================

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        await discord.utils.sleep_until(discord.utils.utcnow() + timedelta(seconds=1))
        try:
            ban_entry = await guild.fetch_ban(user)
            reason = ban_entry.reason or "No reason provided"
            moderator = None

            if guild.id in self.recent_actions and "ban" in self.recent_actions[guild.id]:
                mod_id = self.recent_actions[guild.id]["ban"].pop(user.id, None)
                if mod_id:
                    moderator = guild.get_member(mod_id)

            if moderator is None:
                async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.ban):
                    if entry.target.id == user.id:
                        moderator = entry.user
                        if entry.reason:
                            reason = entry.reason
                        break

            await self.send_log(guild, "Ban", moderator, user, reason)
        except:
            pass

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        await discord.utils.sleep_until(discord.utils.utcnow() + timedelta(seconds=1))
        try:
            moderator = None
            reason = "No reason provided"

            if guild.id in self.recent_actions and "unban" in self.recent_actions[guild.id]:
                mod_id = self.recent_actions[guild.id]["unban"].pop(user.id, None)
                if mod_id:
                    moderator = guild.get_member(mod_id)

            if moderator is None:
                async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.unban):
                    if entry.target.id == user.id:
                        moderator = entry.user
                        reason = entry.reason or "No reason provided"
                        break

            await self.send_log(guild, "Unban", moderator, user, reason)
        except:
            pass

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        await discord.utils.sleep_until(discord.utils.utcnow() + timedelta(seconds=1))
        try:
            moderator = None
            reason = "No reason provided"

            if member.guild.id in self.recent_actions and "kick" in self.recent_actions[member.guild.id]:
                mod_id = self.recent_actions[member.guild.id]["kick"].pop(member.id, None)
                if mod_id:
                    moderator = member.guild.get_member(mod_id)

            if moderator is None:
                async for entry in member.guild.audit_logs(limit=5, action=discord.AuditLogAction.kick):
                    if entry.target.id == member.id:
                        moderator = entry.user
                        reason = entry.reason or "No reason provided"
                        break

            await self.send_log(member.guild, "Kick", moderator, member, reason)
        except:
            pass

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if before.timed_out_until != after.timed_out_until:
            if after.timed_out_until:
                try:
                    moderator = None
                    reason = "No reason provided"

                    if after.guild.id in self.recent_actions and "mute" in self.recent_actions[after.guild.id]:
                        mod_id = self.recent_actions[after.guild.id]["mute"].pop(after.id, None)
                        if mod_id:
                            moderator = after.guild.get_member(mod_id)

                    if moderator is None:
                        async for entry in after.guild.audit_logs(limit=5, action=discord.AuditLogAction.member_update):
                            if entry.target.id == after.id and hasattr(entry.changes.after, 'timed_out_until'):
                                moderator = entry.user
                                reason = entry.reason or "No reason provided"
                                break

                    duration = after.timed_out_until.strftime("%m/%d/%Y %I:%M %p")
                    await self.send_log(after.guild, "Mute", moderator, after, reason, f"**Duration**: Until {duration}")
                except:
                    pass
            else:
                try:
                    moderator = None
                    reason = "No reason provided"

                    if after.guild.id in self.recent_actions and "unmute" in self.recent_actions[after.guild.id]:
                        mod_id = self.recent_actions[after.guild.id]["unmute"].pop(after.id, None)
                        if mod_id:
                            moderator = after.guild.get_member(mod_id)

                    if moderator is None:
                        async for entry in after.guild.audit_logs(limit=5, action=discord.AuditLogAction.member_update):
                            if entry.target.id == after.id:
                                moderator = entry.user
                                reason = entry.reason or "No reason provided"
                                break

                    await self.send_log(after.guild, "Unmute", moderator, after, reason)
                except:
                    pass

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        await discord.utils.sleep_until(discord.utils.utcnow() + timedelta(seconds=1))
        try:
            moderator = None
            async for entry in role.guild.audit_logs(limit=5, action=discord.AuditLogAction.role_create):
                if entry.target.id == role.id:
                    moderator = entry.user
                    break
            await self.send_log(role.guild, "Role Created", moderator, None, None, f"**Role**: {role.mention}\n**Color**: {role.color}")
        except:
            pass

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        await discord.utils.sleep_until(discord.utils.utcnow() + timedelta(seconds=1))
        try:
            moderator = None
            async for entry in role.guild.audit_logs(limit=5, action=discord.AuditLogAction.role_delete):
                if entry.target.id == role.id:
                    moderator = entry.user
                    break
            await self.send_log(role.guild, "Role Deleted", moderator, None, None, f"**Role**: {role.name}\n**Color**: {role.color}")
        except:
            pass

async def setup(bot):
    await bot.add_cog(Logging(bot))