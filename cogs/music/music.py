import discord
from discord.ext import commands
import wavelink
from collections import deque
import random
import asyncio
from config import COLOR, APPROVE_EMOJI, DENY_EMOJI, LAVALINK_NODES, LAVALINK_HOST, LAVALINK_PORT, LAVALINK_PASSWORD

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = {}
        self.text_channels = {}
        self.loop_status = {}
        self.color = COLOR
        self.approve_emoji = APPROVE_EMOJI
        self.deny_emoji = DENY_EMOJI
        self.inactivity_tasks = {}
        self.bot.loop.create_task(self.connect_nodes())

    def get_queue(self, guild_id):
        if guild_id not in self.queue:
            self.queue[guild_id] = deque()
        return self.queue[guild_id]

    async def update_voice_status(self, player: wavelink.Player, track: wavelink.Playable):
        """Updates the voice channel status to show the current track"""
        try:
            if player.channel:
                status_text = f"Playing: {track.title[:28]}..." if len(track.title) > 28 else track.title
                await player.channel.edit(status=status_text)
        except Exception as e:
            print(f"[VOICE STATUS] Failed to update status: {e}")

    async def clear_voice_status(self, player: wavelink.Player):
        """Clears the voice channel status"""
        try:
            if player.channel:
                await player.channel.edit(status=None)
        except Exception as e:
            print(f"[VOICE STATUS] Failed to clear status: {e}")

    def cancel_inactivity_task(self, guild_id):
        """Cancels the inactivity timer for a guild"""
        if guild_id in self.inactivity_tasks:
            self.inactivity_tasks[guild_id].cancel()
            del self.inactivity_tasks[guild_id]

    async def start_inactivity_timer(self, guild_id):
        """Starts a 3-minute inactivity timer"""
        self.cancel_inactivity_task(guild_id)
        
        async def inactivity_check():
            try:
                await asyncio.sleep(180)  # 3 minutes
                guild = self.bot.get_guild(guild_id)
                if guild and guild.voice_client:
                    vc: wavelink.Player = guild.voice_client
                    await self.clear_voice_status(vc)
                    await vc.disconnect()
                    
                    if guild_id in self.text_channels:
                        channel = self.text_channels[guild_id]
                        try:
                            embed = discord.Embed(
                                description=f"{self.approve_emoji} Left due to 3 minutes of inactivity",
                                color=self.color
                            )
                            await channel.send(embed=embed)
                        except:
                            pass
                    
                    self.get_queue(guild_id).clear()
                    self.loop_status[guild_id] = False
                    
                if guild_id in self.inactivity_tasks:
                    del self.inactivity_tasks[guild_id]
            except asyncio.CancelledError:
                pass
        
        self.inactivity_tasks[guild_id] = self.bot.loop.create_task(inactivity_check())

    async def _play_next(self, player: wavelink.Player):
        guild_id = player.guild.id
        queue = self.get_queue(guild_id)
        
        if len(queue) > 0:
            track = queue.popleft()
            await player.play(track)
            await self.update_voice_status(player, track)
            self.cancel_inactivity_task(guild_id)
            
            if guild_id in self.text_channels:
                channel = self.text_channels[guild_id]
                try:
                    description = f"• [`{track.title} - {track.author}`]({track.uri})\n"
                    description += f"• Requested By: <@{track.requester}>"
                    
                    embed = discord.Embed(
                        title="Now Playing",
                        description=description,
                        color=self.color
                    )
                    
                    if track.artwork:
                        embed.set_thumbnail(url=track.artwork)
                    
                    await channel.send(embed=embed)
                except:
                    pass
        else:
            await self.start_inactivity_timer(guild_id)
            
    async def connect_nodes(self):
        await self.bot.wait_until_ready()
        try:
            nodes = [wavelink.Node(uri=f"http://{LAVALINK_HOST}:{LAVALINK_PORT}", password=LAVALINK_PASSWORD)]
            await wavelink.Pool.connect(nodes=nodes, client=self.bot, cache_capacity=100)
            print(f"[WAVELINK] Connected to Lavalink node: {LAVALINK_HOST}:{LAVALINK_PORT}")
        except Exception as e:
            print(f"[WAVELINK] Failed to connect to Lavalink: {e}")

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload):
        print(f"[WAVELINK] Node {payload.node.identifier} is ready!")
            
    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        player = payload.player
        guild_id = player.guild.id

        if guild_id in self.loop_status and self.loop_status[guild_id]:
            current = payload.track
            if current:
                await player.play(current)
                await self.update_voice_status(player, current)
                self.cancel_inactivity_task(guild_id)
                if guild_id in self.text_channels:
                    channel = self.text_channels[guild_id]
                    embed = discord.Embed(
                        title="🔁 Looping",
                        description=f"**{current.title}** is looping again!",
                        color=self.color
                    )
                    embed.add_field(
                        name="Duration",
                        value=f"{current.length // 60000}:{(current.length // 1000) % 60:02d}",
                        inline=True
                    )
                    embed.add_field(name="Author", value=current.author, inline=True)
                    if current.artwork:
                        embed.set_thumbnail(url=current.artwork)
                    await channel.send(embed=embed)
                return

        await self._play_next(player)

    @commands.command(name='join', help='Joins your voice channel')
    async def join(self, ctx):
        if not ctx.author.voice:
            embed = discord.Embed(
                description=f"{self.deny_emoji} You are not connected to a voice channel!",
                color=self.color
            )
            await ctx.send(embed=embed)
            return
        
        channel = ctx.author.voice.channel
        
        if ctx.voice_client:
            await ctx.voice_client.move_to(channel)
        else:
            await channel.connect(cls=wavelink.Player)
        
        self.cancel_inactivity_task(ctx.guild.id)
        
        embed = discord.Embed(
            description=f"{self.approve_emoji} Joined **{channel.name}**",
            color=self.color
        )
        await ctx.send(embed=embed)
    
    @commands.command(name='play', aliases=["p"], help='Plays a song from YouTube (URL or search)')
    async def play(self, ctx, *, query: str):
        self.text_channels[ctx.guild.id] = ctx.channel
        
        if not ctx.voice_client:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect(cls=wavelink.Player)
            else:
                embed = discord.Embed(
                    description=f"{self.deny_emoji} You need to be in a voice channel!",
                    color=self.color
                )
                await ctx.send(embed=embed)
                return
        
        vc: wavelink.Player = ctx.voice_client
        self.cancel_inactivity_task(ctx.guild.id)
        
        async with ctx.typing():
            try:
                tracks = await wavelink.Playable.search(query)
                
                if not tracks:
                    embed = discord.Embed(
                        description=f"{self.deny_emoji} No results found.",
                        color=self.color
                    )
                    return await ctx.send(embed=embed)
                
                guild_id = ctx.guild.id
                
                if isinstance(tracks, wavelink.Playlist):
                    playlist = tracks
                    
                    if vc.playing:
                        self.get_queue(guild_id).extend(playlist.tracks)
                        embed = discord.Embed(
                            title="📋 Playlist Added to Queue",
                            description=f"**{playlist.name}**\nAdded **{len(playlist.tracks)}** tracks to queue",
                            color=self.color
                        )
                        embed.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.display_avatar.url)
                        await ctx.send(embed=embed)
                    else:
                        await vc.play(playlist.tracks[0])
                        await self.update_voice_status(vc, playlist.tracks[0])
                        if len(playlist.tracks) > 1:
                            self.get_queue(guild_id).extend(playlist.tracks[1:])
                        
                        embed = discord.Embed(
                            title="📋 Playing Playlist",
                            description=f"**{playlist.name}**\nNow playing **{playlist.tracks[0].title}**",
                            color=self.color
                        )
                        embed.add_field(name="Duration", value=f"{playlist.tracks[0].length // 60000}:{(playlist.tracks[0].length // 1000) % 60:02d}", inline=True)
                        embed.add_field(name="Total Tracks", value=f"{len(playlist.tracks)}", inline=True)
                        embed.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.display_avatar.url)
                        if playlist.tracks[0].artwork:
                            embed.set_thumbnail(url=playlist.tracks[0].artwork)
                        await ctx.send(embed=embed)
                else:
                    if isinstance(tracks, list):
                        track = tracks[0]
                    else:
                        track = tracks
                    
                    if vc.playing:
                        self.get_queue(guild_id).append(track)
                        embed = discord.Embed(
                            title="Added to Queue",
                            description=f"**{track.title}**",
                            color=self.color
                        )
                        embed.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.display_avatar.url)
                        await ctx.send(embed=embed)
                    else:
                        await vc.play(track)
                        await self.update_voice_status(vc, track)
                        
                        description = f"• [`{track.title}`]({track.uri}) - [`{track.author}`]({track.uri})\n"
                        description += f"• Requested By: {ctx.author.mention}"
                        
                        embed = discord.Embed(
                            title="Now Playing",
                            description=description,
                            color=self.color
                        )
                        
                        if track.artwork:
                            embed.set_thumbnail(url=track.artwork)
                        
                        await ctx.send(embed=embed)
                    
            except Exception as e:
                embed = discord.Embed(
                    description=f"{self.deny_emoji} An error occurred: {str(e)}",
                    color=self.color
                )
                await ctx.send(embed=embed)

    @commands.command(name='pause', help='Pauses the current song')
    async def pause(self, ctx):
        vc: wavelink.Player = ctx.voice_client
        
        if vc and vc.playing:
            await vc.pause(True)
            await self.start_inactivity_timer(ctx.guild.id)
            embed = discord.Embed(
                description=f"{self.approve_emoji} Paused",
                color=self.color
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description=f"{self.deny_emoji} Nothing is playing right now.",
                color=self.color
            )
            await ctx.send(embed=embed)

    @commands.command(name='resume', help='Resumes the paused song')
    async def resume(self, ctx):
        vc: wavelink.Player = ctx.voice_client
        
        if vc and vc.paused:
            await vc.pause(False)
            self.cancel_inactivity_task(ctx.guild.id)
            embed = discord.Embed(
                description=f"{self.approve_emoji} Resumed",
                color=self.color
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description=f"{self.deny_emoji} Nothing is paused right now.",
                color=self.color
            )
            await ctx.send(embed=embed)

    @commands.command(name='skip', help='Skips the current song')
    async def skip(self, ctx):
        vc: wavelink.Player = ctx.voice_client
        
        if vc and vc.playing:
            await vc.stop()
            embed = discord.Embed(
                description=f"{self.approve_emoji} Skipped",
                color=self.color
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description=f"{self.deny_emoji} Nothing is playing right now.",
                color=self.color
            )
            await ctx.send(embed=embed)

    @commands.command(name='stop', help='Stops playing and clears the queue')
    async def stop(self, ctx):
        vc: wavelink.Player = ctx.voice_client
        guild_id = ctx.guild.id
        
        self.get_queue(guild_id).clear()
        self.loop_status[guild_id] = False
        self.cancel_inactivity_task(guild_id)
        
        if vc:
            await vc.stop()
            await self.clear_voice_status(vc)
            await self.start_inactivity_timer(guild_id)
            embed = discord.Embed(
                description=f"{self.approve_emoji} Stopped and cleared queue",
                color=self.color
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description=f"{self.deny_emoji} Not connected to a voice channel.",
                color=self.color
            )
            await ctx.send(embed=embed)

    @commands.command(name='queue', help='Shows the current queue')
    async def show_queue(self, ctx):
        vc = ctx.voice_client
        queue = self.get_queue(ctx.guild.id)
        
        description = ">>> Now Playing:\n"
        
        if vc and vc.current:
            current = vc.current
            current_mins = vc.position // 60000
            current_secs = (vc.position // 1000) % 60
            total_mins = current.length // 60000
            total_secs = (current.length // 1000) % 60
            
            description += f"[`{current.title}`]({current.uri}) - [`{current_mins}:{current_secs:02d}/{total_mins}:{total_secs:02d}`]({current.uri})\n"
        else:
            description += "*Nothing playing*\n"
        
        if queue:
            description += "Up Next:\n"
            for track in queue:
                mins = track.length // 60000
                secs = (track.length // 1000) % 60
                description += f"[`{track.title}`]({track.uri}) - [`{mins}:{secs:02d}`]({track.uri})\n"
        else:
            description += "Up Next:\n*Queue is empty*"
        
        embed = discord.Embed(
            title="<:spotify:1432059509215334532> Music Queue",
            description=description,
            color=self.color
        )
        
        await ctx.send(embed=embed)

    @commands.command(name='leave', help='Disconnects the bot from voice channel')
    async def leave(self, ctx):
        vc: wavelink.Player = ctx.voice_client
        
        if vc:
            guild_id = ctx.guild.id
            self.get_queue(guild_id).clear()
            self.loop_status[guild_id] = False
            self.cancel_inactivity_task(guild_id)
            await self.clear_voice_status(vc)
            await vc.disconnect()
            embed = discord.Embed(
                description=f"{self.approve_emoji} Disconnected",
                color=self.color
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description=f"{self.deny_emoji} I'm not in a voice channel.",
                color=self.color
            )
            await ctx.send(embed=embed)

    @commands.command(name='volume', help='Changes the volume (0-100)')
    async def volume(self, ctx, volume: int):
        vc: wavelink.Player = ctx.voice_client
        
        if not vc:
            embed = discord.Embed(
                description=f"{self.deny_emoji} Not connected to a voice channel.",
                color=self.color
            )
            await ctx.send(embed=embed)
            return
        
        if 0 <= volume <= 100:
            await vc.set_volume(volume)
            embed = discord.Embed(
                description=f"{self.approve_emoji} Volume set to **{volume}%**",
                color=self.color
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description=f"{self.deny_emoji} Volume must be between 0 and 100.",
                color=self.color
            )
            await ctx.send(embed=embed)

    @commands.command(name='loop', help='Toggles looping the current song (on/off)')
    async def loop(self, ctx, mode: str = None):
        guild_id = ctx.guild.id

        if not ctx.voice_client or not ctx.voice_client.playing:
            embed = discord.Embed(
                description=f"{self.deny_emoji} Nothing is currently playing.",
                color=self.color
            )
            await ctx.send(embed=embed)
            return

        if mode is None:
            current_state = self.loop_status.get(guild_id, False)
            status = "enabled" if current_state else "disabled"
            embed = discord.Embed(
                description=f"🔁 Loop is currently **{status}**.\nUse `!loop on` or `!loop off` to change it.",
                color=self.color
            )
            await ctx.send(embed=embed)
            return

        if mode.lower() == "on":
            self.loop_status[guild_id] = True
            embed = discord.Embed(
                description=f"{self.approve_emoji} Looping **enabled** — the current song will repeat!",
                color=self.color
            )
            await ctx.send(embed=embed)

        elif mode.lower() == "off":
            self.loop_status[guild_id] = False
            embed = discord.Embed(
                description=f"{self.approve_emoji} Looping **disabled.**",
                color=self.color
            )
            await ctx.send(embed=embed)

        else:
            embed = discord.Embed(
                description=f"{self.deny_emoji} Invalid option. Use `on` or `off`.",
                color=self.color
            )
            await ctx.send(embed=embed)

    @commands.command(name='shuffle', help='Shuffles the queue')
    async def shuffle(self, ctx):
        vc = ctx.voice_client
        
        if not vc:
            return await ctx.send("❌ I'm not connected to a voice channel!")
        
        queue = self.get_queue(ctx.guild.id)
        
        if len(queue) < 2:
            return await ctx.send("❌ Not enough tracks in queue to shuffle!")
        
        random.shuffle(queue)
        
        embed = discord.Embed(
            title="🔀 Queue Shuffled",
            description=f"Shuffled **{len(queue)}** tracks",
            color=self.color
        )
        await ctx.send(embed=embed)
    
    @commands.command(name='bassboost', help='Toggles bass boost')
    async def bassboost(self, ctx, level: int = None):
        vc = ctx.voice_client
        
        if not vc:
            return await ctx.send("❌ I'm not connected to a voice channel!")
        
        if not vc.playing:
            return await ctx.send("❌ Nothing is currently playing!")
        
        if level is None:
            filters = vc.filters
            filters.equalizer.reset()
            await vc.set_filters(filters)
            
            embed = discord.Embed(
                title="🔊 Bass Boost Disabled",
                description="Bass boost has been turned off",
                color=self.color
            )
            return await ctx.send(embed=embed)
        
        if level < 1 or level > 5:
            return await ctx.send("❌ Bass boost level must be between 1-5!")
        
        filters = vc.filters
        
        boost_values = {
            1: 0.15,
            2: 0.25,
            3: 0.35,
            4: 0.45,
            5: 0.60
        }
        
        boost = boost_values[level]
        
        filters.equalizer.set(band=0, gain=boost)
        filters.equalizer.set(band=1, gain=boost)
        filters.equalizer.set(band=2, gain=boost * 0.75)
        filters.equalizer.set(band=3, gain=boost * 0.5)
        
        await vc.set_filters(filters)
        
        embed = discord.Embed(
            title="🔊 Bass Boost Enabled",
            description=f"Bass boost set to level **{level}**/5",
            color=self.color
        )
        await ctx.send(embed=embed)

    @commands.group(name="filters", invoke_without_command=True)
    async def filters(self, ctx):
        """Show available filters"""
        embed = discord.Embed(
            title="🎛️ Available Filters",
            description=(
                "**Usage:** `,filters <filter>`\n\n"
                "🔹 `nightcore` — Speeds up and raises pitch (1.2x)\n"
                "🔹 `karaoke` — Removes vocals for karaoke-style playback"
            ),
            color=self.color
        )
        await ctx.send(embed=embed)

    @filters.command(name="nightcore")
    async def nightcore(self, ctx):
        """Applies nightcore filter (1.2x pitch and tempo)"""
        vc: wavelink.Player = ctx.voice_client

        if not vc or not vc.playing:
            embed = discord.Embed(
                description=f"{self.deny_emoji} Nothing is currently playing!",
                color=self.color
            )
            return await ctx.send(embed=embed)

        try:
            filters = wavelink.Filters()
            filters.timescale.set(pitch=1.1, rate=1.1, speed=1.1)
            await vc.set_filters(filters)

            embed = discord.Embed(
                description=f"{self.approve_emoji} Nightcore filter enabled.",
                color=self.color
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                description=f"{self.deny_emoji} Failed to apply filter:\n```{e}```",
                color=self.color
            )
            await ctx.send(embed=embed)

    @filters.command(name="karaoke")
    async def karaoke(self, ctx):
        """Applies karaoke filter (removes vocals)"""
        vc: wavelink.Player = ctx.voice_client

        if not vc or not vc.playing:
            embed = discord.Embed(
                description=f"{self.deny_emoji} Nothing is currently playing!",
                color=self.color
            )
            return await ctx.send(embed=embed)

        try:
            filters = wavelink.Filters()
            filters.karaoke.set(level=1.0, mono_level=1.0, filter_band=220.0, filter_width=100.0)
            await vc.set_filters(filters)

            embed = discord.Embed(
                description=f"{self.approve_emoji} **Karaoke filter enabled!** 🎤 Vocals removed.",
                color=self.color
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                description=f"{self.deny_emoji} Failed to apply filter:\n```{e}```",
                color=self.color
            )
            await ctx.send(embed=embed)

    @filters.command(name="reset")
    async def reset_filter(self, ctx):
        """Removes all filters"""
        vc: wavelink.Player = ctx.voice_client

        if not vc:
            embed = discord.Embed(
                description=f"{self.deny_emoji} Not connected to a voice channel.",
                color=self.color
            )
            return await ctx.send(embed=embed)

        try:
            filters = wavelink.Filters()
            await vc.set_filters(filters)
            embed = discord.Embed(
                description=f"{self.approve_emoji} All filters reset.",
                color=self.color
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                description=f"{self.deny_emoji} Failed to reset filters:\n```{e}```",
                color=self.color
            )
            await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Music(bot))