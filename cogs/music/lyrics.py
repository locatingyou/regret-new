import discord
from discord.ext import commands
import sys
import os
from musixmatch import Musixmatch

class LyricsView(discord.ui.View):
    def __init__(self, pages, song_data, author_id):
        super().__init__(timeout=180)
        self.pages = pages
        self.current_page = 0
        self.song_data = song_data
        self.author_id = author_id
        self.update_buttons()
    
    def update_buttons(self):
        self.previous_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == len(self.pages) - 1
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            embed = discord.Embed(description="<:warn:1431625293768163378> Only the **author** of this embed can use these buttons", color=0xa6afe7)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False
        return True
    
    def get_embed(self):
        embed = discord.Embed(
            title=self.song_data['title'],
            description=f"```\n{self.pages[self.current_page]}\n```",
            color=0x495678
        )
        embed.set_author(name=self.song_data['author'])
        if self.song_data.get('albumArt'):
            embed.set_thumbnail(url=self.song_data['albumArt'])
        embed.set_footer(text=f"Page {self.current_page + 1}/{len(self.pages)} • Powered by Musixmatch")
        return embed
    
    @discord.ui.button(emoji="<:left:1429560648563687525>", style=discord.ButtonStyle.secondary)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
    
    @discord.ui.button(emoji="<:right:1429560663843278878>", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
    
    @discord.ui.button(emoji="<:deny:1431626916036739072>", style=discord.ButtonStyle.secondary)
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()

class Lyrics(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.mxm = Musixmatch({
            'requestTimeoutMs': 10000,
            'cacheTTL': 300000,
            'maxCacheEntries': 100
        })
    
    def split_lyrics(self, lyrics, max_length=500):
        """Split lyrics into chunks that fit in embeds with code blocks"""
        lines = lyrics.split('\n')
        chunks = []
        current_chunk = ""
        
        for line in lines:
            # +1 for newline, +6 for code block markers
            if len(current_chunk) + len(line) + 7 > max_length:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = line + "\n"
            else:
                current_chunk += line + "\n"
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def get_spotify_activity(self, member):
        """Get Spotify activity from a member"""
        for activity in member.activities:
            if isinstance(activity, discord.Spotify):
                return activity
        return None
    
    @commands.command(name='lyrics', aliases=['ly'])
    async def lyrics(self, ctx, *, query: str = None):
        """
        Get lyrics for a song
        Usage: ,lyrics <song name> or ,lyrics <artist - song>
        If no query provided, fetches lyrics for your current Spotify song
        """
        
        async with ctx.typing():
            try:
                # If no query provided, try to get from Spotify
                if not query:
                    spotify = self.get_spotify_activity(ctx.author)
                    
                    if not spotify:
                        embed = discord.Embed(
                            description="❌ No query provided and you're not listening to Spotify!\n\nUsage: `,lyrics <song name>` or connect Spotify",
                            color=0x495678
                        )
                        return await ctx.send(embed=embed)
                    
                    # Build query from Spotify activity
                    query = f"{spotify.artist} - {spotify.title}"
                
                result = await self.mxm.find_lyrics(query)
                
                if not result:
                    embed = discord.Embed(
                        description=f"❌ Couldn't find lyrics for **{query}**",
                        color=0x495678
                    )
                    return await ctx.send(embed=embed)
                
                track_info = result.get('track', {})
                lyrics_text = result.get('text', '')
                
                if not lyrics_text:
                    embed = discord.Embed(
                        description="❌ Lyrics found but no text available",
                        color=0x495678
                    )
                    return await ctx.send(embed=embed)
                
                # Split lyrics into pages
                pages = self.split_lyrics(lyrics_text)
                
                # Song data for embed
                song_data = {
                    'title': track_info.get('title', 'Unknown'),
                    'author': track_info.get('author', 'Unknown Artist'),
                    'albumArt': track_info.get('albumArt')
                }
                
                # Create view with buttons (pass author_id)
                view = LyricsView(pages, song_data, ctx.author.id)
                
                # Send first page
                await ctx.send(embed=view.get_embed(), view=view)
                
            except Exception as e:
                embed = discord.Embed(
                    description=f"❌ An error occurred: {str(e)}",
                    color=0x495678
                )
                await ctx.send(embed=embed)
    
    @lyrics.error
    async def lyrics_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                description="❌ Usage: `,lyrics <song name>` or connect Spotify and use `,lyrics`",
                color=0x495678
            )
            await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Lyrics(bot))