import discord
from discord.ext import commands
from config import COG_EMOJIS, HELP_INVITE_URL, COLOR, APPROVE_EMOJI, DENY_EMOJI

class HelpDropdown(discord.ui.Select):
    def __init__(self, bot, cogs_dict, prefix):
        self.bot = bot
        self.cogs_dict = cogs_dict
        self.prefix = prefix
        self.approve = APPROVE_EMOJI
        self.deny = DENY_EMOJI
        
        # Create options dynamically from cogs
        options = [
            discord.SelectOption(
                label="Home",
                description="Return to the main help menu",
                emoji="<:public:1429426955077554247>"
            )
        ]
        
        # Add a option for each cog
        for cog_name, cog_data in cogs_dict.items():
            options.append(
                discord.SelectOption(
                    label=cog_name,
                    description=cog_data['description'][:100],  # Discord limit
                    emoji=cog_data['emoji']
                )
            )
        
        super().__init__(
            placeholder="Choose a category...",
            min_values=1,
            max_values=1,
            options=options[:25]  # Discord limit of 25 options
        )
    
    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        
        if category == "Home":
            embed = self.create_home_embed()
        else:
            cog_data = self.cogs_dict.get(category)
            if cog_data:
                embed = self.create_category_embed(
                    category,
                    cog_data['emoji'],
                    cog_data['commands']
                )
            else:
                embed = self.create_home_embed()
        
        await interaction.response.edit_message(embed=embed, view=self.view)
    
    def create_home_embed(self):
        embed = discord.Embed(
            title=self.bot.user.name if self.bot.user else "Bot",
            description=f"**Information**:\n```js\n[] = optional, <> = required```\n**Invite**:\n[invite]({HELP_INVITE_URL})",
            color=COLOR
        )
        
        # Set bot thumbnail
        if self.bot.user:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        
        # Add instruction text as footer
        embed.set_footer(text="Select a category from the dropdown menu below\n")
        
        return embed
    
    def create_category_embed(self, title, emoji, commands_list):
        # Get cog description
        cog = self.bot.cogs.get(title)
        cog_description = cog.__doc__.strip() if cog and cog.__doc__ else f"{title} commands"
        
        # Create a comma-separated list of command names with asterisk for groups
        command_names = []
        for cmd in commands_list:
            # Check if command is a group (has subcommands)
            if isinstance(cmd, commands.Group):
                command_names.append(f"{cmd.name}*")
            else:
                command_names.append(cmd.name)
        
        command_names_str = ", ".join(command_names)
        
        # Count total commands
        command_count = len(commands_list)
        
        # Build description with cog description, commands in code block, and count
        description = f"{cog_description}\n```{command_names_str}```\n**{command_count} Commands**"
        
        embed = discord.Embed(
            title=title,
            description=description,
            color=COLOR
        )
        
        return embed

class HelpView(discord.ui.View):
    def __init__(self, bot, cogs_dict, prefix):
        super().__init__(timeout=180)
        self.add_item(HelpDropdown(bot, cogs_dict, prefix))
    
    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


