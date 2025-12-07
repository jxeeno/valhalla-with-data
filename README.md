# Valhalla with Custom Data

This repository builds Docker images containing Valhalla routing engine with custom OSM data modifications.

## Purpose

This repository is designed for **testing** and **custom use cases** where modifications to OSM data are needed but may not make sense to apply upstream to the main OpenStreetMap database. Common use cases include:

- **Custom road names** - Using local or proprietary naming conventions
- **Testing routing changes** - Validating modifications before upstream submission
- **Proprietary data overlays** - Adding custom attributes or restrictions
- **Regional customizations** - Modifications specific to a particular deployment

These modifications are applied during the build process and are **not** intended to be submitted back to OpenStreetMap.

## Workflow Overview

The build process applies modifications to OSM extracts in the following order:

1. **OSM Extract** - Base OSM data (PBF format)
2. **Change Files** - OSM change files (.osc, .osm, .opl) applied sequentially
3. **Tag Overrides** - JSON-based tag modifications (`modifications.json`)
4. **Valhalla Build** - Generate routing tiles from the modified OSM data
5. **Docker Image** - Package everything into a Docker image

## Configuration Source

Modification files (`modifications.json` and change files in `osc_files/`) are fetched from a **GitHub Gist** during the build process. This allows you to:

- Keep modification files private (Gist can be private)
- Update modifications without changing repository code
- Manage different modification sets for different deployments

### Setting Up the Gist

1. **Create a GitHub Gist** containing:
   - `modifications.json` - Tag override configuration
   - Any `.osc`, `.osm`, or `.opl` files - Change files to apply

2. **Configure the Gist URL**:
   - For GitHub Actions: Add `MODIFICATIONS_GIST_URL` as a repository secret
   - For local builds: Set the environment variable or pass as argument:
     ```bash
     export MODIFICATIONS_GIST_URL="https://gist.github.com/username/gist_id"
     # or just the Gist ID:
     export MODIFICATIONS_GIST_URL="gist_id"
     ```

3. **Authentication** (for private Gists):
   - GitHub Actions: Automatically uses `GITHUB_TOKEN` (no action needed)
   - Local builds: Set `GITHUB_TOKEN` environment variable:
     ```bash
     export GITHUB_TOKEN="your_github_token"
     ```

4. **Initialize modifications** before building:
   ```bash
   ./init_modifications.sh
   ```

The Gist can be public or private. For private Gists, ensure your GitHub token has access. GitHub Actions automatically has access via `GITHUB_TOKEN`.

## Prerequisites

### Required Tools

- **Python 3** with `pyosmium`:
  ```bash
  pip install osmium
  ```

- **osmium-tool** (for change file support):
  - Ubuntu/Debian: `sudo apt-get install osmium-tool`
  - macOS: `brew install osmium-tool`
  - Or download from: https://osmcode.org/osmium-tool/

- **Docker** - For building Valhalla tiles and Docker images

- **jq** (optional, for config modifications):
  - Ubuntu/Debian: `sudo apt-get install jq`
  - macOS: `brew install jq`

## Using Change Files (.osc, .osm, .opl)

### Supported File Formats

The build process supports three types of OSM change files:

1. **.osc files** - OpenStreetMap Change files (XML format)
   - Contains create/modify/delete operations
   - Exported from JOSM, iD Editor, or other OSM editors
   - Applied using `osmium apply-changes`

2. **.osm files** - Full OSM data files (XML format)
   - Contains complete OSM elements (nodes, ways, relations)
   - Can be exported from JOSM or downloaded from OSM
   - Merged using `osmium merge`

3. **.opl files** - OSM Protocol format (text-based)
   - Compact text-based format for OSM data
   - Can be exported from JOSM or converted from other formats
   - Merged using `osmium merge`

### Workflow with JOSM

1. **Open JOSM** and load the area you want to edit
2. **Make your changes** (add/modify/delete nodes, ways, relations)
3. **Export your changes**:
   - **As OSC**: File → Export → Export as OSM Change File (.osc)
   - **As OSM**: File → Export → Export as OSM XML (.osm)
   - **As OPL**: File → Export → Export as OPL (.opl)
   - Save to `osc_files/` directory
4. **Name your files** - Files are applied in alphabetical order, so use prefixes like:
   - `01_highway_changes.osc`
   - `02_poi_updates.osm`
   - `03_additional_data.opl`
   - etc.
5. **Run the build** - Change files will be automatically applied during the build process

### Change Files Directory

Place your change files in the `osc_files/` directory:

```
osc_files/
  ├── 01_highway_fixes.osc
  ├── 02_roundabout_updates.osm
  ├── 03_poi_additions.opl
  └── 04_additional_changes.osc
```

Files are processed in alphabetical order, so use numeric prefixes if order matters. All file types (.osc, .osm, .opl) are processed together in alphabetical order.

