#!/usr/bin/env python3
"""
Remove state road tagging for highway ways with network=AU:QLD:S.

This script:
- Removes network= and ref= tags from highway ways that have network=AU:QLD:S
- Removes destination:ref= tags from highway ways if the value is numeric-only (regardless of network)
- Deletes all relations that have network=AU:QLD:S

Usage:
    python remove_state_road_tags.py input.pbf output.pbf
"""

import osmium
import sys
import logging
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)

MODIFIED_WAYS_COUNT = 0
TOTAL_WAYS = 0
TOTAL_HIGHWAY_WAYS = 0
DELETED_RELATIONS_COUNT = 0
TOTAL_RELATIONS = 0
TARGET_NETWORK = 'AU:QLD:S'

def is_numeric_only(value):
    """Check if a string contains only numeric characters (digits)."""
    return bool(re.match(r'^\d+$', value))

class StateRoadTagRemover(osmium.SimpleHandler):
    """Remove network= and ref= tags from highway ways with network=AU:QLD:S, remove numeric-only destination:ref= tags, and delete relations with network=AU:QLD:S."""
    
    def __init__(self):
        super().__init__()
        self.writer = None

    def apply_writer(self, writer):
        self.writer = writer

    def way(self, w):
        global MODIFIED_WAYS_COUNT, TOTAL_WAYS, TOTAL_HIGHWAY_WAYS
        
        TOTAL_WAYS += 1
        
        # Check if this is a highway way
        has_highway = False
        has_target_network = False
        has_numeric_destination_ref = False
        
        tags_dict = dict(w.tags)
        modified = False
        
        if 'highway' in tags_dict:
            has_highway = True
            TOTAL_HIGHWAY_WAYS += 1
        
        # Check for network=AU:QLD:S
        if 'network' in tags_dict and tags_dict['network'] == TARGET_NETWORK:
            has_target_network = True
        
        # Check for numeric-only destination:ref (independent of network)
        if 'destination:ref' in tags_dict:
            dest_ref_value = tags_dict['destination:ref']
            if is_numeric_only(dest_ref_value):
                has_numeric_destination_ref = True
        
        # Remove tags based on conditions
        if has_highway and has_target_network:
            # Remove network and ref tags
            if 'network' in tags_dict:
                del tags_dict['network']
                modified = True
            if 'ref' in tags_dict:
                del tags_dict['ref']
                modified = True
        
        # Remove numeric-only destination:ref (regardless of network)
        if has_highway and has_numeric_destination_ref:
            if 'destination:ref' in tags_dict:
                del tags_dict['destination:ref']
                modified = True
        
        # Write the way (modified or unchanged)
        if modified:
            # Create a new mutable way with updated tags
            new_way = osmium.osm.mutable.Way(w)
            new_way.tags = [(k, v) for k, v in tags_dict.items()]
            
            self.writer.add_way(new_way)
            MODIFIED_WAYS_COUNT += 1
            
            removed_tags = []
            if has_target_network:
                removed_tags.append("network=")
                removed_tags.append("ref=")
            if has_numeric_destination_ref:
                removed_tags.append("destination:ref=")
            logging.debug(f"Removed {', '.join(removed_tags)} tags from way_id={w.id}")
        else:
            # Write the way unchanged
            self.writer.add_way(w)

    def node(self, n):
        self.writer.add_node(n)

    def relation(self, r):
        global DELETED_RELATIONS_COUNT, TOTAL_RELATIONS
        
        TOTAL_RELATIONS += 1
        
        # Check if this relation has network=AU:QLD:S
        tags_dict = dict(r.tags)
        
        if 'network' in tags_dict and tags_dict['network'] == TARGET_NETWORK:
            # Skip writing this relation (effectively deleting it)
            DELETED_RELATIONS_COUNT += 1
            logging.debug(f"Deleted relation_id={r.id} with network={TARGET_NETWORK}")
        else:
            # Write the relation unchanged
            self.writer.add_relation(r)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python remove_state_road_tags.py input.pbf output.pbf")
        print("\nThis script:")
        print(f"  - Removes network= and ref= tags from highway ways with network={TARGET_NETWORK}")
        print(f"  - Removes destination:ref= tags from highway ways if the value is numeric-only (regardless of network)")
        print(f"  - Deletes all relations with network={TARGET_NETWORK}")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    handler = StateRoadTagRemover()
    writer = osmium.SimpleWriter(output_file)

    logging.info(f"Processing input file: {input_file}")
    logging.info(f"Output will be written to: {output_file}")
    logging.info(f"Target network: {TARGET_NETWORK}")

    try:
        handler.apply_writer(writer)
        handler.apply_file(input_file, locations=False)
    finally:
        writer.close()

    logging.info(f"Total ways processed: {TOTAL_WAYS}")
    logging.info(f"Total highway ways: {TOTAL_HIGHWAY_WAYS}")
    logging.info(f"Total ways modified (network/ref tags removed for network={TARGET_NETWORK}, or numeric-only destination:ref removed): {MODIFIED_WAYS_COUNT}")
    logging.info(f"Total relations processed: {TOTAL_RELATIONS}")
    logging.info(f"Total relations deleted (network={TARGET_NETWORK}): {DELETED_RELATIONS_COUNT}")

