## Music Downloader 🎶 🎧 💃 🦄

### What is this fork

I don't like ansible. I don't like to painstakingly configure every fucking config on my system.

I just wanna `docker compose up -d`:

```
services:
  deezer:
    image: pkill/deezer-ympd:latest
    build: .
    ports:
      - 8000:80
      - 6600:6600
    volumes:
      # MPD Library
      - ./mpd:/var/lib/mpd
      # MPD Music Library base path
      - ./data:/mnt/deezer-downloader
      # Logs
      - ./log:/log/
      # Your Collection
      # - /data/my_music:/mnt/deezer-downloader/my_music
      # your spotify cookies
      - ./cookies.txt:/app/cookies.txt
    environment:
      - DEEZER_COOKIE_ARL=908c985e1f7733b1d73801be42e5542d6eaf9c7550fb0019fae589f51e2d207ad889c0709402c97332bd8023469f36b948326b37b6f596099de42479f6aba2189cc5b6ab9052b0a08da7ecba873ab97a79598a8cc8431e66a0cba9223979d19f
```

Edit the example config to your liking. Build it or pull it.

### That's stupid - why are you shipping the mpd inside docker?!

I am personally using additionally a remote pulseaudio server. In the future I will probably also integrate a snapcast server. (pull requests welcome)

### Features

- download songs, albums, public playlists from Deezer.com (account is required, free plan is enough)
- download Spotify playlists (by parsing the Spotify website and download the songs from Deezer)
- download as zip file (including m3u8 playlist file)
- 320 kbit/s mp3s with ID3-Tags and album cover (UPDATE: right now only 128bkit/s mp3 works, see #66)
- download songs via yt-dlp
- KISS (keep it simple and stupid) front end
- MPD integration (use it on a Raspberry Pi - no don't do that!)
- simple REST api
- proxy support (https/socks5)
- **ADDED** supervisord with excellent logging
- **ADDED** mpd server preconfigured
- **ADDED** stupid html5 webaudio player integrated into ympd
- **ADDED** automatically plays the preconfigured http stream (available at http://[HOST]/stream)

### How to use it

 - Get a deezer ARL-Cookie (it looks like the one in the example above)
 - Create the folders: (I'm going to build scripts for this in the future)
    1. `mkdir -p ./log/supervisord` and 
    2. `mkdir -p ./mpd/playlists`. 
    3. `chmod -R 777 mpd log` both. 
 - `docker compose up -d`

### Some screenshots

Search for songs. You can listen to a 30 second preview in the browser.  

![](/docs/screenshots/2020-05-13-211356_screenshot.png)  

Search for albums. You can download them as zip file.  

![](/docs/screenshots/2020-05-13-213544_screenshot.png)

List songs of an album.

![](/docs/screenshots/2020-05-13-211528_screenshot.png)

Download songs with youtube-dl  

![](/docs/screenshots/2020-05-13-211622_screenshot.png)

Download a Spotify playlist.   

![](/docs/screenshots/2020-05-13-211629_screenshot.png)  

Download a Deezer playlist.    

![](/docs/screenshots/2020-05-13-211633_screenshot.png)  


