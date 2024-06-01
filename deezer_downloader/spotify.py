import re
from time import sleep
from urllib.parse import urlparse, parse_qs

import requests

import inspect
import json
import logging
from enum import Enum
from pathlib import Path

#import spotify_web_downloader
#from . import __version__
from spotify_web_downloader.constants import *
from spotify_web_downloader.downloader import Downloader
from spotify_web_downloader.downloader_music_video import DownloaderMusicVideo
from spotify_web_downloader.downloader_song import DownloaderSong
from spotify_web_downloader.enums import DownloadModeSong, DownloadModeVideo, RemuxMode
from spotify_web_downloader.models import Lyrics
from spotify_web_downloader.spotify_api import SpotifyApi
from spotify_web_downloader.enums import DownloadModeSong

from deezer_downloader.threadpool_queue import ThreadpoolScheduler, report_progress


token_url = 'https://open.spotify.com/get_access_token?reason=transport&productType=web_player'
playlist_base_url = 'https://api.spotify.com/v1/playlists/{}/tracks?limit=100&additional_types=track&market=GB'  # todo figure out market
track_base_url = 'https://api.spotify.com/v1/tracks/{}'
album_base_url = 'https://api.spotify.com/v1/albums/{}/tracks'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.115 Safari/537.36'}


class SpotifyInvalidUrlException(Exception):
    pass


class SpotifyWebsiteParserException(Exception):
    pass


def parse_uri(uri):
    u = urlparse(uri)
    if u.netloc == "embed.spotify.com":
        if not u.query:
            raise SpotifyInvalidUrlException("ERROR: url {} is not supported".format(uri))

        qs = parse_qs(u.query)
        return parse_uri(qs['uri'][0])

    # backwards compatibility
    if not u.scheme and not u.netloc:
        return {"type": "playlist", "id": u.path}

    if u.scheme == "spotify":
        parts = uri.split(":")
    else:
        if u.netloc != "open.spotify.com" and u.netloc != "play.spotify.com":
            raise SpotifyInvalidUrlException("ERROR: url {} is not supported".format(uri))

        parts = u.path.split("/")

    if parts[1] == "embed":
        parts = parts[1:]

    l = len(parts)
    if l == 3 and parts[1] in ["album", "track", "playlist"]:
        return {"type": parts[1], "id": parts[2]}
    if l == 5 and parts[3] == "playlist":
        return {"type": parts[3], "id": parts[4]}

    # todo add support for other types; artists, searches, users

    raise SpotifyInvalidUrlException("ERROR: unable to determine Spotify URL type or type is unsupported.")


def get_songs_from_spotify_website(playlist, proxy):
    # parses Spotify Playlist from Spotify website
    # playlist: playlist url or playlist id as string
    # proxy: https/socks5 proxy (e. g. socks5://user:pass@127.0.0.1:1080/)
    # e.g. https://open.spotify.com/playlist/0wl9Q3oedquNlBAJ4MGZtS
    # e.g. https://open.spotify.com/embed/0wl9Q3oedquNlBAJ4MGZtS
    # e.g. 0wl9Q3oedquNlBAJ4MGZtS
    # return: list of songs (song: artist - title)
    # raises SpotifyWebsiteParserException if parsing the website goes wrong

    return_data = []
    url_info = parse_uri(playlist)

    req = requests.get(token_url, headers=headers, proxies={"https": proxy})
    if req.status_code != 200:
        raise SpotifyWebsiteParserException(
            "ERROR: {} gave us not a 200. Instead: {}".format(token_url, req.status_code))
    token = req.json()

    if url_info['type'] == "playlist":
        url = playlist_base_url.format(url_info["id"])
        while True:
            resp = get_json_from_api(url, token["accessToken"], proxy)
            for track in resp['items']:
                return_data.append(parse_track(track["track"]))

            if resp['next'] is None:
                break
            url = resp['next']
    elif url_info["type"] == "track":
        resp = get_json_from_api(track_base_url.format(url_info["id"]), token["accessToken"], proxy)
        if resp is None:  # try again in case of rate limit
            resp = get_json_from_api(track_base_url.format(url_info["id"]), token["accessToken"], proxy)

        return_data.append(parse_track(resp))
    elif url_info["type"] == "album":
        resp = get_json_from_api(album_base_url.format(url_info["id"]), token["accessToken"], proxy)
        if resp is None:  # try again in case of rate limit
            resp = get_json_from_api(album_base_url.format(url_info["id"]), token["accessToken"], proxy)

        for track in resp['items']:
            return_data.append(parse_track(track))

    return [track for track in return_data if track]


def parse_track(track):
    artist = track['artists'][0]['name']
    song = track['name']
    full = "{} {}".format(artist, song)
    # remove everything in brackets to get better search results later on Deezer
    # e.g. (Radio  Version) or (Remastered)
    return re.sub(r'\([^)]*\)', '', full)


