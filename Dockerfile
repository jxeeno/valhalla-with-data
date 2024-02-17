FROM ghcr.io/gis-ops/docker-valhalla/valhalla:3.1.4
RUN cat /usr/local/src/valhalla_locales | xargs -d '\n' -n1 locale-gen
WORKDIR /
ADD custom_files /custom_files
