import discord
import discord_ios
from discord.ext import commands
from datetime import datetime
import os
import wavelink
import jishaku
import asyncio
from config import TOKEN, PREFIX, OWNER_IDS, STATUS_MESSAGES, LAVALINK_NODES, COLOR
from threading import Thread
from api import start_flask  # Replace with your actual filename

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

for owner_id in OWNER_IDS:
    bot.owner_ids.add(owner_id)

bot.tree.allowed_installs = discord.app_commands.AppInstallationType(guild=True, user=True)
bot.tree.allowed_contexts = discord.app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True)

statuses = STATUS_MESSAGES

bot.uptime = datetime.utcnow()

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

    bot.loop.create_task(status_task())

    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")

async def status_task():
    await bot.wait_until_ready()
    while not bot.is_closed():
        for status_text in statuses:
            custom_status = discord.CustomActivity(name=status_text)
            await bot.change_presence(status=discord.Status.online, activity=custom_status)
            await asyncio.sleep(10)

async def connect_nodes():
    """Connect to Lavalink nodes"""
    nodes = [
        wavelink.Node(uri=node["uri"], password=node["password"])
        for node in LAVALINK_NODES
    ]

    await wavelink.Pool.connect(client=bot, nodes=nodes)
    print(f"✅ Attempting to connect to {len(nodes)} Lavalink nodes...")

@bot.event
async def on_wavelink_node_ready(payload: wavelink.NodeReadyEventPayload):
    """Event when a Lavalink node successfully connects"""
    print(f"✅ Lavalink Node Ready: {payload.node.identifier} | Resumed: {payload.resumed}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if bot.user.mentioned_in(message) and not message.mention_everyone:
        content = message.content.replace(f'<@{bot.user.id}>', '').replace(f'<@!{bot.user.id}>', '').strip()
        
        if not content:
            embed = discord.Embed(
                description=f"<@{message.author.id}> Prefix: `{bot.command_prefix}`",
                color=COLOR
            )
            await message.reply(embed=embed, mention_author=False)

    await bot.process_commands(message)

@bot.check
async def globally_block_disabled_servers(ctx):
    """Global check to block commands in disabled servers"""
    if ctx.guild is None:  # Allow DM commands
        return True
    
    info_cog = bot.get_cog('Information')
    if info_cog and info_cog.is_server_disabled(ctx.guild.id):
        return False
    return True

@bot.event
async def setup_hook():
    await connect_nodes()

    try:
        await bot.load_extension("jishaku")
        print("✅ Loaded Jishaku")
    except Exception as e:
        print(f"❌ Failed to load Jishaku: {e}")

    cog_directories = ["cogs/core", "cogs/music", "cogs/fun", "cogs/admin"]
    
    for cog_dir in cog_directories:
        if os.path.exists(cog_dir):
            for filename in os.listdir(cog_dir):
                if filename.endswith(".py") and filename != "__init__.py":
                    try:
                        await bot.load_extension(f"{cog_dir.replace('/', '.')}.{filename[:-3]}")
                        print(f"✅ Loaded cog: {filename}")
                    except Exception as e:
                        print(f"❌ Failed to load {filename}: {e}")

@bot.event
async def on_ready():
    print(f'{bot.user} is ready!')
    start_flask(bot)  # Start the API when bot is ready

bot.run(TOKEN)