def get_json_from_api(api_url, access_token, proxy):
    headers.update({'Authorization': 'Bearer {}'.format(access_token)})
    req = requests.get(api_url, headers=headers, proxies={"https": proxy})

    if req.status_code == 429:
        seconds = int(req.headers.get("Retry-After")) + 1
        print("INFO: rate limited! Sleeping for {} seconds".format(seconds))
        sleep(seconds)
        return None

    if req.status_code != 200:
        raise SpotifyWebsiteParserException("ERROR: {} gave us not a 200. Instead: {}".format(api_url, req.status_code))
    return req.json()


def do_download_by_playlist_url(url, path):

    cookies_path = Path("/app/cookies.txt")
    output_path = Path(path)
    save_cover = True
    lrc_only = False
    overwrite = False
    no_lrc = True

    template_folder_album = "/",
    template_folder_compilation = "/",
    template_file_single_disc = "{album} - {track:02d} {title}",
    template_file_multi_disc = "{album} - {track:02d} {title}",

    spotify_api = SpotifyApi(cookies_path)
    downloader = Downloader(
        spotify_api=spotify_api,
        output_path=output_path,
    )
    downloader_song = DownloaderSong(
        downloader=downloader,
        download_mode=DownloadModeSong.ARIA2C
    )

    list_of_files = []
    try:
        url_info = downloader.get_url_info(url)
        download_queue = downloader.get_download_queue(url_info)
    except Exception as e:
        print("Error parsing url")
    for queue_index, queue_item in enumerate(download_queue, start=1):
        #queue_progress = f"Track {queue_index}/{len(download_queue)} from URL {url_index}/{len(urls)}"
        report_progress(queue_index, len(download_queue))
        track = queue_item.metadata
        try:

            #logger.info(f'({queue_progress}) Downloading "{track["name"]}"') rewrite async logging
            track_id = track["id"]
            gid = spotify_api.track_id_to_gid(track_id)
            metadata_gid = spotify_api.get_gid_metadata(gid)
            if not lrc_only:
                downloader.set_cdm()
              
            if not metadata_gid.get("original_video"):
                if metadata_gid.get("has_lyrics") and spotify_api.is_premium:
                    lyrics = downloader_song.get_lyrics(track_id)
                else:
                    lyrics = Lyrics()
                album_metadata = spotify_api.get_album(
                    spotify_api.gid_to_track_id(metadata_gid["album"]["gid"])
                )
                track_credits = spotify_api.get_track_credits(track_id)
                tags = downloader_song.get_tags(
                    metadata_gid,
                    album_metadata,
                    track_credits,
                    lyrics.unsynced,
                )
                #final_path = downloader_song.get_final_path(tags)
                c_path = path + "/" + tags["artist"] + " " + tags["album"] + " " + tags["title"] + ".m4a".replace("/","")
                final_path = Path(c_path)
                lrc_path = downloader_song.get_lrc_path(final_path)
                cover_path = downloader_song.get_cover_path(final_path)
                cover_url = downloader.get_cover_url(metadata_gid, "LARGE")
                list_of_files.append(str(final_path))
                print(final_path)

                if lrc_only:
                    pass
                elif final_path.exists() and not overwrite:
                    print ("Track already exists")
                else:
                    file_id = downloader_song.get_file_id(metadata_gid)
                    if not file_id:
                        print("File not found on spotify's Servers")
                        continue
                    pssh = spotify_api.get_pssh(file_id)
                    decryption_key = downloader_song.get_decryption_key(pssh)
                    stream_url = spotify_api.get_stream_url(file_id)
                    encrypted_path = downloader.get_encrypted_path(track_id, ".m4a")
                    decrypted_path = downloader.get_decrypted_path(track_id, ".m4a")
                    downloader_song.download(encrypted_path, stream_url)
                    remuxed_path = downloader.get_remuxed_path(track_id, ".m4a")
                    downloader_song.remux(
                        encrypted_path,
                        decrypted_path,
                        remuxed_path,
                        decryption_key,
                    )
                    downloader.apply_tags(remuxed_path, tags, cover_url)
                    downloader.move_to_final_path(remuxed_path, final_path)
                if no_lrc or not lyrics.synced:
                    pass
                else:
                    downloader_song.save_lrc(lrc_path, lyrics.synced)
                if lrc_only or not save_cover:
                    pass
                elif cover_path.exists() and not overwrite:
                    print ("Cover already exists")
                else:
                    print("Saving Cover")
                    downloader.save_cover(cover_path, cover_url)

        except Exception as e:
            print ("Error Occured" + str(e))

    return list_of_files


if __name__ == '__main__':
    # playlist = "21wZXvtrERELL0bVtKtuUh"
    playlist = "0wl9Q3oedquNlBAJ4MGZtS"
    album = "spotify:album:7zCODUHkfuRxsUjtuzNqbd"
    song = "https://open.spotify.com/track/6piFKF6WvM6ZZLmi2Vz8Vt"
    print(get_songs_from_spotify_website(playlist))
