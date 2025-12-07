#!/bin/bash
#
# Initialize modifications from GitHub Gist
#
# This script fetches modifications.json and change files (.osc, .osm, .opl)
# from a GitHub Gist and places them in the appropriate locations.
#
# Usage:
#   ./init_modifications.sh [gist_url]
#
# Environment variables:
#   MODIFICATIONS_GIST_URL - GitHub Gist URL or Gist ID (required if not provided as argument)
#
# The Gist should contain:
#   - modifications.json (will replace the existing file)
#   - Any .osc, .osm, or .opl files (will be placed in osc_files/)

set -e

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

# Get Gist URL from argument or environment variable
GIST_URL="${1:-${MODIFICATIONS_GIST_URL}}"

if [ -z "$GIST_URL" ]; then
    log_error "Gist URL not provided"
    log_error "Usage: ./init_modifications.sh [gist_url]"
    log_error "Or set MODIFICATIONS_GIST_URL environment variable"
    exit 1
fi

# Extract Gist ID from URL if full URL is provided
# Supports formats:
#   - https://gist.github.com/username/gist_id
#   - https://gist.github.com/gist_id
#   - gist_id
GIST_ID=$(echo "$GIST_URL" | sed -E 's|https?://gist\.github\.com/[^/]+/||' | sed -E 's|https?://gist\.github\.com/||' | sed 's|/.*||')

if [ -z "$GIST_ID" ]; then
    log_error "Could not extract Gist ID from: $GIST_URL"
    exit 1
fi

log_info "Fetching modifications from Gist: $GIST_ID"

# Create temporary directory for Gist contents
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

# Fetch Gist metadata to get file list
log_info "Fetching Gist metadata..."
GIST_API_URL="https://api.github.com/gists/$GIST_ID"

# Use GitHub token if available (for private Gists or rate limiting)
if [ -n "$GITHUB_TOKEN" ]; then
    log_info "Using GITHUB_TOKEN for authentication"
    GIST_JSON=$(curl -s -f -H "Authorization: token $GITHUB_TOKEN" "$GIST_API_URL" || {
        log_error "Failed to fetch Gist. Check that:"
        log_error "  1. The Gist ID is correct: $GIST_ID"
        log_error "  2. The Gist is accessible with the provided token"
        exit 1
    })
else
    GIST_JSON=$(curl -s -f "$GIST_API_URL" || {
        log_error "Failed to fetch Gist. Check that:"
        log_error "  1. The Gist ID is correct: $GIST_ID"
        log_error "  2. The Gist is public or set GITHUB_TOKEN for private Gists"
        exit 1
    })
fi

# Check if we got valid JSON
if ! echo "$GIST_JSON" | jq -e . > /dev/null 2>&1; then
    log_error "Invalid response from Gist API. Response:"
    echo "$GIST_JSON"
    exit 1
fi

# Extract file information
FILES=$(echo "$GIST_JSON" | jq -r '.files | keys[]')

if [ -z "$FILES" ]; then
    log_error "No files found in Gist"
    exit 1
fi

# Count files by type
OSC_COUNT=0
OSM_COUNT=0
OPL_COUNT=0
JSON_COUNT=0
OTHER_COUNT=0

# Download files
log_info "Downloading files from Gist..."
mkdir -p osc_files

for filename in $FILES; do
    # Get raw URL for the file
    raw_url=$(echo "$GIST_JSON" | jq -r ".files[\"$filename\"].raw_url")
    
    if [ -z "$raw_url" ] || [ "$raw_url" = "null" ]; then
        log_warn "Could not get raw URL for: $filename"
        continue
    fi
    
    # Determine file type and destination
    if [ "$filename" = "modifications.json" ]; then
        dest="modifications.json"
        JSON_COUNT=$((JSON_COUNT + 1))
        log_info "  Downloading: $filename -> $dest"
        curl -s -f -L "$raw_url" > "$dest" || {
            log_error "Failed to download $filename"
            exit 1
        }
    elif [[ "$filename" == *.osc ]]; then
        dest="osc_files/$filename"
        OSC_COUNT=$((OSC_COUNT + 1))
        log_info "  Downloading: $filename -> $dest"
        curl -s -f -L "$raw_url" > "$dest" || {
            log_error "Failed to download $filename"
            exit 1
        }
    elif [[ "$filename" == *.osm ]]; then
        dest="osc_files/$filename"
        OSM_COUNT=$((OSM_COUNT + 1))
        log_info "  Downloading: $filename -> $dest"
        curl -s -f -L "$raw_url" > "$dest" || {
            log_error "Failed to download $filename"
            exit 1
        }
    elif [[ "$filename" == *.opl ]]; then
        dest="osc_files/$filename"
        OPL_COUNT=$((OPL_COUNT + 1))
        log_info "  Downloading: $filename -> $dest"
        curl -s -f -L "$raw_url" > "$dest" || {
            log_error "Failed to download $filename"
            exit 1
        }
    else
        OTHER_COUNT=$((OTHER_COUNT + 1))
        log_warn "  Skipping unsupported file: $filename"
    fi
done

# Summary
log_info "========================================"
log_info "Downloaded files from Gist:"
[ $JSON_COUNT -gt 0 ] && log_info "  - modifications.json: $JSON_COUNT file(s)"
[ $OSC_COUNT -gt 0 ] && log_info "  - OSC files: $OSC_COUNT file(s)"
[ $OSM_COUNT -gt 0 ] && log_info "  - OSM files: $OSM_COUNT file(s)"
[ $OPL_COUNT -gt 0 ] && log_info "  - OPL files: $OPL_COUNT file(s)"
[ $OTHER_COUNT -gt 0 ] && log_warn "  - Skipped files: $OTHER_COUNT file(s)"
log_info "========================================"

if [ $JSON_COUNT -eq 0 ]; then
    log_warn "No modifications.json found in Gist. Using existing file if present."
fi

if [ $OSC_COUNT -eq 0 ] && [ $OSM_COUNT -eq 0 ] && [ $OPL_COUNT -eq 0 ]; then
    log_warn "No change files (.osc, .osm, .opl) found in Gist."
fi

log_info "Modifications initialized successfully!"

