#!/bin/bash
#
# Master build script for Valhalla data with OSM extracts, change files, and tag overrides
#
# This script orchestrates the complete workflow:
# 1. Fetch/download OSM extract (PBF)
# 2. Apply change files (.osc, .osm, .opl) from osc_files/ (if any exist)
# 3. Apply tag overrides from modifications.json
# 4. Build Valhalla tiles
# 5. Prepare custom_files directory for Docker build
#
# Usage:
#   ./build_valhalla_data.sh [input_pbf] [output_pbf]
#
# If input_pbf is not provided, it will be fetched from Geofabrik
# If output_pbf is not provided, it defaults to custom_files/australia-latest.osm.pbf

set -e  # Exit on error

# Configuration
OSM_EXTRACT_URL="${OSM_EXTRACT_URL:-https://download.geofabrik.de/australia-oceania/australia-latest.osm.pbf}"
OSC_DIR="${OSC_DIR:-osc_files}"
MODIFICATIONS_JSON="${MODIFICATIONS_JSON:-modifications.json}"
CUSTOM_FILES_DIR="${CUSTOM_FILES_DIR:-custom_files}"
VALHALLA_IMAGE="${VALHALLA_IMAGE:-ghcr.io/gis-ops/docker-valhalla/valhalla:3.4.0}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check dependencies
check_dependencies() {
    log_info "Checking dependencies..."
    
    # Check Python and osmium
    if ! python3 -c "import osmium" 2>/dev/null; then
        log_error "pyosmium is not installed. Install with: pip install osmium"
        exit 1
    fi
    
    # Check osmium-tool (for OSC file application)
    if ! command -v osmium &> /dev/null; then
        log_warn "osmium-tool is not installed. OSC file support will not work."
        log_warn "Install with:"
        log_warn "  - Ubuntu/Debian: sudo apt-get install osmium-tool"
        log_warn "  - macOS: brew install osmium-tool"
        log_warn "  - Or download from: https://osmcode.org/osmium-tool/"
    fi
    
    # Check jq (for config modifications)
    if ! command -v jq &> /dev/null; then
        log_warn "jq is not installed. Config modifications will be skipped."
        log_warn "Install with:"
        log_warn "  - Ubuntu/Debian: sudo apt-get install jq"
        log_warn "  - macOS: brew install jq"
    fi
    
    log_info "Dependencies check complete"
}

# Step 1: Fetch or use provided OSM extract
fetch_osm_extract() {
    local input_pbf="$1"
    
    if [ -n "$input_pbf" ] && [ -f "$input_pbf" ]; then
        log_info "Using provided OSM extract: $input_pbf"
        echo "$input_pbf"
        return
    fi
    
    log_info "Fetching OSM extract from Geofabrik..."
    local temp_pbf="tmp_$(basename $OSM_EXTRACT_URL)"
    
    if curl -L -f -H "User-Agent: valhalla-with-data/1.0" "$OSM_EXTRACT_URL" > "$temp_pbf"; then
        # Verify file size (should be > 512KB for a valid PBF)
        local size=$(stat -c%s "$temp_pbf" 2>/dev/null || stat -f%z "$temp_pbf" 2>/dev/null)
        if [ "$size" -lt 524288 ]; then
            log_error "Downloaded file is too small ($size bytes). Outputting contents:"
            cat "$temp_pbf"
            rm -f "$temp_pbf"
            exit 1
        fi
        log_info "Downloaded OSM extract: $temp_pbf ($(du -h "$temp_pbf" | cut -f1))"
        echo "$temp_pbf"
    else
        log_error "Failed to download OSM extract from $OSM_EXTRACT_URL"
        exit 1
    fi
}

