#!/usr/bin/env python3
"""
Remove state road tagging for highway ways with network=AU:QLD:S or AU:QLD:MR.

This script:
- Removes AU:QLD:S and AU:QLD:MR entries from network= tags (handles semicolon-delimited lists)
- Removes corresponding ref= entries (handles semicolon-delimited lists, preserves other refs)
- Removes destination:ref= tags from highway ways if the value is numeric-only (regardless of network)
- Deletes all relations that have network=AU:QLD:S or AU:QLD:MR (handles semicolon-delimited lists)

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
TARGET_NETWORKS = ['AU:QLD:S', 'AU:QLD:MR', 'AU:QLD:NR']

def is_numeric_only(value):
    """Check if a string contains only numeric characters (digits)."""
    return bool(re.match(r'^\d+$', value))

def parse_semicolon_list(value):
    """Parse a semicolon-delimited list, handling empty values."""
    if not value:
        return []
    return [item.strip() for item in value.split(';') if item.strip()]

def join_semicolon_list(items):
    """Join a list into a semicolon-delimited string."""
    return ';'.join(items)

def remove_target_network_from_lists(network_value, ref_value):
    """
    Remove all AU:QLD:S and AU:QLD:MR entries from network and corresponding ref entries.
    
    Args:
        network_value: Network tag value (may be semicolon-delimited)
        ref_value: Ref tag value (may be semicolon-delimited)
    
    Returns:
        Tuple of (new_network_value, new_ref_value, modified)
        If all entries are removed, returns (None, None, True) to indicate tag should be deleted
    """
    # Parse the lists
    network_list = parse_semicolon_list(network_value) if network_value else []
    ref_list = parse_semicolon_list(ref_value) if ref_value else []
    
    if not network_list:
        return (network_value, ref_value, False)
    
    # Find indices to remove (where network is in TARGET_NETWORKS)
    indices_to_remove = [i for i, net in enumerate(network_list) if net in TARGET_NETWORKS]
    
    if not indices_to_remove:
        return (network_value, ref_value, False)
    
    # Remove from network list (in reverse order to maintain indices)
    for i in reversed(indices_to_remove):
        network_list.pop(i)
    
    # Remove corresponding ref entries (in reverse order)
    for i in reversed(indices_to_remove):
        if i < len(ref_list):
            ref_list.pop(i)
    
    # Determine what to return
    modified = True
    new_network_value = None
    new_ref_value = None
    
    if network_list:
        # Some network entries remain
        new_network_value = join_semicolon_list(network_list)
    # else: all network entries removed, return None to delete tag
    
    if ref_list:
        # Some ref entries remain
        new_ref_value = join_semicolon_list(ref_list)
    # else: all ref entries removed, return None to delete tag
    
    return (new_network_value, new_ref_value, modified)

class StateRoadTagRemover(osmium.SimpleHandler):
    """Remove AU:QLD:S and AU:QLD:MR entries from network/ref tags (handles semicolon-delimited lists), remove numeric-only destination:ref= tags, and delete relations with these networks."""
    
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
        
        # Check for network=AU:QLD:S or AU:QLD:MR (may be semicolon-delimited)
        network_value = tags_dict.get('network', '')
        if network_value:
            network_list = parse_semicolon_list(network_value)
            has_target_network = any(net in TARGET_NETWORKS for net in network_list)
        else:
            has_target_network = False
        
        # Check for numeric-only destination:ref (independent of network)
        if 'destination:ref' in tags_dict:
            dest_ref_value = tags_dict['destination:ref']
            if is_numeric_only(dest_ref_value):
                has_numeric_destination_ref = True
        
        # Remove tags based on conditions
        if has_highway and has_target_network:
            # Handle semicolon-delimited network and ref tags
            network_value = tags_dict.get('network', '')
            ref_value = tags_dict.get('ref', '')
            
            new_network_value, new_ref_value, network_modified = remove_target_network_from_lists(
                network_value, ref_value
            )
            
            if network_modified:
                modified = True
                # Update or remove network tag
                if new_network_value is None:
                    # All network entries removed
                    if 'network' in tags_dict:
                        del tags_dict['network']
                else:
                    # Some network entries remain
                    tags_dict['network'] = new_network_value
                
                # Update or remove ref tag
                if new_ref_value is None:
                    # All ref entries removed
                    if 'ref' in tags_dict:
                        del tags_dict['ref']
                else:
                    # Some ref entries remain
                    tags_dict['ref'] = new_ref_value
        
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
        
        # Check if this relation has network=AU:QLD:S or AU:QLD:MR (may be semicolon-delimited)
        tags_dict = dict(r.tags)
        
        network_value = tags_dict.get('network', '')
        has_target_network = False
        if network_value:
            network_list = parse_semicolon_list(network_value)
            has_target_network = any(net in TARGET_NETWORKS for net in network_list)
        
        if has_target_network:
            # Skip writing this relation (effectively deleting it)
            DELETED_RELATIONS_COUNT += 1
            found_networks = [net for net in network_list if net in TARGET_NETWORKS]
            logging.debug(f"Deleted relation_id={r.id} with network(s): {', '.join(found_networks)}")
        else:
            # Write the relation unchanged
            self.writer.add_relation(r)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python remove_state_road_tags.py input.pbf output.pbf")
        print("\nThis script:")
        print(f"  - Removes AU:QLD:S and AU:QLD:MR entries from network= tags (handles semicolon-delimited lists)")
        print(f"  - Removes corresponding ref= entries (preserves other refs)")
        print(f"  - Removes destination:ref= tags from highway ways if the value is numeric-only (regardless of network)")
        print(f"  - Deletes all relations with network=AU:QLD:S or AU:QLD:MR (handles semicolon-delimited lists)")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    handler = StateRoadTagRemover()
    writer = osmium.SimpleWriter(output_file)

    logging.info(f"Processing input file: {input_file}")
    logging.info(f"Output will be written to: {output_file}")
    logging.info(f"Target networks: {', '.join(TARGET_NETWORKS)}")

    try:
        handler.apply_writer(writer)
        handler.apply_file(input_file, locations=False)
    finally:
        writer.close()

    logging.info(f"Total ways processed: {TOTAL_WAYS}")
    logging.info(f"Total highway ways: {TOTAL_HIGHWAY_WAYS}")
    logging.info(f"Total ways modified (network/ref tags removed for networks {', '.join(TARGET_NETWORKS)}, or numeric-only destination:ref removed): {MODIFIED_WAYS_COUNT}")
    logging.info(f"Total relations processed: {TOTAL_RELATIONS}")
    logging.info(f"Total relations deleted (networks {', '.join(TARGET_NETWORKS)}): {DELETED_RELATIONS_COUNT}")

