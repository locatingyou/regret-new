import discord
from discord.ext import commands
import sqlite3
import os
from datetime import datetime, timedelta
import random
import asyncio
from config import COLOR

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = "data/economy.db"
        self.purple = COLOR
        self.work_cooldowns = {}
        self.setup_database()
        
    def setup_database(self):
        """Initialize the database and create tables if they don't exist"""
        os.makedirs("data", exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Create users table
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0,
            bank INTEGER DEFAULT 0,
            last_daily TEXT,
            last_weekly TEXT,
            inventory TEXT DEFAULT '{}'
        )''')
        
        conn.commit()
        conn.close()
    
    def get_user(self, user_id):
        """Get user data from database"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
        
        if not user:
            c.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
            conn.commit()
            c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            user = c.fetchone()
        
        conn.close()
        return user
    
    def update_balance(self, user_id, amount, bank=False):
        """Update user balance"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        if bank:
            c.execute("UPDATE users SET bank = bank + ? WHERE user_id = ?", (amount, user_id))
        else:
            c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        
        conn.commit()
        conn.close()
    
    @commands.command(name="balance", aliases=["bal", "money"])
    async def balance(self, ctx, member: discord.Member = None):
        """Check balance of yourself or another user"""
        target = member or ctx.author
        user_data = self.get_user(target.id)
        
        embed = discord.Embed(
            title=f"💰 {target.display_name}'s Balance",
            color=self.purple
        )
        embed.add_field(name="Wallet", value=f"${user_data[1]:,}", inline=True)
        embed.add_field(name="Bank", value=f"${user_data[2]:,}", inline=True)
        embed.add_field(name="Total", value=f"${user_data[1] + user_data[2]:,}", inline=True)
        embed.set_thumbnail(url=target.display_avatar.url)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="daily")
    async def daily(self, ctx):
        """Claim daily reward"""
        user_data = self.get_user(ctx.author.id)
        last_daily = user_data[3]
        
        if last_daily:
            last_time = datetime.fromisoformat(last_daily)
            if datetime.now() - last_time < timedelta(days=1):
                time_left = timedelta(days=1) - (datetime.now() - last_time)
                hours, remainder = divmod(time_left.seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                
                embed = discord.Embed(
                    title="⏰ Daily Cooldown",
                    description=f"You've already claimed your daily reward!\nCome back in **{hours} hours** and **{minutes} minutes**",
                    color=self.purple
                )
                await ctx.send(embed=embed)
                return
        
        amount = random.randint(500, 1500)
        self.update_balance(ctx.author.id, amount)
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("UPDATE users SET last_daily = ? WHERE user_id = ?", 
                 (datetime.now().isoformat(), ctx.author.id))
        conn.commit()
        conn.close()
        
        embed = discord.Embed(
            title="🎁 Daily Reward Claimed!",
            description=f"You received **${amount:,}**!",
            color=self.purple
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="weekly")
    async def weekly(self, ctx):
        """Claim weekly reward"""
        user_data = self.get_user(ctx.author.id)
        last_weekly = user_data[4]
        
        if last_weekly:
            last_time = datetime.fromisoformat(last_weekly)
            if datetime.now() - last_time < timedelta(days=7):
                time_left = timedelta(days=7) - (datetime.now() - last_time)
                days = time_left.days
                hours, remainder = divmod(time_left.seconds, 3600)
                
                embed = discord.Embed(
                    title="⏰ Weekly Cooldown",
                    description=f"You've already claimed your weekly reward!\nCome back in **{days} days** and **{hours} hours**",
                    color=self.purple
                )
                await ctx.send(embed=embed)
                return
        
        amount = random.randint(5000, 10000)
        self.update_balance(ctx.author.id, amount)
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("UPDATE users SET last_weekly = ? WHERE user_id = ?", 
                 (datetime.now().isoformat(), ctx.author.id))
        conn.commit()
        conn.close()
        
        embed = discord.Embed(
            title="🎉 Weekly Reward Claimed!",
            description=f"You received **${amount:,}**!",
            color=self.purple
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="deposit", aliases=["dep"])
    async def deposit(self, ctx, amount: str):
        """Deposit money into your bank"""
        user_data = self.get_user(ctx.author.id)
        wallet = user_data[1]
        
        if amount.lower() == "all":
            amount = wallet
        else:
            try:
                amount = int(amount)
            except ValueError:
                embed = discord.Embed(
                    title="❌ Invalid Amount",
                    description="Please enter a valid number or 'all'",
                    color=self.purple
                )
                await ctx.send(embed=embed)
                return
        
        if amount <= 0:
            embed = discord.Embed(
                title="❌ Invalid Amount",
                description="Amount must be positive!",
                color=self.purple
            )
            await ctx.send(embed=embed)
            return
        
        if amount > wallet:
            embed = discord.Embed(
                title="❌ Insufficient Funds",
                description=f"You only have **${wallet:,}** in your wallet!",
                color=self.purple
            )
            await ctx.send(embed=embed)
            return
        
        self.update_balance(ctx.author.id, -amount)
        self.update_balance(ctx.author.id, amount, bank=True)
        
        embed = discord.Embed(
            title="🏦 Deposit Successful",
            description=f"Deposited **${amount:,}** into your bank!",
            color=self.purple
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="withdraw", aliases=["with"])
    async def withdraw(self, ctx, amount: str):
        """Withdraw money from your bank"""
        user_data = self.get_user(ctx.author.id)
        bank = user_data[2]
        
        if amount.lower() == "all":
            amount = bank
        else:
            try:
                amount = int(amount)
            except ValueError:
                embed = discord.Embed(
                    title="❌ Invalid Amount",
                    description="Please enter a valid number or 'all'",
                    color=self.purple
                )
                await ctx.send(embed=embed)
                return
        
        if amount <= 0:
            embed = discord.Embed(
                title="❌ Invalid Amount",
                description="Amount must be positive!",
                color=self.purple
            )
            await ctx.send(embed=embed)
            return
        
        if amount > bank:
            embed = discord.Embed(
                title="❌ Insufficient Funds",
                description=f"You only have **${bank:,}** in your bank!",
                color=self.purple
            )
            await ctx.send(embed=embed)
            return
        
        self.update_balance(ctx.author.id, amount)
        self.update_balance(ctx.author.id, -amount, bank=True)
        
        embed = discord.Embed(
            title="🏦 Withdrawal Successful",
            description=f"Withdrew **${amount:,}** from your bank!",
            color=self.purple
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="give", aliases=["pay"])
    async def give(self, ctx, member: discord.Member, amount: int):
        """Give money to another user"""
        if member.id == ctx.author.id:
            embed = discord.Embed(
                title="❌ Invalid Action",
                description="You can't give money to yourself!",
                color=self.purple
            )
            await ctx.send(embed=embed)
            return
        
        if member.bot:
            embed = discord.Embed(
                title="❌ Invalid Action",
                description="You can't give money to bots!",
                color=self.purple
            )
            await ctx.send(embed=embed)
            return
        
        if amount <= 0:
            embed = discord.Embed(
                title="❌ Invalid Amount",
                description="Amount must be positive!",
                color=self.purple
            )
            await ctx.send(embed=embed)
            return
        
        user_data = self.get_user(ctx.author.id)
        wallet = user_data[1]
        
        if amount > wallet:
            embed = discord.Embed(
                title="❌ Insufficient Funds",
                description=f"You only have **${wallet:,}** in your wallet!",
                color=self.purple
            )
            await ctx.send(embed=embed)
            return
        
        self.update_balance(ctx.author.id, -amount)
        self.update_balance(member.id, amount)
        
        embed = discord.Embed(
            title="💸 Money Sent",
            description=f"You gave **${amount:,}** to {member.mention}!",
            color=self.purple
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="work")
    async def work(self, ctx):
        """Work to earn money (10 second cooldown)"""
        user_id = ctx.author.id
        
        # Check cooldown
        if user_id in self.work_cooldowns:
            time_left = 60 - (datetime.now() - self.work_cooldowns[user_id]).total_seconds()
            if time_left > 0:
                embed = discord.Embed(
                    title="⏰ Work Cooldown",
                    description=f"You need to rest! Try again in **{int(time_left)} seconds**",
                    color=self.purple
                )
                await ctx.send(embed=embed)
                return
        
        jobs = [
            ("programming", "💻"),
            ("teaching", "👨‍🏫"),
            ("cooking", "👨‍🍳"),
            ("cleaning", "🧹"),
            ("delivery driving", "🚗"),
            ("gardening", "🌱"),
            ("writing", "✍️"),
            ("painting", "🎨")
        ]
        
        job, emoji = random.choice(jobs)
        amount = random.randint(100, 500)
        
        self.update_balance(ctx.author.id, amount)
        self.work_cooldowns[user_id] = datetime.now()
        
        embed = discord.Embed(
            title=f"{emoji} Work Complete!",
            description=f"You worked as a **{job}** and earned **${amount:,}**!",
            color=self.purple
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="slots", aliases=["slot"])
    async def slots(self, ctx, bet: int):
        """Play the slot machine"""
        if bet <= 0:
            embed = discord.Embed(
                title="❌ Invalid Bet",
                description="Bet must be positive!",
                color=self.purple
            )
            await ctx.send(embed=embed)
            return
        
        user_data = self.get_user(ctx.author.id)
        wallet = user_data[1]
        
        if bet > wallet:
            embed = discord.Embed(
                title="❌ Insufficient Funds",
                description=f"You only have **${wallet:,}** in your wallet!",
                color=self.purple
            )
            await ctx.send(embed=embed)
            return
        
        emojis = ["🍒", "🍋", "🍊", "🍇", "💎", "7️⃣"]
        
        # Create initial spinning message
        embed = discord.Embed(
            title="🎰 Slot Machine",
            description="🎰 | 🎰 | 🎰\n\n*Spinning...*",
            color=self.purple
        )
        message = await ctx.send(embed=embed)
        
        # Animate the slots
        final_results = [random.choice(emojis) for _ in range(3)]
        
        # Animation frames
        for i in range(3):
            await asyncio.sleep(0.7)
            current = [random.choice(emojis) if j > i else final_results[j] for j in range(3)]
            embed.description = f"{current[0]} | {current[1]} | {current[2]}\n\n*Spinning...*"
            await message.edit(embed=embed)
        
        # Final result
        await asyncio.sleep(0.5)
        results = final_results
        
        # Calculate winnings
        if results[0] == results[1] == results[2]:
            if results[0] == "💎":
                multiplier = 10
            elif results[0] == "7️⃣":
                multiplier = 7
            else:
                multiplier = 3
            winnings = bet * multiplier
            self.update_balance(ctx.author.id, winnings)
            result_text = f"🎉 **JACKPOT!** You won **${winnings:,}**!"
        elif results[0] == results[1] or results[1] == results[2] or results[0] == results[2]:
            winnings = bet
            self.update_balance(ctx.author.id, 0)
            result_text = f"You got your bet back! **${bet:,}**"
        else:
            self.update_balance(ctx.author.id, -bet)
            result_text = f"💸 You lost **${bet:,}**"
        
        embed = discord.Embed(
            title="🎰 Slot Machine",
            description=f"{results[0]} | {results[1]} | {results[2]}\n\n{result_text}",
            color=self.purple
        )
        
        await message.edit(embed=embed)
    
    @commands.command(name="coinflip", aliases=["cf", "flip"])
    async def coinflip(self, ctx, bet: int, choice: str):
        """Flip a coin - heads or tails"""
        choice = choice.lower()
        if choice not in ["heads", "tails", "h", "t"]:
            embed = discord.Embed(
                title="❌ Invalid Choice",
                description="Choose **heads** (h) or **tails** (t)!",
                color=self.purple
            )
            await ctx.send(embed=embed)
            return
        
        if bet <= 0:
            embed = discord.Embed(
                title="❌ Invalid Bet",
                description="Bet must be positive!",
                color=self.purple
            )
            await ctx.send(embed=embed)
            return
        
        user_data = self.get_user(ctx.author.id)
        wallet = user_data[1]
        
        if bet > wallet:
            embed = discord.Embed(
                title="❌ Insufficient Funds",
                description=f"You only have **${wallet:,}** in your wallet!",
                color=self.purple
            )
            await ctx.send(embed=embed)
            return
        
        # Normalize choice
        if choice in ["h", "heads"]:
            choice = "heads"
        else:
            choice = "tails"
        
        result = random.choice(["heads", "tails"])
        
        if result == choice:
            winnings = bet * 2
            self.update_balance(ctx.author.id, bet)
            outcome = f"🎉 **You won!** +**${bet:,}**"
        else:
            self.update_balance(ctx.author.id, -bet)
            outcome = f"💸 **You lost!** -**${bet:,}**"
        
        embed = discord.Embed(
            title="🪙 Coin Flip",
            description=f"You chose: **{choice}**\nResult: **{result}**\n\n{outcome}",
            color=self.purple
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="dice", aliases=["roll"])
    async def dice(self, ctx, bet: int, guess: int):
        """Roll a dice (1-6) and guess the number"""
        if guess < 1 or guess > 6:
            embed = discord.Embed(
                title="❌ Invalid Guess",
                description="Guess must be between 1 and 6!",
                color=self.purple
            )
            await ctx.send(embed=embed)
            return
        
        if bet <= 0:
            embed = discord.Embed(
                title="❌ Invalid Bet",
                description="Bet must be positive!",
                color=self.purple
            )
            await ctx.send(embed=embed)
            return
        
        user_data = self.get_user(ctx.author.id)
        wallet = user_data[1]
        
        if bet > wallet:
            embed = discord.Embed(
                title="❌ Insufficient Funds",
                description=f"You only have **${wallet:,}** in your wallet!",
                color=self.purple
            )
            await ctx.send(embed=embed)
            return
        
        result = random.randint(1, 6)
        
        if result == guess:
            winnings = bet * 6
            self.update_balance(ctx.author.id, winnings - bet)
            outcome = f"🎉 **Perfect guess!** You won **${winnings:,}**!"
        else:
            self.update_balance(ctx.author.id, -bet)
            outcome = f"💸 **Wrong guess!** You lost **${bet:,}**"
        
        embed = discord.Embed(
            title="🎲 Dice Roll",
            description=f"You guessed: **{guess}**\nRolled: **{result}**\n\n{outcome}",
            color=self.purple
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="blackjack", aliases=["bj"])
    async def blackjack(self, ctx, bet: int):
        """Play a game of blackjack"""
        if bet <= 0:
            embed = discord.Embed(
                title="❌ Invalid Bet",
                description="Bet must be positive!",
                color=self.purple
            )
            await ctx.send(embed=embed)
            return
        
        user_data = self.get_user(ctx.author.id)
        wallet = user_data[1]
        
        if bet > wallet:
            embed = discord.Embed(
                title="❌ Insufficient Funds",
                description=f"You only have **${wallet:,}** in your wallet!",
                color=self.purple
            )
            await ctx.send(embed=embed)
            return
        
        # Simple blackjack simulation
        def card_value():
            return random.randint(1, 11)
        
        player_hand = [card_value(), card_value()]
        dealer_hand = [card_value(), card_value()]
        
        player_total = sum(player_hand)
        dealer_total = sum(dealer_hand)
        
        # Dealer draws until 17+
        while dealer_total < 17:
            dealer_hand.append(card_value())
            dealer_total = sum(dealer_hand)
        
        # Determine winner
        if player_total > 21:
            self.update_balance(ctx.author.id, -bet)
            result = f"💸 **BUST!** You went over 21 and lost **${bet:,}**"
        elif dealer_total > 21:
            winnings = bet * 2
            self.update_balance(ctx.author.id, bet)
            result = f"🎉 **Dealer busts!** You won **${bet:,}**!"
        elif player_total > dealer_total:
            winnings = bet * 2
            self.update_balance(ctx.author.id, bet)
            result = f"🎉 **You win!** You won **${bet:,}**!"
        elif player_total < dealer_total:
            self.update_balance(ctx.author.id, -bet)
            result = f"💸 **Dealer wins!** You lost **${bet:,}**"
        else:
            result = f"🤝 **Push!** It's a tie, you keep your **${bet:,}**"
        
        embed = discord.Embed(
            title="🃏 Blackjack",
            description=f"**Your hand:** {player_total}\n**Dealer's hand:** {dealer_total}\n\n{result}",
            color=self.purple
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="leaderboard", aliases=["lb", "top"])
    async def leaderboard(self, ctx):
        """Display economy leaderboard"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("SELECT user_id, balance + bank as total FROM users ORDER BY total DESC LIMIT 10")
        top_users = c.fetchall()
        conn.close()
        
        if not top_users:
            embed = discord.Embed(
                title="📊 Economy Leaderboard",
                description="No users found!",
                color=self.purple
            )
            await ctx.send(embed=embed)
            return
        
        description = ""
        for idx, (user_id, total) in enumerate(top_users, 1):
            user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
            medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"`#{idx}`"
            description += f"{medal} **{user.display_name}** - ${total:,}\n"
        
        embed = discord.Embed(
            title="📊 Economy Leaderboard",
            description=description,
            color=self.purple
        )
        
        await ctx.send(embed=embed)
    
    # NEW COMMANDS BELOW
    
    @commands.command(name="rob")
    @commands.cooldown(1, 3600, commands.BucketType.user)
    async def rob(self, ctx, member: discord.Member):
        """Attempt to rob another user (1 hour cooldown)"""
        if member.id == ctx.author.id:
            embed = discord.Embed(
                title="❌ Invalid Action",
                description="You can't rob yourself!",
                color=self.purple
            )
            await ctx.send(embed=embed)
            ctx.command.reset_cooldown(ctx)
            return
        
        if member.bot:
            embed = discord.Embed(
                title="❌ Invalid Action",
                description="You can't rob bots!",
                color=self.purple
            )
            await ctx.send(embed=embed)
            ctx.command.reset_cooldown(ctx)
            return
        
        target_data = self.get_user(member.id)
        target_wallet = target_data[1]
        
        if target_wallet < 100:
            embed = discord.Embed(
                title="❌ Not Worth It",
                description=f"{member.mention} doesn't have enough money to rob!",
                color=self.purple
            )
            await ctx.send(embed=embed)
            ctx.command.reset_cooldown(ctx)
            return
        
        user_data = self.get_user(ctx.author.id)
        user_wallet = user_data[1]
        
        # 40% success rate
        success = random.random() < 0.4
        
        if success:
            # Rob 20-50% of their wallet
            amount = random.randint(int(target_wallet * 0.2), int(target_wallet * 0.5))
            self.update_balance(ctx.author.id, amount)
            self.update_balance(member.id, -amount)
            
            embed = discord.Embed(
                title="💰 Robbery Successful!",
                description=f"You successfully robbed **${amount:,}** from {member.mention}!",
                color=self.purple
            )
        else:
            # Pay 25% of your wallet as fine
            fine = int(user_wallet * 0.25) if user_wallet > 0 else 0
            if fine > 0:
                self.update_balance(ctx.author.id, -fine)
            
            embed = discord.Embed(
                title="🚔 Robbery Failed!",
                description=f"You got caught and paid a fine of **${fine:,}**!",
                color=self.purple
            )
        
        await ctx.send(embed=embed)
    
    @rob.error
    async def rob_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            minutes, seconds = divmod(int(error.retry_after), 60)
            embed = discord.Embed(
                title="⏰ Robbery Cooldown",
                description=f"You need to wait **{minutes} minutes** and **{seconds} seconds** before robbing again!",
                color=self.purple
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="beg")
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def beg(self, ctx):
        """Beg for money (30 second cooldown)"""
        responses = [
            ("A kind stranger", random.randint(50, 150)),
            ("A wealthy businessman", random.randint(100, 300)),
            ("An old lady", random.randint(25, 100)),
            ("A generous person", random.randint(75, 200)),
            ("Someone passing by", random.randint(30, 120)),
        ]
        
        # 70% success rate
        if random.random() < 0.7:
            person, amount = random.choice(responses)
            self.update_balance(ctx.author.id, amount)
            
            embed = discord.Embed(
                title="🙏 Begging Successful",
                description=f"**{person}** gave you **${amount:,}**!",
                color=self.purple
            )
        else:
            embed = discord.Embed(
                title="😔 Begging Failed",
                description="Nobody gave you anything...",
                color=self.purple
            )
        
        await ctx.send(embed=embed)
    
    @beg.error
    async def beg_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            seconds = int(error.retry_after)
            embed = discord.Embed(
                title="⏰ Begging Cooldown",
                description=f"Wait **{seconds} seconds** before begging again!",
                color=self.purple
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="crime")
    @commands.cooldown(1, 600, commands.BucketType.user)
    async def crime(self, ctx):
        """Commit a crime for big rewards (10 minute cooldown)"""
        crimes = [
            ("robbed a bank", 5000, 10000),
            ("hacked a corporation", 7000, 12000),
            ("stole a luxury car", 4000, 8000),
            ("smuggled contraband", 6000, 11000),
            ("ran an illegal casino", 5500, 9500),
        ]
        
        crime_desc, min_reward, max_reward = random.choice(crimes)
        
        # 50% success rate
        if random.random() < 0.5:
            amount = random.randint(min_reward, max_reward)
            self.update_balance(ctx.author.id, amount)
            
            embed = discord.Embed(
                title="😈 Crime Successful!",
                description=f"You **{crime_desc}** and got away with **${amount:,}**!",
                color=self.purple
            )
        else:
            user_data = self.get_user(ctx.author.id)
            user_wallet = user_data[1]
            fine = int(user_wallet * 0.4) if user_wallet > 0 else 0
            
            if fine > 0:
                self.update_balance(ctx.author.id, -fine)
            
            embed = discord.Embed(
                title="🚨 Crime Failed!",
                description=f"You got caught trying to **{crime_desc[:-1]}**!\nYou paid a fine of **${fine:,}**!",
                color=self.purple
            )
        
        await ctx.send(embed=embed)
    
    @crime.error
    async def crime_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            minutes, seconds = divmod(int(error.retry_after), 60)
            embed = discord.Embed(
                title="⏰ Crime Cooldown",
                description=f"You need to wait **{minutes} minutes** and **{seconds} seconds** before committing another crime!",
                color=self.purple
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="gamble", aliases=["bet"])
    async def gamble(self, ctx, amount: int):
        """Gamble your money with 45% win chance"""
        if amount <= 0:
            embed = discord.Embed(
                title="❌ Invalid Amount",
                description="Amount must be positive!",
                color=self.purple
            )
            await ctx.send(embed=embed)
            return
        
        user_data = self.get_user(ctx.author.id)
        wallet = user_data[1]
        
        if amount > wallet:
            embed = discord.Embed(
                title="❌ Insufficient Funds",
                description=f"You only have **${wallet:,}** in your wallet!",
                color=self.purple
            )
            await ctx.send(embed=embed)
            return
        
        # 45% win chance
        if random.random() < 0.45:
            self.update_balance(ctx.author.id, amount)
            embed = discord.Embed(
                title="🎰 Gamble Won!",
                description=f"You won **${amount:,}**!\nNew balance: **${wallet + amount:,}**",
                color=self.purple
            )
        else:
            self.update_balance(ctx.author.id, -amount)
            embed = discord.Embed(
                title="💸 Gamble Lost!",
                description=f"You lost **${amount:,}**!\nNew balance: **${wallet - amount:,}**",
                color=self.purple
            )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="search")
    @commands.cooldown(1, 45, commands.BucketType.user)
    async def search(self, ctx):
        """Search random places for money (45 second cooldown)"""
        places = [
            ("your couch cushions", 50, 200),
            ("a parking lot", 75, 250),
            ("the trash", 30, 150),
            ("under a bridge", 40, 180),
            ("a park bench", 60, 220),
            ("an old jacket", 80, 300),
            ("a dumpster", 45, 175),
            ("the sidewalk", 35, 160),
        ]
        
        place, min_amount, max_amount = random.choice(places)
        amount = random.randint(min_amount, max_amount)
        
        self.update_balance(ctx.author.id, amount)
        
        embed = discord.Embed(
            title="🔍 Search Complete",
            description=f"You searched **{place}** and found **${amount:,}**!",
            color=self.purple
        )
        
        await ctx.send(embed=embed)
    
    @search.error
    async def search_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            seconds = int(error.retry_after)
            embed = discord.Embed(
                title="⏰ Search Cooldown",
                description=f"Wait **{seconds} seconds** before searching again!",
                color=self.purple
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="fish")
    @commands.cooldown(1, 20, commands. BucketType.user)
    async def fish(self, ctx):
        """Go fishing to earn money (20 second cooldown)"""
        catches = [
            ("common fish", "🐟", 100, 300),
            ("rare fish", "🐠", 300, 600),
            ("tropical fish", "🐡", 400, 800),
            ("shark", "🦈", 800, 1500),
            ("octopus", "🐙", 500, 1000),
            ("lobster", "🦞", 600, 1200),
            ("old boot", "👢", 10, 50),
            ("treasure chest", "💎", 1000, 2000),
        ]
        
        catch, emoji, min_amount, max_amount = random.choice(catches)
        amount = random.randint(min_amount, max_amount)
        
        self.update_balance(ctx.author.id, amount)
        
        embed = discord.Embed(
            title="🎣 Fishing Success!",
            description=f"You caught a **{catch}** {emoji} and sold it for **${amount:,}**!",
            color=self.purple
        )
        
        await ctx.send(embed=embed)
    
    @fish.error
    async def fish_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            seconds = int(error.retry_after)
            embed = discord.Embed(
                title="⏰ Fishing Cooldown",
                description=f"Your fishing rod needs a break! Wait **{seconds} seconds**",
                color=self.purple
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="hunt")
    @commands.cooldown(1, 40, commands.BucketType.user)
    async def hunt(self, ctx):
        """Go hunting for animals (40 second cooldown)"""
        animals = [
            ("rabbit", "🐰", 200, 400),
            ("deer", "🦌", 500, 800),
            ("bear", "🐻", 800, 1200),
            ("wolf", "🐺", 600, 1000),
            ("fox", "🦊", 400, 700),
            ("boar", "🐗", 450, 750),
            ("duck", "🦆", 150, 350),
            ("legendary dragon", "🐉", 2000, 4000),
        ]
        
        # 75% success rate
        if random.random() < 0.75:
            animal, emoji, min_amount, max_amount = random.choice(animals)
            amount = random.randint(min_amount, max_amount)
            
            self.update_balance(ctx.author.id, amount)
            
            embed = discord.Embed(
                title="🏹 Successful Hunt!",
                description=f"You hunted a **{animal}** {emoji} and sold it for **${amount:,}**!",
                color=self.purple
            )
        else:
            embed = discord.Embed(
                title="❌ Hunt Failed",
                description="You didn't catch anything this time...",
                color=self.purple
            )
        
        await ctx.send(embed=embed)
    
    @hunt.error
    async def hunt_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            seconds = int(error.retry_after)
            embed = discord.Embed(
                title="⏰ Hunting Cooldown",
                description=f"You need to rest! Wait **{seconds} seconds** before hunting again",
                color=self.purple
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="mine")
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def mine(self, ctx):
        """Mine for valuable resources (1 minute cooldown)"""
        resources = [
            ("coal", "⚫", 100, 250),
            ("iron", "⚪", 200, 400),
            ("gold", "🟡", 500, 800),
            ("diamond", "💎", 1000, 1500),
            ("emerald", "💚", 800, 1200),
            ("ruby", "❤️", 700, 1100),
            ("sapphire", "💙", 750, 1150),
            ("ancient artifact", "👑", 2000, 3000),
        ]
        
        resource, emoji, min_amount, max_amount = random.choice(resources)
        amount = random.randint(min_amount, max_amount)
        
        self.update_balance(ctx.author.id, amount)
        
        embed = discord.Embed(
            title="⛏️ Mining Success!",
            description=f"You mined **{resource}** {emoji} and sold it for **${amount:,}**!",
            color=self.purple
        )
        
        await ctx.send(embed=embed)
    
    @mine.error
    async def mine_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            seconds = int(error.retry_after)
            embed = discord.Embed(
                title="⏰ Mining Cooldown",
                description=f"Your pickaxe needs sharpening! Wait **{seconds} seconds**",
                color=self.purple
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="highlow", aliases=["hl"])
    async def highlow(self, ctx, bet: int):
        """Guess if the next number will be higher or lower"""
        if bet <= 0:
            embed = discord.Embed(
                title="❌ Invalid Bet",
                description="Bet must be positive!",
                color=self.purple
            )
            await ctx.send(embed=embed)
            return
        
        user_data = self.get_user(ctx.author.id)
        wallet = user_data[1]
        
        if bet > wallet:
            embed = discord.Embed(
                title="❌ Insufficient Funds",
                description=f"You only have **${wallet:,}** in your wallet!",
                color=self.purple
            )
            await ctx.send(embed=embed)
            return
        
        first_num = random.randint(1, 100)
        
        embed = discord.Embed(
            title="📊 High or Low",
            description=f"Your number is: **{first_num}**\n\nWill the next number be **higher** or **lower**?\n\nReact with ⬆️ for higher or ⬇️ for lower!",
            color=self.purple
        )
        message = await ctx.send(embed=embed)
        
        await message.add_reaction("⬆️")
        await message.add_reaction("⬇️")
        
        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in ["⬆️", "⬇️"] and reaction.message.id == message.id
        
        try:
            reaction, user = await self.bot.wait_for("reaction_add", timeout=15.0, check=check)
            
            second_num = random.randint(1, 100)
            user_guess = "higher" if str(reaction.emoji) == "⬆️" else "lower"
            
            correct = (user_guess == "higher" and second_num > first_num) or (user_guess == "lower" and second_num < first_num)
            
            if second_num == first_num:
                result_text = f"It's a tie! The number was **{second_num}**\nYou keep your **${bet:,}**"
            elif correct:
                self.update_balance(ctx.author.id, bet)
                result_text = f"✅ Correct! The number was **{second_num}**\nYou won **${bet:,}**!"
            else:
                self.update_balance(ctx.author.id, -bet)
                result_text = f"❌ Wrong! The number was **{second_num}**\nYou lost **${bet:,}**"
            
            embed = discord.Embed(
                title="📊 High or Low - Result",
                description=f"First number: **{first_num}**\nSecond number: **{second_num}**\n\n{result_text}",
                color=self.purple
            )
            await message.edit(embed=embed)
            
        except asyncio.TimeoutError:
            embed = discord.Embed(
                title="⏰ Timeout",
                description="You took too long to respond!",
                color=self.purple
            )
            await message.edit(embed=embed)

    @commands.command(name="add", aliases=["addmoney"])
    @commands.is_owner()
    async def add_money(self, ctx, member: discord.Member, amount: int):
        """Add money to a user's wallet"""
        if amount <= 0:
            embed = discord.Embed(
                title="❌ Invalid Amount",
                description="Amount must be positive!",
                color=self.purple
            )
            await ctx.send(embed=embed)
            return
        
        self.update_balance(member.id, amount)
        
        embed = discord.Embed(
            title="💰 Money Added",
            description=f"Successfully added **${amount:,}** to {member.mention}'s wallet!",
            color=self.purple
        )
        
        await ctx.send(embed=embed)
    
    @add_money.error
    async def add_money_error(self, ctx, error):
        if isinstance(error, commands.NotOwner):
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="Only the bot owner can use this command!",
                color=self.purple
            )
            await ctx.send(embed=embed)
            
    @commands.command(name="reset", aliases=["resetbalance"])
    @commands.is_owner()
    async def reset_balance(self, ctx, member: discord.Member):
        """Reset a user's wallet and bank to 0"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("UPDATE users SET balance = 0, bank = 0 WHERE user_id = ?", (member.id,))
        conn.commit()
        conn.close()
        
        embed = discord.Embed(
            title="🔄 Balance Reset",
            description=f"Successfully reset {member.mention}'s wallet and bank to **$0**!",
            color=self.purple
        )
        
        await ctx.send(embed=embed)
    
    @reset_balance.error
    async def reset_balance_error(self, ctx, error):
        if isinstance(error, commands.NotOwner):
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="Only the bot owner can use this command!",
                color=self.purple
            )
            await ctx.send(embed=embed)
            
async def setup(bot):
    await bot.add_cog(Economy(bot))