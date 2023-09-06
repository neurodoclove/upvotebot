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
    with open('channel_ids.json', 'r') as f:
        forum_channel_ids = json.load(f)
except FileNotFoundError:
    forum_channel_ids = {}

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
    with open('channel_ids.json', 'w') as f:
        json.dump(forum_channel_ids, f)

    await ctx.send(f"Channel has been set to {channel.name} for this server.")

async def fetch_leaderboard(channel):
    leaderboard = {}
    twitch_clip_regex = re.compile(r'(https://clips\.twitch\.tv/[A-Za-z0-9_-]+)')
    
    messages = []
    
    if isinstance(channel, discord.TextChannel):
        async for message in channel.history(limit=200):  # You can set any limit you prefer
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
            for reaction in message.reactions:
                if reaction.emoji == '⭐':
                    stars_count = reaction.count
                    break
            headline = message.channel.name if isinstance(channel, discord.TextChannel) else message.channel.parent.name
            if twitch_clip_url in leaderboard:
                existing_headline, existing_stars = leaderboard[twitch_clip_url]
                stars_count += existing_stars
            leaderboard[twitch_clip_url] = (headline, stars_count)
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
    sorted_leaderboard = sorted(leaderboard.items(), key=lambda x: x[1][1], reverse=True)[:10]

    output = "Top 10 Clips:\n"
    for i, (clip, (headline, stars)) in enumerate(sorted_leaderboard, start=1):
        star_word = "stars" if stars != 1 else "star"
        output += f"{i}. {stars} {star_word} - <{clip}>\n"

    await ctx.send(output)  # This sends the top 10 clips to wherever the command was run


@tasks.loop(minutes=1)
async def update_every_x_minutes():
    for guild_id, channel_id in forum_channel_ids.items():
        forum_channel = client.get_channel(channel_id)
        if forum_channel:
            leaderboard = await fetch_leaderboard(forum_channel)

@update_every_x_minutes.before_loop
async def before():
    await client.wait_until_ready()

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')
    update_every_x_minutes.start()


client.run(os.getenv('BOT_TOKEN'))  # Read bot token from environment variables