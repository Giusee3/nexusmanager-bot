import discord
from discord.ext import commands
import os
import time
import asyncio
import logging
from collections import defaultdict
from keep_alive import keep_alive

# --- CONFIGURAZIONE BOT---
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix='$', intents=intents, help_command=None)

# --- DATI IN MEMORIA ---
user_spam_tracker = {}
user_warnings = defaultdict(list)

# --- FUNZIONE AUSILIARIA PER IL TEMPO ---
def parse_time(time_str: str):
    unit = time_str[-1].lower()
    value_str = time_str[:-1]

    if not value_str.isdigit():
        return None

    value = int(value_str)

    if unit == 's':
        return value
    elif unit == 'm':
        return value * 60
    elif unit == 'h':
        return value * 3600
    elif unit == 'd':
        return value * 86400
    else:
        return None

# --- EVENTI DEL BOT ---
@bot.event
async def on_ready():
    if bot.user:
        print(f'Bot connesso come {bot.user.name}')
        print('Il bot è online e operativo!')
    else:
        print("Errore: Impossibile ottenere le info del bot.")
    await bot.change_presence(activity=discord.Game(name="$help per i comandi"))

@bot.event
async def on_message(message):
    if message.author.bot:
        await bot.process_commands(message)
        return

    user_id = message.author.id
    current_time = int(time.time())

    if user_id not in user_spam_tracker:
        user_spam_tracker[user_id] = {'content': message.content, 'timestamp': current_time, 'count': 1}
    else:
        tracker = user_spam_tracker[user_id]
        if message.content and message.content == tracker['content']:
            if current_time - tracker['timestamp'] > 15:
                tracker.update({'timestamp': current_time, 'count': 1})
            else:
                tracker['count'] += 1
        else:
            tracker.update({'content': message.content, 'timestamp': current_time, 'count': 1})

    if user_spam_tracker[user_id].get('count', 0) >= 3:
        try:
            await message.delete()
            reason = "Spam di messaggi identici."
            user_warnings[user_id].append(("Sistema Anti-Spam", reason))
            embed = discord.Embed(
                title="⚠️ Avvertimento Automatico per Spam",
                description=f"L'utente {message.author.mention} ha ricevuto un avvertimento.",
                color=0xf1c40f
            )
            await message.channel.send(embed=embed, delete_after=15)
            user_spam_tracker[user_id]['count'] = 0
        except discord.errors.NotFound:
            pass

    await bot.process_commands(message)

# --- COMANDI ---
@bot.command(name='help')
async def help(ctx):
    embed = discord.Embed(title="🤖 Lista Comandi del Bot", description="Il prefisso è `$`.", color=0x2f3136)
    if bot.user and bot.user.display_avatar:
        embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.add_field(name="Moderazione", value="`warn`, `warns`, `kick`, `ban`, `unban`", inline=False)
    embed.add_field(name="Moderazione a Tempo", value="`mutetime`, `bantime`", inline=False)
    embed.add_field(name="Formato del tempo", value="Usa `d` (giorni), `h` (ore), `m` (minuti), `s` (secondi).", inline=False)
    await ctx.send(embed=embed)

@bot.command(name='warn')
@commands.has_permissions(manage_messages=True)
async def warn(ctx, member: discord.Member, *, reason="Nessun motivo specificato"):
    user_warnings[member.id].append((ctx.author.name, reason))
    embed = discord.Embed(title="⚠️ Avvertimento", description=f"**{member.display_name}** ha ricevuto un avvertimento.", color=0xf1c40f)
    embed.add_field(name="Da", value=ctx.author.name, inline=False)
    embed.add_field(name="Motivo", value=reason, inline=False)
    embed.set_footer(text=f"Warn totali: {len(user_warnings[member.id])}")
    await ctx.send(embed=embed)

@bot.command(name='warns')
@commands.has_permissions(manage_messages=True)
async def warns(ctx, member: discord.Member):
    warnings_list = user_warnings.get(member.id, [])
    if not warnings_list:
        await ctx.send(f"L'utente **{member.display_name}** non ha avvertimenti.")
        return
    embed = discord.Embed(title=f"Avvertimenti di {member.display_name}", color=0x2f3136)
    for i, (moderator, reason) in enumerate(warnings_list, 1):
        embed.add_field(name=f"Warn #{i} (da {moderator})", value=reason, inline=False)
    await ctx.send(embed=embed)

@bot.command(name='mutetime')
@commands.has_permissions(manage_roles=True)
async def mutetime(ctx, member: discord.Member, time_str: str, *, reason="Nessun motivo specificato"):
    seconds = parse_time(time_str)
    if seconds is None:
        await ctx.send("Formato tempo non valido. Usa es. `10m`, `2h`, `1d`.")
        return
    muted_role = discord.utils.get(ctx.guild.roles, name="Muted")
    if not muted_role:
        muted_role = await ctx.guild.create_role(name="Muted")
        for channel in ctx.guild.channels:
            await channel.set_permissions(muted_role, speak=False, send_messages=False)
    await member.add_roles(muted_role, reason=reason)
    await ctx.send(embed=discord.Embed(title="🔇 Utente Silenziato a Tempo", description=f"**{member.display_name}** silenziato per **{time_str}**.", color=0x778899))
    await asyncio.sleep(seconds)
    if muted_role in member.roles:
        await member.remove_roles(muted_role)

@bot.command(name='bantime')
@commands.has_permissions(ban_members=True)
async def bantime(ctx, member: discord.Member, time_str: str, *, reason="Nessun motivo specificato"):
    seconds = parse_time(time_str)
    if seconds is None:
        await ctx.send("Formato tempo non valido. Usa es. `10m`, `2h`, `1d`.")
        return
    await member.ban(reason=reason)
    await ctx.send(embed=discord.Embed(title="🔨 Utente Bannato a Tempo", description=f"**{member.display_name}** bannato per **{time_str}**.", color=0xff0000))
    await asyncio.sleep(seconds)
    try:
        await ctx.guild.unban(member)
    except discord.NotFound:
        pass

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("🚫 Non hai i permessi.", delete_after=10)
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("🤔 Manca un pezzo al comando. Controlla `$help`.", delete_after=10)
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("🤷 Non trovo questo utente.", delete_after=10)
    else:
        logging.error(f"Errore non gestito nel server {ctx.guild.id if ctx.guild else 'DM'}", exc_info=error)

# --- BLOCCO DI AVVIO E RIAVVIO ---
async def main():
    keep_alive()
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        print("ERRORE: Token non trovato!")
        return

    handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')

    async with bot:
        discord.utils.setup_logging(handler=handler, level=logging.INFO)
        await bot.start(token)

if __name__ == "__main__":
    while True:
        try:
            asyncio.run(main())
        except Exception as e:
            print(f"Bot crashato: {e}. Riavvio tra 5 secondi...")
            time.sleep(5)