## Build Process

### Quick Start

1. **Initialize modifications from Gist** (if using Gist):
   ```bash
   export MODIFICATIONS_GIST_URL="your_gist_id_or_url"
   ./init_modifications.sh
   ```

2. **Run the build script**:
   ```bash
   ./build_valhalla_data.sh
   ```

This will:
1. Fetch modifications from Gist (if `MODIFICATIONS_GIST_URL` is set)
2. Download the OSM extract (default: Australia from Geofabrik)
3. Apply any change files from `osc_files/`
4. Apply tag overrides from `modifications.json`
5. Build Valhalla tiles
6. Prepare the `custom_files/` directory

### Manual Build Steps

If you prefer to run steps manually:

```bash
# 0. Initialize modifications from Gist (if using Gist)
export MODIFICATIONS_GIST_URL="your_gist_id_or_url"
./init_modifications.sh

# 1. Get OSM extract (or use your own)
curl -L "https://download.geofabrik.de/australia-oceania/australia-latest.osm.pbf" > input.pbf

# 2. Apply change files (.osc, .osm, .opl) if any
python3 apply_osc_files.py input.pbf after_osc.pbf osc_files/

# 3. Apply tag overrides
python3 apply_tag_overrides.py after_osc.pbf after_tags.pbf modifications.json

# 4. Build Valhalla tiles
mkdir custom_files
cp after_tags.pbf custom_files/
docker run -v $PWD/custom_files:/custom_files \
           -e serve_tiles=False \
           ghcr.io/gis-ops/docker-valhalla/valhalla:3.4.0
```

### Customizing the Build

You can customize the build by setting environment variables:

```bash
# Use a different OSM extract URL
export OSM_EXTRACT_URL="https://download.geofabrik.de/europe/germany-latest.osm.pbf"
./build_valhalla_data.sh

# Use a different OSC directory
export OSC_DIR="my_osc_files"
./build_valhalla_data.sh

# Use a different Valhalla Docker image
export VALHALLA_IMAGE="ghcr.io/valhalla/valhalla-scripted:latest"
./build_valhalla_data.sh
```

## File Structure

```
.
├── apply_osc_files.py          # Script to apply change files to PBF
├── apply_tag_overrides.py       # Script to apply tag overrides
├── build_valhalla_data.sh       # Master build script
├── init_modifications.sh        # Initialize modifications from GitHub Gist
├── modifications.json           # Tag override configuration (can be from Gist)
├── osc_files/                   # Directory for change files (can be from Gist)
│   ├── .gitkeep
│   └── README.md
├── custom_files/                # Generated during build
│   ├── *.osm.pbf               # Final modified OSM data
│   ├── valhalla.json           # Valhalla configuration
│   └── valhalla_tiles/         # Routing tiles (if not removed)
├── Dockerfile                   # Docker image definition
├── latest.Dockerfile           # Alternative Dockerfile
└── tagged.Dockerfile           # Tagged version Dockerfile
```

**Note**: `modifications.json` and files in `osc_files/` are typically fetched from a GitHub Gist during the build process using `init_modifications.sh`. The files in the repository are placeholders or defaults.

## Tag Overrides (modifications.json)

The `modifications.json` file allows you to override tags on specific OSM elements:

```json
[
  {
    "way_ids": [123456, 789012],
    "tags": {"highway": "motorway_link", "name": ""}
  },
  {
    "node_ids": [345678],
    "tags": {"highway": "motorway_junction"}
  }
]
```

## Docker Images

After building, you can create Docker images:

```bash
# Build using the default Dockerfile
docker build -t my-valhalla:latest .

# Or use a specific Dockerfile
docker build -f latest.Dockerfile -t my-valhalla:latest .
```

## Troubleshooting

### Change Files Not Applied

- Check that `osmium-tool` is installed: `osmium --version`
- Verify change files are in the `osc_files/` directory
- Check file extensions are `.osc`, `.osm`, or `.opl`
- Review logs for errors during change file application

### Build Fails

- Ensure all dependencies are installed (see Prerequisites)
- Check that the OSM extract downloaded successfully
- Verify Docker has enough resources (memory/disk space)
- Review error messages in the build output

### Changes Not Reflected

- Change files are applied in alphabetical order - check file naming
- Tag overrides in `modifications.json` may override change file modifications
- Ensure you're using the correct OSM element IDs
- For .osm and .opl files, elements are merged (not replaced) - conflicts may occur

## Contributing

When adding change files:
1. Export from JOSM or your OSM editor (.osc, .osm, or .opl format)
2. Place in `osc_files/` with a descriptive name
3. Use numeric prefixes if order matters
4. Test the build process locally before committing
5. Note: .osc files apply changes, while .osm and .opl files merge data

