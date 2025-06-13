import discord
from discord.ext import commands
from youtube_search import YoutubeSearch #type: ignore
import spotipy #type: ignore
from spotipy.oauth2 import SpotifyClientCredentials #type: ignore
import pandas as pd #type: ignore
import requests
import os
import uuid
import datetime as dt
from pydub import AudioSegment #type: ignore
import yt_dlp
from collections import deque

queue = deque()
voice = None

playQueue = []

def after_song(error=None):
    if queue:
        next_song = queue.popleft()
        voice.play(discord.FFmpegPCMAudio(next_song[1]), after=after_song)

def after_song_playlist(error=None):
    global playQueue
    if playQueue:
        voice.stop()
        next_song = playQueue.pop(0)
        playQueue.append(next_song)
        print(playQueue)
        voice.play(discord.FFmpegPCMAudio(next_song), after=after_song_playlist)


def search(keyword, num=1, tosave="lazy_static"):
    try:
        cid, secret = '<spotify client id here>', '<spotify client secret here>'
        search = keyword
        client_credentials_manager = SpotifyClientCredentials(client_id=cid, client_secret=secret)
        sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)
        artist_name = []
        track_name = []
        popularity = []
        track_id = []
        url = []
        title = []
        for i in range(0, 1, 50):
            track_results = sp.search(q=search, type='track', limit=50, offset=i)
            for _, t in enumerate(track_results['tracks']['items']):
                artist_name.append(t['artists'][0]['name'])
                track_name.append(t['name'])
                track_id.append(t['id'])
                popularity.append(t['popularity'])

        track_dataframe = pd.DataFrame(
            {'artist_name': artist_name, 'track_name': track_name, 'track_id': track_id, 'popularity': popularity})
        track_dataframe = track_dataframe.drop([i for i in range(10, track_dataframe.shape[0])])
        artist = list(track_dataframe["artist_name"])
        track = list(track_dataframe["track_name"])

        if track_dataframe.shape[0] == 0:
            return ["0x11", None, None, None]

        results = YoutubeSearch(track[num-1] + " by " + artist[num-1], max_results=1).to_dict()
        for _, j in enumerate(results):
            url.append(j['url_suffix'])
            title.append(j['title'])
        abc = "https://www.youtube.com" + url[0]
        name = str(uuid.uuid4())
        filename = f"{name}"

        options = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
                'preferredquality': '192',
            }],
            'outtmpl': filename,
            'noplaylist': True,
        }

        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.download([abc])
        wav_audio = AudioSegment.from_file(f"{name}.m4a")
        wav_audio.export(f"{name}.wav", format="wav")
        os.remove(f"{name}.m4a")
        os.rename(f"{name}.wav", f"{tosave}/{name}.wav")
        return ["0x10", f"{tosave}/{name}.wav", title[0], artist[0]]

    except Exception as e:
        return [str(e), None]

intents = discord.Intents.default()
intents.voice_states = True
intents.message_content = True

client = commands.Bot(command_prefix="$", intents=intents)

@client.command()
async def add(ctx, *args):
    song_name = " ".join(args)
    result = search(song_name)
    if result[0] == "0x10":
        queue.append(result)
        await ctx.send(f"Added **{result[2]}** by {result[3]} to the queue.")
        if len(queue) == 1:
            try:
                if not voice.is_playing():
                    await play_next(ctx)
            except Exception as e:
                print(e)
                if str(e) == "'NoneType' object has no attribute 'is_playing'":
                    print(e)
                    await play_next(ctx)
    else:
        await ctx.send("Failed to find the song.")

@client.command()
async def show_queue(ctx):
    if queue:
        queue_list = "\n".join([f"{i+1}. {song[2]} by {song[3]}" for i, song in enumerate(queue)])
        await ctx.send(f"**Song Queue:**\n{queue_list}")
    else:
        await ctx.send("The queue is empty.")

@client.command()
async def play(ctx):
    await play_next(ctx)

@client.command()
async def play_next(ctx):
    global voice
    if queue:
        song = queue.popleft()
        if voice and voice.is_playing():
            voice.stop()
        if ctx.message.author.voice:
            channel = ctx.message.author.voice.channel
            try:
                await channel.connect()
                await ctx.guild.change_voice_state(channel=channel, self_mute=False, self_deaf=True)
            except Exception:
                pass
            voice = discord.utils.get(client.voice_clients, guild=ctx.guild)
        embed = discord.Embed(title="Now Playing", description=f"**{song[2]}** by {song[3]}", colour=ctx.author.colour)
        await ctx.send(embed=embed)
        voice.play(discord.FFmpegPCMAudio(song[1]), after=after_song)
    else:
        await ctx.send("The queue is empty!")

@client.command()
async def skip(ctx):
    if voice and voice.is_playing():
        voice.stop()
        await play_next(ctx)
    else:
        await ctx.send("No song is currently playing.")

@client.command()
async def skip_in_playlist(ctx):
    after_song_playlist()

@client.command()
async def leave(ctx):
    voice = discord.utils.get(client.voice_clients, guild=ctx.guild)
    if voice is not None and voice.is_connected():
        await voice.disconnect()
    else:
        await ctx.send("Lazy_Static! is not connected to a voice channel")


@client.command()
async def pause(ctx):
    voice = discord.utils.get(client.voice_clients, guild=ctx.guild)
    if voice is not None and voice.is_playing():
        voice.pause()
    else:
        await ctx.send("Lazy_Static! is not playing any audio")


@client.command()
async def resume(ctx):
    voice = discord.utils.get(client.voice_clients, guild=ctx.guild)
    if voice is not None and voice.is_paused():
        voice.resume()
    else:
        await ctx.send("Lazy_Static! is not currently paused, no need for that")

@client.command()
async def stop(ctx):
    voice = discord.utils.get(client.voice_clients, guild=ctx.guild)
    if voice is not None:
        voice.stop()
    else:
        await ctx.send("Lazy_Static! is already stopped")

@client.command()
async def new_playlist(ctx, name):
    names = str(name) + str(ctx.author.id)
    try:
        os.system(f"cd lazy_static && mkdir {names}")
        await ctx.send(f"Created a new playlist for user {ctx.author.display_name} with the name {name}")
    except Exception:
        await ctx.send("Already exists")

@client.command()
async def add_to_playlist(ctx, name, *args):
    song_name = " ".join(args)
    result = search(song_name, tosave=f"lazy_static/{str(name) + str(ctx.author.id)}")
    await ctx.send(f"Added **{result[2]}** by {result[3]} to the playlist.")
    if playQueue != []:
        playQueue.append(result[1])

@client.command()
async def play_playlist(ctx, name):
    global playQueue
    global voice
    directory = "lazy_static/" + str(name) + str(ctx.author.id) + "/"
    files = [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
    for f in files:
        playQueue.append(directory+str(f))
    print(playQueue)
    try:
        if voice and voice.is_playing():
                voice.stop()
    except Exception as e:
        pass
    if ctx.message.author.voice:
        channel = ctx.message.author.voice.channel
        try:
            await channel.connect()
            await ctx.guild.change_voice_state(channel=channel, self_mute=False, self_deaf=True)
        except Exception:
            pass
        song = playQueue.pop(0)
        playQueue.append(song)
        voice = discord.utils.get(client.voice_clients, guild=ctx.guild)
        voice.play(discord.FFmpegPCMAudio(song), after=after_song_playlist)



print("[Debug] Application Started")
client.run("<Discord client key>")
