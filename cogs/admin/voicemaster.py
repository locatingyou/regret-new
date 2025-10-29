import discord
from discord.ext import commands
from datetime import timedelta

class VoiceMasterPanelView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog
    
    @discord.ui.button(emoji="<:lock:1431711278417580092>", style=discord.ButtonStyle.gray, custom_id="vmp_lock")
    async def lock_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        if not interaction.user.voice or not interaction.user.voice.channel:
            embed = discord.Embed(description="<:warn:1431625293768163378> You must be in a voice channel", color=0xa6afe7)
            return await interaction.followup.send(embed=embed, ephemeral=True)
        
        channel = interaction.user.voice.channel
        owner_id = await self.cog.get_temp_channel_owner(channel.id)
        
        if not owner_id or owner_id != interaction.user.id:
            embed = discord.Embed(description="<:warn:1431625293768163378> You don't own this voice channel", color=0xa6afe7)
            return await interaction.followup.send(embed=embed, ephemeral=True)
        
        await channel.set_permissions(interaction.guild.default_role, connect=False)
        embed = discord.Embed(description="🔒 Voice channel has been **locked**", color=0xa6afe7)
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @discord.ui.button(emoji="<:unlock:1431711742722838659>", style=discord.ButtonStyle.gray, custom_id="vmp_unlock")
    async def unlock_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        if not interaction.user.voice or not interaction.user.voice.channel:
            embed = discord.Embed(description="<:warn:1431625293768163378> You must be in a voice channel", color=0xa6afe7)
            return await interaction.followup.send(embed=embed, ephemeral=True)
        
        channel = interaction.user.voice.channel
        owner_id = await self.cog.get_temp_channel_owner(channel.id)
        
        if not owner_id or owner_id != interaction.user.id:
            embed = discord.Embed(description="<:warn:1431625293768163378> You don't own this voice channel", color=0xa6afe7)
            return await interaction.followup.send(embed=embed, ephemeral=True)
        
        await channel.set_permissions(interaction.guild.default_role, connect=None)
        embed = discord.Embed(description="🔓 Voice channel has been **unlocked**", color=0xa6afe7)
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @discord.ui.button(emoji="<:ghost:1431712153638801641>", style=discord.ButtonStyle.gray, custom_id="vmp_ghost")
    async def ghost_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        if not interaction.user.voice or not interaction.user.voice.channel:
            embed = discord.Embed(description="<:warn:1431625293768163378> You must be in a voice channel", color=0xa6afe7)
            return await interaction.followup.send(embed=embed, ephemeral=True)
        
        channel = interaction.user.voice.channel
        owner_id = await self.cog.get_temp_channel_owner(channel.id)
        
        if not owner_id or owner_id != interaction.user.id:
            embed = discord.Embed(description="<:warn:1431625293768163378> You don't own this voice channel", color=0xa6afe7)
            return await interaction.followup.send(embed=embed, ephemeral=True)
        
        await channel.set_permissions(interaction.guild.default_role, view_channel=False)
        embed = discord.Embed(description="👻 Voice channel is now **hidden**", color=0xa6afe7)
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @discord.ui.button(emoji="<:reveal:1431712302758891563>", style=discord.ButtonStyle.gray, custom_id="vmp_reveal")
    async def reveal_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        if not interaction.user.voice or not interaction.user.voice.channel:
            embed = discord.Embed(description="<:warn:1431625293768163378> You must be in a voice channel", color=0xa6afe7)
            return await interaction.followup.send(embed=embed, ephemeral=True)
        
        channel = interaction.user.voice.channel
        owner_id = await self.cog.get_temp_channel_owner(channel.id)
        
        if not owner_id or owner_id != interaction.user.id:
            embed = discord.Embed(description="<:warn:1431625293768163378> You don't own this voice channel", color=0xa6afe7)
            return await interaction.followup.send(embed=embed, ephemeral=True)
        
        await channel.set_permissions(interaction.guild.default_role, view_channel=None)
        embed = discord.Embed(description="👁️ Voice channel is now **visible**", color=0xa6afe7)
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @discord.ui.button(emoji="<:claim:1431712612026159165>", style=discord.ButtonStyle.gray, custom_id="vmp_claim", row=1)
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        if not interaction.user.voice or not interaction.user.voice.channel:
            embed = discord.Embed(description="<:warn:1431625293768163378> You must be in a voice channel", color=0xa6afe7)
            return await interaction.followup.send(embed=embed, ephemeral=True)
        
        channel = interaction.user.voice.channel
        owner_id = await self.cog.get_temp_channel_owner(channel.id)
        
        if not owner_id:
            embed = discord.Embed(description="<:warn:1431625293768163378> This is not a temporary voice channel", color=0xa6afe7)
            return await interaction.followup.send(embed=embed, ephemeral=True)
        
        owner = interaction.guild.get_member(owner_id)
        
        if owner and owner.voice and owner.voice.channel == channel:
            embed = discord.Embed(description="<:warn:1431625293768163378> The current owner is still in the channel", color=0xa6afe7)
            return await interaction.followup.send(embed=embed, ephemeral=True)
        
        import aiosqlite
        async with aiosqlite.connect(self.cog.db_path) as db:
            await db.execute(
                "UPDATE temp_channels SET owner_id = ? WHERE channel_id = ?",
                (interaction.user.id, channel.id)
            )
            await db.commit()
        
        self.cog.temp_channels[channel.id] = interaction.user.id
        
        embed = discord.Embed(description=f"🎤 You are now the owner of **{channel.name}**", color=0xa6afe7)
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @discord.ui.button(emoji="<:information:1431713146485342430>", style=discord.ButtonStyle.gray, custom_id="vmp_info", row=1)
    async def info_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        if not interaction.user.voice or not interaction.user.voice.channel:
            embed = discord.Embed(description="<:warn:1431625293768163378> You must be in a voice channel", color=0xa6afe7)
            return await interaction.followup.send(embed=embed, ephemeral=True)
        
        channel = interaction.user.voice.channel
        owner_id = await self.cog.get_temp_channel_owner(channel.id)
        
        if not owner_id:
            embed = discord.Embed(description="<:warn:1431625293768163378> This is not a temporary voice channel", color=0xa6afe7)
            return await interaction.followup.send(embed=embed, ephemeral=True)
        
        owner = interaction.guild.get_member(owner_id)
        
        embed = discord.Embed(title=f"ℹ️ {channel.name}", color=0xa6afe7)
        embed.add_field(name="Owner", value=owner.mention if owner else "Unknown", inline=True)
        embed.add_field(name="Members", value=f"{len(channel.members)}/{channel.user_limit or '∞'}", inline=True)
        embed.add_field(name="Bitrate", value=f"{channel.bitrate//1000}kbps", inline=True)
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @discord.ui.button(emoji="<:increase:1431712749997523234>", style=discord.ButtonStyle.gray, custom_id="vmp_increase", row=1)
    async def increase_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        if not interaction.user.voice or not interaction.user.voice.channel:
            embed = discord.Embed(description="<:warn:1431625293768163378> You must be in a voice channel", color=0xa6afe7)
            return await interaction.followup.send(embed=embed, ephemeral=True)
        
        channel = interaction.user.voice.channel
        owner_id = await self.cog.get_temp_channel_owner(channel.id)
        
        if not owner_id or owner_id != interaction.user.id:
            embed = discord.Embed(description="<:warn:1431625293768163378> You don't own this voice channel", color=0xa6afe7)
            return await interaction.followup.send(embed=embed, ephemeral=True)
        
        current_limit = channel.user_limit
        new_limit = min((current_limit or 0) + 1, 99)
        
        if new_limit == current_limit:
            embed = discord.Embed(description="<:warn:1431625293768163378> User limit is already at maximum (99)", color=0xa6afe7)
            return await interaction.followup.send(embed=embed, ephemeral=True)
        
        await channel.edit(user_limit=new_limit)
        embed = discord.Embed(description=f"➕ User limit increased to **{new_limit}**", color=0xa6afe7)
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @discord.ui.button(emoji="<:decrease:1431712945976512604>", style=discord.ButtonStyle.gray, custom_id="vmp_decrease", row=1)
    async def decrease_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        if not interaction.user.voice or not interaction.user.voice.channel:
            embed = discord.Embed(description="<:warn:1431625293768163378> You must be in a voice channel", color=0xa6afe7)
            return await interaction.followup.send(embed=embed, ephemeral=True)
        
        channel = interaction.user.voice.channel
        owner_id = await self.cog.get_temp_channel_owner(channel.id)
        
        if not owner_id or owner_id != interaction.user.id:
            embed = discord.Embed(description="<:warn:1431625293768163378> You don't own this voice channel", color=0xa6afe7)
            return await interaction.followup.send(embed=embed, ephemeral=True)
        
        current_limit = channel.user_limit or 0
        new_limit = max(current_limit - 1, 0)
        
        if current_limit == 0:
            embed = discord.Embed(description="<:warn:1431625293768163378> User limit is already unlimited", color=0xa6afe7)
            return await interaction.followup.send(embed=embed, ephemeral=True)
        
        await channel.edit(user_limit=new_limit if new_limit > 0 else None)
        limit_text = "unlimited" if new_limit == 0 else str(new_limit)
        embed = discord.Embed(description=f"➖ User limit decreased to **{limit_text}**", color=0xa6afe7)
        await interaction.followup.send(embed=embed, ephemeral=True)

