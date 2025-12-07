#!/usr/bin/env python3
"""
Generate an OSC (OSM Change) file by comparing two OSM PBF files.

This script compares an original and modified OSM PBF file and generates
an OSC change file containing create, modify, and delete operations.

Usage:
    python generate_osc_from_diff.py original.pbf modified.pbf output.osc
"""

import osmium
import sys
import xml.etree.ElementTree as ET
from xml.dom import minidom
import logging
from collections import defaultdict
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)


class ElementData:
    """Store element data for comparison."""
    def __init__(self, element):
        self.id = element.id
        self.version = element.version
        self.timestamp = element.timestamp
        self.uid = element.uid if hasattr(element, 'uid') else None
        self.user = element.user if hasattr(element, 'user') else None
        self.changeset = element.changeset if hasattr(element, 'changeset') else None
        self.tags = dict(element.tags)
        
        # For nodes: lat/lon
        if isinstance(element, osmium.osm.Node):
            self.lat = element.location.lat
            self.lon = element.location.lon
            self.location = (element.location.lat, element.location.lon)
        else:
            self.location = None
        
        # For ways: node references
        if isinstance(element, osmium.osm.Way):
            self.nodes = [node.ref for node in element.nodes]
        else:
            self.nodes = None
        
        # For relations: members
        if isinstance(element, osmium.osm.Relation):
            self.members = [(m.type, m.ref, m.role) for m in element.members]
        else:
            self.members = None
    
    def __eq__(self, other):
        """Compare two elements, ignoring version/timestamp/user metadata."""
        if self.id != other.id:
            return False
        
        # Compare tags
        if self.tags != other.tags:
            return False
        
        # Compare location (for nodes)
        if self.location is not None and other.location is not None:
            if abs(self.lat - other.lat) > 1e-7 or abs(self.lon - other.lon) > 1e-7:
                return False
        
        # Compare nodes (for ways)
        if self.nodes is not None and other.nodes is not None:
            if self.nodes != other.nodes:
                return False
        
        # Compare members (for relations)
        if self.members is not None and other.members is not None:
            if self.members != other.members:
                return False
        
        return True
    
    def is_modified(self, other):
        """Check if element is modified compared to another."""
        return not self.__eq__(other)


class PBFReader(osmium.SimpleHandler):
    """Read and store all elements from a PBF file."""
    
    def __init__(self):
        super().__init__()
        self.nodes = {}
        self.ways = {}
        self.relations = {}
    
    def node(self, n):
        self.nodes[n.id] = ElementData(n)
    
    def way(self, w):
        self.ways[w.id] = ElementData(w)
    
    def relation(self, r):
        self.relations[r.id] = ElementData(r)


def format_timestamp(timestamp):
    """Format timestamp for OSC output."""
    if timestamp:
        return timestamp.strftime('%Y-%m-%dT%H:%M:%SZ')
    return datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')


def create_osm_element_xml(element_data, element_type):
    """Create XML element for an OSM element."""
    elem = ET.Element(element_type)
    elem.set('id', str(element_data.id))
    elem.set('version', str(element_data.version))
    
    if element_data.timestamp:
        elem.set('timestamp', format_timestamp(element_data.timestamp))
    
    if element_data.uid is not None:
        elem.set('uid', str(element_data.uid))
    
    if element_data.user:
        elem.set('user', element_data.user)
    
    if element_data.changeset is not None:
        elem.set('changeset', str(element_data.changeset))
    
    # Add location for nodes
    if element_type == 'node' and element_data.location:
        elem.set('lat', str(element_data.lat))
        elem.set('lon', str(element_data.lon))
    
    # Add node references for ways
    if element_type == 'way' and element_data.nodes:
        for node_ref in element_data.nodes:
            nd = ET.SubElement(elem, 'nd')
            nd.set('ref', str(node_ref))
    
    # Add members for relations
    if element_type == 'relation' and element_data.members:
        for member_type, member_ref, member_role in element_data.members:
            member = ET.SubElement(elem, 'member')
            member.set('type', member_type)
            member.set('ref', str(member_ref))
            member.set('role', member_role)
    
    # Add tags
    for key, value in sorted(element_data.tags.items()):
        tag = ET.SubElement(elem, 'tag')
        tag.set('k', key)
        tag.set('v', value)
    
    return elem


