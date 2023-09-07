from dotenv import load_dotenv
import os


from discord.ext import commands, tasks
import discord
import re
import json

load_dotenv()  # Load environment variables from .env file

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.reactions = True

client = commands.Bot(command_prefix="!", intents=intents)

# Load saved channel IDs from a JSON file
try:
    with open('channel_settings.json', 'r') as f:
        forum_channel_ids = json.load(f)
except FileNotFoundError:
    forum_channel_ids = {}

# Load saved emojis from JSON file
try:
    with open('emoji_settings.json', 'r') as f:
        emoji_settings = json.load(f)
except FileNotFoundError:
    emoji_settings = {}


@client.command()
async def setchannel(ctx, channel_id_str: str):
    guild_id = str(ctx.guild.id)

    match = re.match(r"<#(\d+)>", channel_id_str)
    if match:
        channel_id_str = match.group(1)

    try:
        channel_id = int(channel_id_str)
    except ValueError:
        await ctx.send("Invalid channel ID.")
        return

    channel = client.get_channel(channel_id)
    if channel is None:
        await ctx.send(f"No channel found with ID {channel_id}")
        return

    if not isinstance(channel, (discord.TextChannel, discord.Thread, discord.ForumChannel)):
        await ctx.send(f"The ID does not belong to a valid channel type")
        return

    # Save the channel ID for this guild
    forum_channel_ids[guild_id] = channel.id
    with open('channel_settings.json', 'w') as f:
        json.dump(forum_channel_ids, f)

    await ctx.send(f"Channel has been set to {channel.name} for this server.")

@client.command()
async def setupvote(ctx, emoji: str):
    guild_id = str(ctx.guild.id)
    
    # Only allow Unicode emojis
    if re.match(r"<a?:[a-zA-Z0-9\_]+:(\d+)>", emoji):
        await ctx.send("Only Unicode emojis are allowed.")
        return

    # Save the emoji for this guild
    emoji_settings[guild_id] = emoji
    with open('emoji_settings.json', 'w') as f:
        json.dump(emoji_settings, f)
    await ctx.send(f"Reaction emoji has been set to {emoji} for this server.")



async def fetch_leaderboard(channel):
    leaderboard = {}
    twitch_clip_regex = re.compile(r'(https://clips\.twitch\.tv/[A-Za-z0-9_-]+)')
    
    messages = []
    
    if isinstance(channel, discord.TextChannel):
        async for message in channel.history(limit=200):
            messages.append(message)
    elif isinstance(channel, discord.ForumChannel):
        for thread in channel.threads:
            async for message in thread.history(limit=40):
                messages.append(message)
    else:
        return None
    
    for message in messages:
        twitch_clip_match = twitch_clip_regex.search(message.content)
        if twitch_clip_match:
            twitch_clip_url = twitch_clip_match.group(1)
            stars_count = 0  
            guild_id = str(channel.guild.id)
            reaction_emoji = emoji_settings.get(guild_id, '⭐')
            
            for reaction in message.reactions:
                # Only consider Unicode emoji
                if isinstance(reaction.emoji, str):
                    if reaction.emoji == reaction_emoji:
                        stars_count = reaction.count
                        break
            
            if twitch_clip_url in leaderboard:
                existing_stars = leaderboard[twitch_clip_url]
                stars_count += existing_stars
            leaderboard[twitch_clip_url] = stars_count
    
    return leaderboard



@client.command()
async def top10(ctx):
    guild_id = str(ctx.guild.id)  # Get the guild ID where the command was run
    channel_id = forum_channel_ids.get(guild_id)  # Retrieve the channel ID set for this server

    if not channel_id:
        await ctx.send("No channel set for this server. Use `!setchannel` to set one.")
        return

    forum_channel = client.get_channel(channel_id)
    if not forum_channel:
        await ctx.send(f"No channel found with ID {channel_id}")
        return

    leaderboard = await fetch_leaderboard(forum_channel)
    sorted_leaderboard = sorted(leaderboard.items(), key=lambda x: x[1], reverse=True)[:10]

    output = "Top 10 Clips:\n"
    count = 0
    for clip, stars in sorted_leaderboard:
        if stars >= 1:  # Only include clips with at least 1 star
            count += 1
            star_word = "upvotes" if stars != 1 else "upvote"
            output += f"{count}. {stars} {star_word} - <{clip}>\n"
            if count >= 10:  # Stop once 10 clips have been added
                break

    if count == 0:  # If there are no clips with at least 1 star
        await ctx.send("No clips have at least 1 upvote.")
    else:
        await ctx.send(output)  # This sends the top 10 clips to wherever the command was run

@client.command()
async def whatchannel(ctx):
    guild_id = str(ctx.guild.id)
    channel_id = forum_channel_ids.get(guild_id, None)
    if channel_id:
        channel = client.get_channel(channel_id)
        if channel:
            await ctx.send(f"The current channel is set to {channel.name}.")
        else:
            await ctx.send(f"Channel ID exists but no such channel was found.")
    else:
        await ctx.send("No channel is set for this server.")

@client.command()
async def whatupvote(ctx):
    guild_id = str(ctx.guild.id)
    emoji = emoji_settings.get(guild_id, None)
    if emoji:
        await ctx.send(f"The current upvote emoji is set to {emoji}.")
    else:
        await ctx.send("No upvote emoji is set for this server.")

async def set_defaults(guild):
    general_channel = discord.utils.get(guild.text_channels, name='general')
    if general_channel:
        forum_channel_ids[str(guild.id)] = general_channel.id
    emoji_settings[str(guild.id)] = "⭐"

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')
    for guild in client.guilds:
        guild_id_str = str(guild.id)
        if guild_id_str not in forum_channel_ids:
            general_channel = discord.utils.get(guild.text_channels, name='general')
            if general_channel:
                forum_channel_ids[guild_id_str] = general_channel.id
                with open('channel_ids.json', 'w') as f:
                    json.dump(forum_channel_ids, f)
        if guild_id_str not in emoji_settings:
            emoji_settings[guild_id_str] = "⭐"
            with open('emoji_settings.json', 'w') as f:
                    json.dump(emoji_settings, f)


client.run(os.getenv('BOT_TOKEN'))  # Read bot token from environment variables