class Help(commands.Cog):
    """Help and information commands"""
    
    def __init__(self, bot):
        self.bot = bot
        
        # Remove default help command
        self.bot.remove_command('help')
        
        # Emoji mapping for cogs
        self.cog_emojis = COG_EMOJIS
    
    def get_cog_emoji(self, cog_name):
        """Get emoji for a cog, or use default"""
        return self.cog_emojis.get(cog_name, "📁")
    
    def get_all_cogs_and_commands(self, guild_id):
        """Fetch all cogs and their commands dynamically"""
        cogs_dict = {}
        
        for cog_name, cog in self.bot.cogs.items():
            # Skip the Help cog itself to avoid recursion
            if cog_name == "Help":
                continue
            
            # Get all commands from this cog
            cog_commands = [
                cmd for cmd in cog.get_commands()
                if not cmd.hidden  # Skip hidden commands
            ]
            
            # If it's the Configuration cog, also add aliases
            if cog_name == "Configuration" and hasattr(cog, 'get_alias_commands') and guild_id:
                try:
                    alias_commands = cog.get_alias_commands(guild_id)
                    cog_commands.extend(alias_commands)
                except:
                    pass
            
            # Only include cogs that have commands
            if cog_commands:
                # Get cog description from docstring or use default
                cog_description = cog.__doc__ or f"{cog_name} commands"
                
                cogs_dict[cog_name] = {
                    'description': cog_description.strip(),
                    'emoji': self.get_cog_emoji(cog_name),
                    'commands': cog_commands
                }
        
        # Add commands that aren't in any cog
        uncategorized_commands = [
            cmd for cmd in self.bot.commands
            if cmd.cog is None and not cmd.hidden
        ]
        
        if uncategorized_commands:
            cogs_dict["Other"] = {
                'description': "Uncategorized commands",
                'emoji': "📦",
                'commands': uncategorized_commands
            }
        
        return cogs_dict
    
    @commands.command(name="help", aliases=["h", "commands"])
    async def help(self, ctx, *, command: str = None):
        """
        Shows help menu or information about a specific command
        
        Usage:
        help - Shows this menu
        help <command> - Shows info about a specific command
        """
        
        prefix = ctx.prefix
        
        # If asking for specific command
        if command:
            cmd = self.bot.get_command(command)
            
            # If not found as a command, check if it's an alias
            if not cmd and ctx.guild:
                config_cog = self.bot.get_cog("Configuration")
                if config_cog and hasattr(config_cog, 'get_alias'):
                    real_command = config_cog.get_alias(ctx.guild.id, command)
                    if real_command:
                        # Show alias info
                        embed = discord.Embed(
                            title=f"Alias: {command} • Configuration Module",
                            description=f"Alias for `{real_command}`",
                            color=COLOR
                        )
                        
                        embed.add_field(
                            name="",
                            value=f"```js\nSyntax: {prefix}{command}\nExample: {prefix}{command}\n```",
                            inline=False
                        )
                        
                        embed.add_field(
                            name="Permissions",
                            value="None",
                            inline=False
                        )
                        
                        embed.set_footer(
                            text=f"Aliases: none",
                            icon_url=self.bot.user.display_avatar.url if self.bot.user else None
                        )
                        
                        await ctx.send(embed=embed)
                        return
            
            if cmd:
                # Get cog name
                cog_name = cmd.cog.qualified_name if cmd.cog else "No category"
                
                embed = discord.Embed(
                    title=f"Command: {cmd.name} • {cog_name} Module",
                    description=cmd.help or cmd.short_doc or "No description provided",
                    color=COLOR
                )
                
                # Add syntax and example in code block
                syntax = f"Syntax: {prefix}{cmd.name}"
                if cmd.signature:
                    syntax += f" {cmd.signature}"
                elif isinstance(cmd, commands.Group):
                    syntax += " [subcommand]"
                
                example = f"Example: {prefix}{cmd.name}"
                if isinstance(cmd, commands.Group) and cmd.commands:
                    # Show first subcommand as example
                    first_subcommand = list(cmd.commands)[0]
                    example += f" {first_subcommand.name}"
                
                embed.add_field(
                    name="",
                    value=f"```js\n{syntax}\n{example}\n```",
                    inline=False
                )
                
                # If it's a group, show available subcommands
                if isinstance(cmd, commands.Group):
                    subcommands = [subcmd.name for subcmd in cmd.commands if not subcmd.hidden]
                    if subcommands:
                        embed.add_field(
                            name="Subcommands",
                            value=", ".join(subcommands),
                            inline=False
                        )
                
                # Add permissions
                permissions = "None"
                if hasattr(cmd, 'checks') and cmd.checks:
                    perms = []
                    for check in cmd.checks:
                        check_str = str(check)
                        # Extract permission names from checks
                        if 'has_permissions' in check_str:
                            # Try to get the actual permission requirements
                            if hasattr(check, '__closure__') and check.__closure__:
                                for cell in check.__closure__:
                                    if hasattr(cell.cell_contents, 'items'):
                                        for key, value in cell.cell_contents.items():
                                            if value:
                                                perms.append(key.replace('_', ' ').title())
                        elif 'is_owner' in check_str:
                            perms.append("Bot Owner")
                        elif 'bot_has_permissions' in check_str:
                            continue  # Skip bot permissions
                    
                    if perms:
                        permissions = ", ".join(perms)
                
                embed.add_field(
                    name="Permissions",
                    value=permissions,
                    inline=False
                )
                
                # Add aliases with bot avatar
                aliases_text = "none" if not cmd.aliases else ", ".join(cmd.aliases)
                footer_text = f"Aliases: {aliases_text}"
                    
                embed.set_footer(
                    text=footer_text,
                    icon_url=self.bot.user.display_avatar.url if self.bot.user else None
                )
                
                await ctx.send(embed=embed)
                return
            else:
                await ctx.send(embed=discord.Embed(description=f"<:deny:1431626916036739072> Command `{command}` not found!", color=COLOR))
                return
        
        # Show full help menu
        guild_id = ctx.guild.id if ctx.guild else None
        cogs_dict = self.get_all_cogs_and_commands(guild_id)
        
        if not cogs_dict:
            await ctx.send("No commands available!")
            return
        
        # Create simple home embed
        embed = discord.Embed(
            title=self.bot.user.name if self.bot.user else "Bot",
            description=f"**Information**:\n```js\n[] = optional, <> = required```\n**Invite**:\n[invite]({HELP_INVITE_URL})",
            color=COLOR
        )
        
        # Set bot thumbnail
        if self.bot.user:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        
        # Add instruction text as footer
        embed.set_footer(text="Select a category from the dropdown menu below\n")
        
        view = HelpView(self.bot, cogs_dict, prefix)
        await ctx.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(Help(bot))