class VoiceMaster(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.configuration_cog = None
    
    async def cog_load(self):
        """Add persistent view when cog loads and get Configuration cog reference"""
        self.configuration_cog = self.bot.get_cog('Configuration')
        if self.configuration_cog:
            self.bot.add_view(VoiceMasterPanelView(self.configuration_cog))
    
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        """Detect when voicemaster creates the j2c channel and create interface"""
        if not isinstance(channel, discord.VoiceChannel):
            return
        
        if channel.name != "j2c":
            return
        
        # Wait a moment to ensure everything is set up
        await discord.utils.sleep_until(discord.utils.utcnow() + timedelta(seconds=1))
        
        # Get configuration cog
        config_cog = self.bot.get_cog('Configuration')
        if not config_cog:
            return
        
        # Check if this is a voicemaster setup
        guild_config = await config_cog.get_guild_config(channel.guild.id)
        if not guild_config or guild_config['join_channel_id'] != channel.id:
            return
        
        category = channel.category
        if not category:
            return
        
        # Check if interface already exists
        if discord.utils.get(category.text_channels, name="interface"):
            return
        
        # Create interface text channel
        interface_channel = await channel.guild.create_text_channel(
            name="menu",
            category=category,
            topic="VoiceMaster control panel - Use the buttons to manage your voice channel"
        )
        
        # Send interface panel
        embed = discord.Embed(color=0xa6afe7)
        embed.set_author(name="VoiceMaster Interface", icon_url=channel.guild.icon.url if channel.guild.icon else None)
        embed.description = "Use the buttons below to control your voice channel."
        
        embed.add_field(name="Button Usage", value=(
            "<:lock:1431711278417580092> — **[Lock](https://discord.gg/x5WnrxrP)** the voice channel\n"
            "<:unlock:1431711742722838659> — **[Unlock](https://discord.gg/x5WnrxrP)** the voice channel\n"
            "<:ghost:1431712153638801641> — **[Ghost](https://discord.gg/x5WnrxrP)** the voice channel\n"
            "<:reveal:1431712302758891563> — **[Reveal](https://discord.gg/x5WnrxrP)** the voice channel\n"
            "<:claim:1431712612026159165> — **[Claim](https://discord.gg/x5WnrxrP)** the voice channel\n"
            "<:information:1431713146485342430> — **[View](https://discord.gg/x5WnrxrP)** channel information\n"
            "<:increase:1431712749997523234> — **[Increase](https://discord.gg/x5WnrxrP)** the user limit\n"
            "<:decrease:1431712945976512604> — **[Decrease](https://discord.gg/x5WnrxrP)** the user limit"
        ), inline=False)
        
        view = VoiceMasterPanelView(config_cog)
        await interface_channel.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(VoiceMaster(bot))