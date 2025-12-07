#!/usr/bin/env python3
"""
Apply OSM change files (.osc, .osm, .opl) to an OSM PBF extract.

This script applies OSM change files from a directory to an OSM PBF file.
It supports:
  - .osc files: OpenStreetMap Change files (uses osmium apply-changes)
  - .osm files: Full OSM data files (uses osmium merge)
  - .opl files: OSM Protocol format files (uses osmium merge)

Usage:
    python apply_osc_files.py input.pbf output.pbf change_files_directory
"""

import sys
import os
import subprocess
import logging
from pathlib import Path
import tempfile
from collections import defaultdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)


def find_change_files(change_dir):
    """Find all .osc, .osm, and .opl files in the directory, sorted by name."""
    change_path = Path(change_dir)
    if not change_path.exists():
        logging.warning(f"Change files directory does not exist: {change_dir}")
        return []
    
    # Find all supported file types
    osc_files = sorted(change_path.glob("*.osc"))
    osm_files = sorted(change_path.glob("*.osm"))
    opl_files = sorted(change_path.glob("*.opl"))
    
    # Combine and sort all files by name (so they're processed in order)
    all_files = []
    for f in osc_files:
        all_files.append(('osc', str(f)))
    for f in osm_files:
        all_files.append(('osm', str(f)))
    for f in opl_files:
        all_files.append(('opl', str(f)))
    
    # Sort by filename
    all_files.sort(key=lambda x: x[1])
    
    return all_files


def check_osmium_tool():
    """Check if osmium tool is available."""
    try:
        result = subprocess.run(
            ['osmium', '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def apply_change_file_with_osmium(input_pbf, output_pbf, file_type, change_file):
    """Apply a single change file using osmium-tool.
    
    Args:
        input_pbf: Input PBF file
        output_pbf: Output PBF file
        file_type: Type of file ('osc', 'osm', or 'opl')
        change_file: Path to the change file
    
    Returns:
        True if successful, False otherwise
    """
    if file_type == 'osc':
        # Use apply-changes for OSC files
        cmd = [
            'osmium', 'apply-changes',
            input_pbf,
            change_file,
            '-f', 'pbf',
            '-o', output_pbf
        ]
    elif file_type in ('osm', 'opl'):
        # Use merge for .osm and .opl files
        cmd = [
            'osmium', 'merge',
            input_pbf,
            change_file,
            '-f', 'pbf',
            '-o', output_pbf
        ]
    else:
        logging.error(f"Unknown file type: {file_type}")
        return False
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=3600  # 1 hour timeout
    )
    
    if result.returncode != 0:
        logging.error(f"osmium command failed for {change_file} ({file_type}):")
        logging.error(f"Command: {' '.join(cmd)}")
        logging.error(f"stdout: {result.stdout}")
        logging.error(f"stderr: {result.stderr}")
        return False
    
    return True


def apply_change_files_with_osmium(input_pbf, output_pbf, change_files):
    """Apply change files (.osc, .osm, .opl) using osmium-tool."""
    if not change_files:
        logging.info("No change files to apply, copying input to output")
        import shutil
        shutil.copy2(input_pbf, output_pbf)
        return True
    
    # Group files by type for logging
    file_counts = defaultdict(int)
    for file_type, _ in change_files:
        file_counts[file_type] += 1
    
    logging.info(f"Found {len(change_files)} change file(s) to apply:")
    for file_type, count in sorted(file_counts.items()):
        type_name = {'osc': 'OSC', 'osm': 'OSM', 'opl': 'OPL'}.get(file_type, file_type.upper())
        logging.info(f"  - {count} {type_name} file(s)")
    
    # Apply files sequentially
    current_file = input_pbf
    temp_files = []
    
    try:
        for i, (file_type, change_file) in enumerate(change_files):
            file_name = os.path.basename(change_file)
            type_name = {'osc': 'OSC', 'osm': 'OSM', 'opl': 'OPL'}.get(file_type, file_type.upper())
            logging.info(f"Applying {type_name} file {i+1}/{len(change_files)}: {file_name}")
            
            # For intermediate steps, use a temporary file
            # For the final step, use the output file
            if i == len(change_files) - 1:
                next_file = output_pbf
            else:
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pbf')
                next_file = temp_file.name
                temp_file.close()
                temp_files.append(next_file)
            
            # Apply the change file
            if not apply_change_file_with_osmium(current_file, next_file, file_type, change_file):
                return False
            
            # Move to next file for next iteration
            if current_file != input_pbf:
                # Clean up previous temp file
                try:
                    os.unlink(current_file)
                except:
                    pass
            
            current_file = next_file
        
        logging.info("All change files applied successfully!")
        return True
        
    except subprocess.TimeoutExpired:
        logging.error("osmium command timed out after 1 hour")
        return False
    except Exception as e:
        logging.error(f"Error running osmium: {e}")
        return False
    finally:
        # Clean up any remaining temporary files
        for temp_file in temp_files:
            try:
                if temp_file != output_pbf and os.path.exists(temp_file):
                    os.unlink(temp_file)
            except:
                pass


def apply_change_files(input_pbf, output_pbf, change_dir):
    """Apply change files (.osc, .osm, .opl) to the input PBF and write to output PBF."""
    
    if not os.path.exists(input_pbf):
        logging.error(f"Input PBF file not found: {input_pbf}")
        return False
    
    # Find change files
    change_files = find_change_files(change_dir)
    
    if not change_files:
        logging.info(f"No change files found in {change_dir}, copying input to output unchanged")
        import shutil
        shutil.copy2(input_pbf, output_pbf)
        return True
    
    # Check if osmium tool is available
    if not check_osmium_tool():
        logging.error("osmium-tool is not installed or not in PATH")
        logging.error("Please install osmium-tool:")
        logging.error("  - Ubuntu/Debian: sudo apt-get install osmium-tool")
        logging.error("  - macOS: brew install osmium-tool")
        logging.error("  - Or download from: https://osmcode.org/osmium-tool/")
        return False
    
    # Apply change files using osmium-tool
    return apply_change_files_with_osmium(input_pbf, output_pbf, change_files)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python apply_osc_files.py input.pbf output.pbf change_files_directory")
        print("\nThis script applies OSM change files to an OSM PBF extract.")
        print("Supported formats:")
        print("  - .osc files: OpenStreetMap Change files (uses osmium apply-changes)")
        print("  - .osm files: Full OSM data files (uses osmium merge)")
        print("  - .opl files: OSM Protocol format files (uses osmium merge)")
        print("\nAll files in the specified directory will be applied sequentially in alphabetical order.")
        print("\nRequirements:")
        print("  - osmium-tool must be installed (https://osmcode.org/osmium-tool/)")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    change_directory = sys.argv[3]
    
    try:
        success = apply_change_files(input_file, output_file, change_directory)
        if success:
            logging.info("Change file application completed successfully!")
            sys.exit(0)
        else:
            logging.error("Change file application failed!")
            sys.exit(1)
    except Exception as e:
        logging.error(f"Failed to apply change files: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
