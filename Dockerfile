FROM ghcr.io/gis-ops/docker-valhalla/valhalla:latest
WORKDIR /tmp
RUN cat /usr/local/src/valhalla_locales | xargs -d '\n' -n1 locale-gen
WORKDIR /
ADD custom_files /custom_files
