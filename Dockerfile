FROM ghcr.io/gis-ops/docker-valhalla/valhalla:3.4.0
USER root
RUN cd /tmp && cat /usr/local/src/valhalla_locales | xargs -d '\n' -n1 locale-gen
USER valhalla
WORKDIR /
ADD custom_files /custom_files
