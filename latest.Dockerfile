FROM ghcr.io/nilsnolde/docker-valhalla/valhalla:latest
# RUN cd /tmp && cat /usr/local/src/valhalla_locales | xargs -d '\n' -n1 locale-gen
# WORKDIR /
ADD custom_files /custom_files