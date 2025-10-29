from flask import Flask, jsonify
from flask_cors import CORS
from threading import Thread
import datetime
import os

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

start_time = datetime.datetime.utcnow()
bot_instance = None

@app.route('/api', methods=['GET'])
def get_all_stats():
    """Get all bot information in one endpoint"""
    if bot_instance is None:
        return jsonify({
            'error': 'Bot instance not initialized'
        }), 503
    
    # Calculate uptime
    uptime_seconds = (datetime.datetime.utcnow() - start_time).total_seconds()
    hours, remainder = divmod(int(uptime_seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime = f"{hours}h {minutes}m {seconds}s"
    
    # Calculate stats
    total_guilds = len(bot_instance.guilds)
    total_users = sum(guild.member_count for guild in bot_instance.guilds)
    total_channels = sum(len(guild.channels) for guild in bot_instance.guilds)
    
    # Get command count
    command_count = len(bot_instance.commands)
    
    # Get guilds data
    guilds_data = []
    for guild in bot_instance.guilds:
        guilds_data.append({
            'id': str(guild.id),
            'name': guild.name,
            'member_count': guild.member_count,
            'icon_url': str(guild.icon.url) if guild.icon else None
        })
    
    # Combine everything
    response = {
        'status': 'online',
        'bot': {
            'name': bot_instance.user.name if bot_instance.user else 'Unknown',
            'id': str(bot_instance.user.id) if bot_instance.user else None,
            'discriminator': bot_instance.user.discriminator if bot_instance.user else None,
            'avatar_url': str(bot_instance.user.avatar.url) if bot_instance.user and bot_instance.user.avatar else None
        },
        'stats': {
            'servers': total_guilds,
            'users': total_users,
            'channels': total_channels,
            'commands': command_count,
            'uptime': uptime,
            'latency': round(bot_instance.latency * 1000, 2)
        },
        'guilds': {
            'total': len(guilds_data),
            'list': guilds_data
        },
        'ready': bot_instance.is_ready()
    }
    
    return jsonify(response)

@app.route('/api/commands', methods=['GET'])
def get_commands():
    """Get all bot commands with their details"""
    if bot_instance is None:
        return jsonify({
            'error': 'Bot instance not initialized'
        }), 503
    
    commands_data = []
    
    for command in bot_instance.commands:
        # Get command category from cog name
        category = command.cog_name.lower() if command.cog_name else 'uncategorized'
        
        # Get command parameters/arguments
        arguments = []
        if command.clean_params:
            for param_name, param in command.clean_params.items():
                arg_info = param_name
                # Check if parameter has a default value (optional)
                if param.default != param.empty:
                    arg_info = f"{param_name} (optional)"
                arguments.append(arg_info)
        
        # Determine required permissions
        permissions = 'none'
        if command.checks:
            # Try to extract permission requirements from checks
            for check in command.checks:
                check_name = check.__qualname__ if hasattr(check, '__qualname__') else str(check)
                if 'administrator' in check_name.lower():
                    permissions = 'administrator'
                elif 'manage_guild' in check_name.lower():
                    permissions = 'manage server'
                elif 'manage_channels' in check_name.lower():
                    permissions = 'manage channels'
                elif 'manage_roles' in check_name.lower():
                    permissions = 'manage roles'
                elif 'manage_messages' in check_name.lower():
                    permissions = 'manage messages'
                elif 'kick_members' in check_name.lower():
                    permissions = 'kick members'
                elif 'ban_members' in check_name.lower():
                    permissions = 'ban members'
                elif 'moderate_members' in check_name.lower():
                    permissions = 'moderate members'
        
        # Check if command is featured (you can customize this logic)
        featured = False  # You can add custom logic to mark certain commands as featured
        
        command_info = {
            'name': command.name,
            'category': category,
            'description': command.help or command.brief or 'No description available',
            'arguments': arguments if arguments else [],
            'permissions': permissions,
            'featured': featured,
            'aliases': list(command.aliases) if command.aliases else [],
            'enabled': command.enabled,
            'hidden': command.hidden
        }
        
        # Only include non-hidden commands
        if not command.hidden:
            commands_data.append(command_info)
    
    # Group commands by category
    categories = {}
    for cmd in commands_data:
        cat = cmd['category']
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(cmd)
    
    # Count commands per category
    category_counts = {cat: len(cmds) for cat, cmds in categories.items()}
    
    response = {
        'total': len(commands_data),
        'commands': commands_data,
        'categories': category_counts,
        'grouped': categories
    }
    
    return jsonify(response)

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'bot_ready': bot_instance is not None and bot_instance.is_ready()
    })

@app.route('/status')
def status():
    """Legacy status endpoint for backwards compatibility"""
    if bot_instance is None:
        return jsonify({"error": "Bot not ready yet"}), 503
    
    uptime_seconds = (datetime.datetime.utcnow() - start_time).total_seconds()
    hours, remainder = divmod(int(uptime_seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime = f"{hours}h {minutes}m {seconds}s"
    
    data = {
        "online": True,
        "uptime": uptime,
        "ping": round(bot_instance.latency * 1000),
        "servers": len(bot_instance.guilds),
        "users": sum(g.member_count for g in bot_instance.guilds)
    }
    return jsonify(data)

def run():
    port = int(os.environ.get('PORT', 30214))
    app.run(host='0.0.0.0', port=port, debug=False)

def start_flask(bot):
    """Start Flask API in a separate thread"""
    global bot_instance, start_time
    bot_instance = bot
    start_time = datetime.datetime.utcnow()
    Thread(target=run, daemon=True).start()