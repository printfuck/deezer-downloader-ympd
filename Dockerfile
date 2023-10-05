FROM python:3.10-alpine3.17 AS builder
RUN pip install poetry
RUN apk add --no-cache g++ make cmake libmpdclient-dev openssl-dev git
COPY . /app
WORKDIR /app
RUN poetry build --format=wheel
WORKDIR /
RUN apk add --no-cache patch
RUN git clone https://github.com/SuperBFG7/ympd && \
    cd /ympd && \
    patch -p 1 < /app/deployment/docker/fix_header.patch && \
    mkdir -p /ympd/build && cd build && \
    cmake .. -DCMAKE_INSTALL_PREFIX:PATH=/usr && make


FROM python:3.10-alpine3.17
ENV PYTHONUNBUFFERED=TRUE

RUN apk add --no-cache ffmpeg nginx mpd supervisor libmpdclient openssl && \
    adduser -D deezer 

COPY --from=0 /ympd/build/ympd /usr/bin/ympd
COPY --from=0 /ympd/build/mkdata /usr/bin/mkdata

COPY --from=builder /app/dist/deezer_downloader*.whl .
RUN pip install deezer_downloader*.whl && \
    /usr/local/bin/deezer-downloader --show-config-template > /etc/deezer-downloader.ini && \
    sed -i "s,.*command = /usr/bin/yt-dlp.*,command = $(which yt-dlp)," /etc/deezer-downloader.ini && \
    sed -i 's,host = 127.0.0.1,host = 0.0.0.0,' /etc/deezer-downloader.ini && \
    sed -i 's,/tmp/deezer-downloader,/mnt/deezer-downloader,' /etc/deezer-downloader.ini && \
    rm deezer_downloader*.whl

ADD supervisord.conf /etc/supervisord.conf
ADD mpd.conf /etc/mpd.conf
ADD deezer-downloader.ini /etc/deezer-downloader.ini
ADD deployment/music-nginx.conf /etc/nginx/http.d/
RUN rm /etc/nginx/http.d/default.conf

EXPOSE 5000
#ENTRYPOINT ["/usr/local/bin/deezer-downloader", "--config", "/etc/deezer-downloader.ini"]
ENTRYPOINT ["/usr/bin/supervisord", "-c", "/etc/supervisord.conf"]