# Step 2: Apply change files (.osc, .osm, .opl)
apply_change_files() {
    local input_pbf="$1"
    local output_pbf="$2"
    
    # Check if any change files exist
    local has_files=false
    if [ -d "$OSC_DIR" ]; then
        if ls $OSC_DIR/*.osc $OSC_DIR/*.osm $OSC_DIR/*.opl 2>/dev/null | grep -q .; then
            has_files=true
        fi
    fi
    
    if [ "$has_files" = false ]; then
        log_info "No change files (.osc, .osm, .opl) found in $OSC_DIR, skipping"
        cp "$input_pbf" "$output_pbf"
        return
    fi
    
    local osc_count=$(ls -1 $OSC_DIR/*.osc 2>/dev/null | wc -l)
    local osm_count=$(ls -1 $OSC_DIR/*.osm 2>/dev/null | wc -l)
    local opl_count=$(ls -1 $OSC_DIR/*.opl 2>/dev/null | wc -l)
    local total_count=$((osc_count + osm_count + opl_count))
    
    log_info "Applying $total_count change file(s) from $OSC_DIR:"
    [ $osc_count -gt 0 ] && log_info "  - $osc_count OSC file(s)"
    [ $osm_count -gt 0 ] && log_info "  - $osm_count OSM file(s)"
    [ $opl_count -gt 0 ] && log_info "  - $opl_count OPL file(s)"
    
    if python3 apply_osc_files.py "$input_pbf" "$output_pbf" "$OSC_DIR"; then
        log_info "Change files applied successfully"
    else
        log_error "Failed to apply change files"
        exit 1
    fi
}

# Step 3: Apply tag overrides
apply_tag_overrides() {
    local input_pbf="$1"
    local output_pbf="$2"
    
    if [ ! -f "$MODIFICATIONS_JSON" ]; then
        log_warn "modifications.json not found, skipping tag overrides"
        cp "$input_pbf" "$output_pbf"
        return
    fi
    
    log_info "Applying tag overrides from $MODIFICATIONS_JSON..."
    
    if python3 apply_tag_overrides.py "$input_pbf" "$output_pbf" "$MODIFICATIONS_JSON"; then
        log_info "Tag overrides applied successfully"
    else
        log_error "Failed to apply tag overrides"
        exit 1
    fi
}

# Step 4: Build Valhalla tiles
build_valhalla_tiles() {
    local pbf_file="$1"
    
    log_info "Preparing custom_files directory..."
    mkdir -p "$CUSTOM_FILES_DIR"
    cp "$pbf_file" "$CUSTOM_FILES_DIR/$(basename $pbf_file)"
    
    log_info "Building Valhalla tiles using Docker image: $VALHALLA_IMAGE"
    log_info "This may take a while..."
    
    if docker run -v "$PWD/$CUSTOM_FILES_DIR:/custom_files" \
                  -e serve_tiles=False \
                  "$VALHALLA_IMAGE"; then
        log_info "Valhalla tiles built successfully"
    else
        log_error "Failed to build Valhalla tiles"
        exit 1
    fi
    
    # Clean up tiles directory if it exists (we only want the PBF and config)
    if [ -d "$CUSTOM_FILES_DIR/valhalla_tiles" ]; then
        log_info "Removing temporary tiles directory..."
        sudo rm -rf "$CUSTOM_FILES_DIR/valhalla_tiles" 2>/dev/null || rm -rf "$CUSTOM_FILES_DIR/valhalla_tiles" 2>/dev/null
    fi
}

# Step 5: Update Valhalla config (optional)
update_valhalla_config() {
    if ! command -v jq &> /dev/null; then
        log_warn "jq not available, skipping config updates"
        return
    fi
    
    local config_file="$CUSTOM_FILES_DIR/valhalla.json"
    if [ ! -f "$config_file" ]; then
        log_warn "valhalla.json not found, skipping config updates"
        return
    fi
    
    log_info "Updating Valhalla configuration..."
    
    # Update trace max_distance
    jq '.service_limits.trace.max_distance = 500000' "$config_file" > /tmp/valhalla.json
    mv /tmp/valhalla.json "$config_file"
    
    # Update trace max_shape
    jq '.service_limits.trace.max_shape = 32000' "$config_file" > /tmp/valhalla.json
    mv /tmp/valhalla.json "$config_file"
    
    log_info "Valhalla configuration updated"
}

# Main workflow
main() {
    local input_pbf="$1"
    local final_output="$2"
    
    log_info "Starting Valhalla data build process..."
    log_info "========================================"
    
    # Check dependencies
    check_dependencies
    
    # Step 1: Get OSM extract
    local base_pbf=$(fetch_osm_extract "$input_pbf")
    
    # Create temporary files for processing pipeline
    local after_osc="after_osc.pbf"
    local after_tags="after_tags.pbf"
    
    # Step 2: Apply change files (.osc, .osm, .opl)
    apply_change_files "$base_pbf" "$after_osc"
    
    # Step 3: Apply tag overrides
    apply_tag_overrides "$after_osc" "$after_tags"
    
    # Step 4: Build Valhalla tiles
    build_valhalla_tiles "$after_tags"
    
    # Step 5: Update config
    update_valhalla_config
    
    # Cleanup temporary files
    log_info "Cleaning up temporary files..."
    if [ "$base_pbf" != "$input_pbf" ] && [[ "$base_pbf" == tmp_* ]]; then
        rm -f "$base_pbf"
    fi
    rm -f "$after_osc" "$after_tags"
    
    log_info "========================================"
    log_info "Build process completed successfully!"
    log_info "Output files are in: $CUSTOM_FILES_DIR"
    
    if [ -n "$final_output" ]; then
        log_info "Copying final PBF to: $final_output"
        cp "$CUSTOM_FILES_DIR/$(basename $after_tags)" "$final_output"
    fi
}

# Run main function
main "$@"

