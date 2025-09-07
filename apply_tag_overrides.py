import osmium
import sys
import json
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)

WAY_TAG_OVERRIDES = {}
NODE_TAG_OVERRIDES = {}
ALL_TARGET_WAY_IDS = set()
ALL_TARGET_NODE_IDS = set()
FOUND_WAY_IDS = set()
FOUND_NODE_IDS = set()
MODIFIED_WAYS_COUNT = 0
MODIFIED_NODES_COUNT = 0
TOTAL_WAYS = 0
TOTAL_NODES = 0

def load_override_config(json_path):
    global WAY_TAG_OVERRIDES, NODE_TAG_OVERRIDES, ALL_TARGET_WAY_IDS, ALL_TARGET_NODE_IDS

    with open(json_path, 'r', encoding='utf-8') as f:
        override_groups = json.load(f)

    for group in override_groups:
        way_ids = group.get("way_ids", [])
        node_ids = group.get("node_ids", [])
        tags = group.get("tags", {})
        
        for way_id in way_ids:
            WAY_TAG_OVERRIDES[way_id] = tags
            ALL_TARGET_WAY_IDS.add(way_id)
            
        for node_id in node_ids:
            NODE_TAG_OVERRIDES[node_id] = tags
            ALL_TARGET_NODE_IDS.add(node_id)

class OsmModifier(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.writer = None

    def apply_writer(self, writer):
        self.writer = writer

    def way(self, w):
        global MODIFIED_WAYS_COUNT, TOTAL_WAYS, FOUND_WAY_IDS
    
        TOTAL_WAYS += 1
        if w.id in WAY_TAG_OVERRIDES:
            FOUND_WAY_IDS.add(w.id)
            override_tags = WAY_TAG_OVERRIDES[w.id]
    
            # Start with original tags
            tags_dict = dict(w.tags)
            tags_dict.update(override_tags)
    
            # Create a new mutable way and set updated tags
            new_way = osmium.osm.mutable.Way(w)
            new_way.tags = [(k, v) for k, v in tags_dict.items()]
    
            self.writer.add_way(new_way)
            MODIFIED_WAYS_COUNT += 1
            logging.debug(f"Modified way_id={w.id} with tags {override_tags}")
        else:
            self.writer.add_way(w)

    def node(self, n):
        global MODIFIED_NODES_COUNT, TOTAL_NODES, FOUND_NODE_IDS
        
        TOTAL_NODES += 1
        if n.id in NODE_TAG_OVERRIDES:
            FOUND_NODE_IDS.add(n.id)
            override_tags = NODE_TAG_OVERRIDES[n.id]
    
            # Start with original tags
            tags_dict = dict(n.tags)
            tags_dict.update(override_tags)
    
            # Create a new mutable node and set updated tags
            new_node = osmium.osm.mutable.Node(n)
            new_node.tags = [(k, v) for k, v in tags_dict.items()]
    
            self.writer.add_node(new_node)
            MODIFIED_NODES_COUNT += 1
            logging.debug(f"Modified node_id={n.id} with tags {override_tags}")
        else:
            self.writer.add_node(n)

    def relation(self, r):
        self.writer.add_relation(r)

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python apply_tag_overrides.py input.pbf output.pbf tag_overrides.json")
        print("Note: tag_overrides.json can contain both 'way_ids' and 'node_ids' arrays for overriding tags")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]
    config_file = sys.argv[3]

    load_override_config(config_file)

    handler = OsmModifier()
    writer = osmium.SimpleWriter(output_file)

    logging.info(f"Processing input file: {input_file}")
    logging.info(f"Output will be written to: {output_file}")
    logging.info(f"Loaded tag overrides from: {config_file}")
    logging.info(f"Total target way_ids: {len(ALL_TARGET_WAY_IDS)}")
    logging.info(f"Total target node_ids: {len(ALL_TARGET_NODE_IDS)}")

    try:
        handler.apply_writer(writer)
        handler.apply_file(input_file, locations=False)
    finally:
        writer.close()

    MISSING_WAY_IDS = ALL_TARGET_WAY_IDS - FOUND_WAY_IDS
    MISSING_NODE_IDS = ALL_TARGET_NODE_IDS - FOUND_NODE_IDS
    
    logging.info(f"Total ways processed: {TOTAL_WAYS}")
    logging.info(f"Total ways modified: {MODIFIED_WAYS_COUNT}")
    logging.info(f"Total nodes processed: {TOTAL_NODES}")
    logging.info(f"Total nodes modified: {MODIFIED_NODES_COUNT}")
    
    if MISSING_WAY_IDS:
        logging.warning(f"{len(MISSING_WAY_IDS)} way_ids from config not found in input PBF:")
        for wid in sorted(MISSING_WAY_IDS):
            logging.warning(f"  Missing way_id: {wid}")
    else:
        logging.info("All target way_ids were found and modified.")
        
    if MISSING_NODE_IDS:
        logging.warning(f"{len(MISSING_NODE_IDS)} node_ids from config not found in input PBF:")
        for nid in sorted(MISSING_NODE_IDS):
            logging.warning(f"  Missing node_id: {nid}")
    else:
        logging.info("All target node_ids were found and modified.")
