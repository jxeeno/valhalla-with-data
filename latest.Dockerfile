FROM ghcr.io/nilsnolde/docker-valhalla/valhalla:latest
USER root
RUN cd /tmp && cat /usr/local/src/valhalla_locales | xargs -d '\n' -n1 locale-gen
USER valhalla
WORKDIR /
ADD custom_files /custom_files
