import os
import argparse
import spotipy
import numpy as np
import spotipy.util as util
import spotify_tokens
import re
from datetime import datetime
import warnings

# suppressing warning from pandas import
warnings.filterwarnings("ignore", message="numpy.dtype size changed")
warnings.filterwarnings("ignore", message="numpy.ufunc size changed")

import pandas as pd

def get_songs_list(database, **kwargs):
    print(kwargs)
    genres = kwargs["genre(s)"]
    tags = kwargs["tag(s)"]
    rating = kwargs["rating"]
    bpm = kwargs["bpm"]
    artists = kwargs["artist(s)"]
    
    filtered = database

    if artists:
        filtered = filtered[filtered.artists.isin(artists)]
    if genres:
        filtered = filtered[(filtered.genre.isin(genres)) | (filtered.genre.isnull())]
    if rating:
        filtered = filtered[(filtered.rating >= rating) | (filtered.rating.isnull())]
    if bpm:
        beats = float(bpm.strip().split()[1])
        print(beats)
        if ">" in bpm:
            filtered = filtered[(filtered.bpm > beats) | (filtered.bpm.isnull())]
        else:
            filtered = filtered[(filtered.bpm < beats) | (filtered.bpm.isnull())]
    if tags:
        # splitting the tags on separate rows then joining with the original table
        # https://stackoverflow.com/questions/17116814/pandas-how-do-i-split-text-in-a-column-into-multiple-rows
        t = filtered.tags.str.split(expand=True).stack()
        t.index = t.index.droplevel(-1)
        t.name = "tags"
        del filtered["tags"]
        filtered = filtered.join(t)
        filtered = filtered[(filtered.tags.isin(tags)) | (filtered.tags.isnull())] # need to handle tags separately
    
    print(filtered)
    return filtered


def create_spotify_playlist(spotify, user, title, public=True, description="Auto-generated playlist"):
    res = spotify.user_playlist_create(user, title, public, description)
    return res['id']


def bpm_type(bpm, pattern=re.compile("[<>] ?\d+$")):
    if not pattern.match(bpm):
        print("not match")
        raise argparse.ArgumentTypeError
    return bpm


def main():
    timestamp = datetime.today().strftime('%d/%m/%Y %H:%M')
    parser = argparse.ArgumentParser(description='''Python script to create playlists on Spotify and 
                                    Youtube starting from a csv file containing the songs list properly
                                    labeled''')
    parser.add_argument("-u", "--user", required=True, help="Spotify username")
    parser.add_argument("-f", "--file", required=True, help="csv file to use as input")
    parser.add_argument("-d", "--duration", type=int, default=60, help="duration in minutes of the playlist")
    parser.add_argument("-t", "--title", default="A wonderful playlist - %s" % timestamp, help="playlist title")
    parser.add_argument("-T", "--tag(s)", nargs='+', help="songs tag(s) to include in the playlist")
    parser.add_argument("-g", "--genre(s)", nargs='+', help="expected genre for the songs in the playlist")
    parser.add_argument("-a", "--artist(s)", nargs='+', help="artist(s) to include in the playlist <name_surname>")
    parser.add_argument("-b", "--bpm", type=bpm_type, help="expected genre for the songs in the playlist")
    parser.add_argument("-r", "--rating", type=float, default=1.0, help="minimum rating for the songs in the playlist")

    args = parser.parse_args()
    print(args)
    token = util.prompt_for_user_token(args.user, "playlist-modify-public", 
                                client_id=spotify_tokens.SPOTIPY_CLIENT_ID,
                                client_secret=spotify_tokens.SPOTIPY_CLIENT_SECRET, 
                                redirect_uri=spotify_tokens.SPOTIPY_REDIRECT_URI)

    print(token)
    sp = spotipy.Spotify(auth=token)

    database = pd.read_csv(args.file, sep=' *, *', engine="python")
    songs = get_songs_list(database, **vars(args))
    
    
    tracks = []
    playlist_duration = 0
    # converting the playlist required duration in ms
    requested_playlist_duration = args.duration * 60 * 1000
    for row in songs.itertuples():
        print(row.artists, row.title)
        res = sp.search(q="track:%s artist:%s" % (row.title, row.artists.replace("_", " ")), limit=1, type="track") 
        
        try:
            track_id = res["tracks"]["items"][0]["id"]
            duration_ms = res["tracks"]["items"][0]["duration_ms"]
            tracks.append(track_id)
            playlist_duration += duration_ms
            if playlist_duration >= requested_playlist_duration:
                print("Creating playlist...")
                playlist_id = create_spotify_playlist(sp, args.user, args.title)
                print("Created playlist: %s" % playlist_id)
                print "Adding tracklist: ", tracks
                sp.user_playlist_add_tracks(args.user, playlist_id, tracks)
                print("DONE")
                break
        
        except IndexError:
            print(res)


if __name__ == "__main__":
    main()

