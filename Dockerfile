FROM ghcr.io/gis-ops/docker-valhalla/valhalla:latest
WORKDIR /
ADD custom_files /custom_files
ADD transit_tiles /transit_tiles