def generate_osc(original_reader, modified_reader, output_file):
    """Generate OSC file from differences between two PBF files."""
    
    # Find created elements (in modified but not in original)
    created_nodes = {k: v for k, v in modified_reader.nodes.items() 
                     if k not in original_reader.nodes}
    created_ways = {k: v for k, v in modified_reader.ways.items() 
                    if k not in original_reader.ways}
    created_relations = {k: v for k, v in modified_reader.relations.items() 
                         if k not in original_reader.relations}
    
    # Find deleted elements (in original but not in modified)
    deleted_nodes = {k: v for k, v in original_reader.nodes.items() 
                     if k not in modified_reader.nodes}
    deleted_ways = {k: v for k, v in original_reader.ways.items() 
                    if k not in modified_reader.ways}
    deleted_relations = {k: v for k, v in original_reader.relations.items() 
                          if k not in modified_reader.relations}
    
    # Find modified elements (same ID but different content)
    modified_nodes = {}
    for node_id in set(original_reader.nodes.keys()) & set(modified_reader.nodes.keys()):
        orig = original_reader.nodes[node_id]
        mod = modified_reader.nodes[node_id]
        if mod.is_modified(orig):
            modified_nodes[node_id] = mod
    
    modified_ways = {}
    for way_id in set(original_reader.ways.keys()) & set(modified_reader.ways.keys()):
        orig = original_reader.ways[way_id]
        mod = modified_reader.ways[way_id]
        if mod.is_modified(orig):
            modified_ways[way_id] = mod
    
    modified_relations = {}
    for rel_id in set(original_reader.relations.keys()) & set(modified_reader.relations.keys()):
        orig = original_reader.relations[rel_id]
        mod = modified_reader.relations[rel_id]
        if mod.is_modified(orig):
            modified_relations[rel_id] = mod
    
    # Create OSC XML structure
    osm_change = ET.Element('osmChange')
    osm_change.set('version', '0.6')
    osm_change.set('generator', 'generate_osc_from_diff.py')
    
    # Create section
    if created_nodes or created_ways or created_relations:
        create_elem = ET.SubElement(osm_change, 'create')
        for node_data in sorted(created_nodes.values(), key=lambda x: x.id):
            create_elem.append(create_osm_element_xml(node_data, 'node'))
        for way_data in sorted(created_ways.values(), key=lambda x: x.id):
            create_elem.append(create_osm_element_xml(way_data, 'way'))
        for rel_data in sorted(created_relations.values(), key=lambda x: x.id):
            create_elem.append(create_osm_element_xml(rel_data, 'relation'))
    
    # Modify section
    if modified_nodes or modified_ways or modified_relations:
        modify_elem = ET.SubElement(osm_change, 'modify')
        for node_data in sorted(modified_nodes.values(), key=lambda x: x.id):
            modify_elem.append(create_osm_element_xml(node_data, 'node'))
        for way_data in sorted(modified_ways.values(), key=lambda x: x.id):
            modify_elem.append(create_osm_element_xml(way_data, 'way'))
        for rel_data in sorted(modified_relations.values(), key=lambda x: x.id):
            modify_elem.append(create_osm_element_xml(rel_data, 'relation'))
    
    # Delete section
    if deleted_nodes or deleted_ways or deleted_relations:
        delete_elem = ET.SubElement(osm_change, 'delete')
        for node_data in sorted(deleted_nodes.values(), key=lambda x: x.id):
            delete_elem.append(create_osm_element_xml(node_data, 'node'))
        for way_data in sorted(deleted_ways.values(), key=lambda x: x.id):
            delete_elem.append(create_osm_element_xml(way_data, 'way'))
        for rel_data in sorted(deleted_relations.values(), key=lambda x: x.id):
            delete_elem.append(create_osm_element_xml(rel_data, 'relation'))
    
    # Write to file
    tree = ET.ElementTree(osm_change)
    
    # Pretty print the XML
    xml_str = ET.tostring(osm_change, encoding='unicode')
    dom = minidom.parseString(xml_str)
    pretty_xml = dom.toprettyxml(indent='  ', encoding='UTF-8')
    
    with open(output_file, 'wb') as f:
        # Remove the XML declaration line added by minidom and add our own
        lines = pretty_xml.decode('utf-8').split('\n')
        # Remove empty lines and the default XML declaration
        lines = [line for line in lines if line.strip()]
        if lines[0].startswith('<?xml'):
            lines[0] = "<?xml version='1.0' encoding='UTF-8'?>"
        else:
            lines.insert(0, "<?xml version='1.0' encoding='UTF-8'?>")
        f.write('\n'.join(lines).encode('utf-8'))
    
    # Log statistics
    logging.info("OSC file generation complete!")
    logging.info(f"Created: {len(created_nodes)} nodes, {len(created_ways)} ways, {len(created_relations)} relations")
    logging.info(f"Modified: {len(modified_nodes)} nodes, {len(modified_ways)} ways, {len(modified_relations)} relations")
    logging.info(f"Deleted: {len(deleted_nodes)} nodes, {len(deleted_ways)} ways, {len(deleted_relations)} relations")
    logging.info(f"Output written to: {output_file}")


def main():
    if len(sys.argv) != 4:
        print("Usage: python generate_osc_from_diff.py original.pbf modified.pbf output.osc")
        print("\nThis script compares two OSM PBF files and generates an OSC change file.")
        print("The OSC file will contain create, modify, and delete operations for")
        print("all differences between the original and modified files.")
        print("\nNote: Version numbers may not change, but the script detects changes")
        print("in tags, locations (for nodes), node references (for ways), and members (for relations).")
        sys.exit(1)
    
    original_file = sys.argv[1]
    modified_file = sys.argv[2]
    output_file = sys.argv[3]
    
    # Validate input files exist
    import os
    if not os.path.exists(original_file):
        logging.error(f"Original PBF file not found: {original_file}")
        sys.exit(1)
    
    if not os.path.exists(modified_file):
        logging.error(f"Modified PBF file not found: {modified_file}")
        sys.exit(1)
    
    logging.info(f"Reading original PBF file: {original_file}")
    original_reader = PBFReader()
    try:
        original_reader.apply_file(original_file, locations=True)
    except Exception as e:
        logging.error(f"Error reading original PBF file: {e}")
        sys.exit(1)
    
    logging.info(f"  Loaded {len(original_reader.nodes)} nodes, "
                 f"{len(original_reader.ways)} ways, "
                 f"{len(original_reader.relations)} relations")
    
    logging.info(f"Reading modified PBF file: {modified_file}")
    modified_reader = PBFReader()
    try:
        modified_reader.apply_file(modified_file, locations=True)
    except Exception as e:
        logging.error(f"Error reading modified PBF file: {e}")
        sys.exit(1)
    
    logging.info(f"  Loaded {len(modified_reader.nodes)} nodes, "
                 f"{len(modified_reader.ways)} ways, "
                 f"{len(modified_reader.relations)} relations")
    
    logging.info("Comparing files and generating OSC...")
    try:
        generate_osc(original_reader, modified_reader, output_file)
    except Exception as e:
        logging.error(f"Error generating OSC file: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

