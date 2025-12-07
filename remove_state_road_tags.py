#!/usr/bin/env python3
"""
Remove state road tagging for highway ways with network=AU:QLD:S.

This script removes both network= and ref= tags from highway ways that have
network=AU:QLD:S.

Usage:
    python remove_state_road_tags.py input.pbf output.pbf
"""

import osmium
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)

MODIFIED_WAYS_COUNT = 0
TOTAL_WAYS = 0
TOTAL_HIGHWAY_WAYS = 0
TARGET_NETWORK = 'AU:QLD:S'

class StateRoadTagRemover(osmium.SimpleHandler):
    """Remove network= and ref= tags from highway ways with network=AU:QLD:S."""
    
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
        
        tags_dict = dict(w.tags)
        
        if 'highway' in tags_dict:
            has_highway = True
            TOTAL_HIGHWAY_WAYS += 1
        
        if 'network' in tags_dict and tags_dict['network'] == TARGET_NETWORK:
            has_target_network = True
        
        # If it's a highway way with network=AU:QLD:S, remove network= and ref=
        if has_highway and has_target_network:
            # Remove network and ref tags
            if 'network' in tags_dict:
                del tags_dict['network']
            if 'ref' in tags_dict:
                del tags_dict['ref']
            
            # Create a new mutable way with updated tags
            new_way = osmium.osm.mutable.Way(w)
            new_way.tags = [(k, v) for k, v in tags_dict.items()]
            
            self.writer.add_way(new_way)
            MODIFIED_WAYS_COUNT += 1
            logging.debug(f"Removed network= and ref= tags from way_id={w.id}")
        else:
            # Write the way unchanged
            self.writer.add_way(w)

    def node(self, n):
        self.writer.add_node(n)

    def relation(self, r):
        self.writer.add_relation(r)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python remove_state_road_tags.py input.pbf output.pbf")
        print("\nThis script removes network= and ref= tags from highway ways")
        print(f"that have network={TARGET_NETWORK}.")
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
    logging.info(f"Total ways modified (network and ref tags removed): {MODIFIED_WAYS_COUNT}")

