import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN", "")
PREFIX = os.getenv("BOT_PREFIX", ",")

LAVALINK_HOST = os.getenv("LAVALINK_HOST")
LAVALINK_PORT = os.getenv("LAVALINK_PORT")
LAVALINK_PASSWORD = os.getenv("LAVALINK_PASSWORD")
LAVALINK_SECURE = os.getenv("LAVALINK_SECURE", "false").lower() == "true"

OWNER_IDS = [1423011606782021763]

COLOR = 0x495678
APPROVE_EMOJI = "<:approve:1431624157916958795>"
DENY_EMOJI = "<:deny:1431626916036739072>"

STATUS_MESSAGES = [
    "✨ regret.best",
    "✨ regret.best/support", 
    "✨ regret.best/commands",
]

LAVALINK_NODES = [
    {
        "uri": "http://paloma.hidencloud.com:24664",
        "password": "youshallnotpass"
    }
]

HELP_INVITE_URL = "https://discord.com/api/oauth2/authorize?client_id=1429404336747974687&permissions=8&scope=bot"
COG_EMOJIS = {
    "Information": "<:guide:1429426928766418954>",
    "Moderation": "<:certifiedmodlight:1429456818081628280>",
    "Utility": "<:moderationn:1429455420136882268>",
    "Fun": "🎮",
    "Music": "<:spotify:1432059509215334532>",
    "LastFM": "<:lastfm:1432059466400006195>",
    "Economy": "💰",
    "Leveling": "⭐",
    "Admin": "<:discordstuff:1429426935288827905>",
    "VoiceMaster": "🎤",
    "Configuration": "⚙️"
}
