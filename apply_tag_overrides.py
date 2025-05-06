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
ALL_TARGET_IDS = set()
FOUND_IDS = set()
MODIFIED_COUNT = 0
TOTAL_WAYS = 0

def load_override_config(json_path):
    global WAY_TAG_OVERRIDES, ALL_TARGET_IDS

    with open(json_path, 'r', encoding='utf-8') as f:
        override_groups = json.load(f)

    for group in override_groups:
        way_ids = group.get("way_ids", [])
        tags = group.get("tags", {})
        for way_id in way_ids:
            WAY_TAG_OVERRIDES[way_id] = tags
            ALL_TARGET_IDS.add(way_id)

class WayModifier(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.writer = None

    def apply_writer(self, writer):
        self.writer = writer

    def way(self, w):
        global MODIFIED_COUNT, TOTAL_WAYS
    
        TOTAL_WAYS += 1
        if w.id in WAY_TAG_OVERRIDES:
            FOUND_IDS.add(w.id)
            override_tags = WAY_TAG_OVERRIDES[w.id]
    
            # Start with original tags
            tags_dict = dict(w.tags)
            tags_dict.update(override_tags)
    
            # Create a new mutable way and set updated tags
            new_way = osmium.osm.mutable.Way(w)
            new_way.tags = [(k, v) for k, v in tags_dict.items()]
    
            self.writer.add_way(new_way)
            MODIFIED_COUNT += 1
            logging.debug(f"Modified way_id={w.id} with tags {override_tags}")
        else:
            self.writer.add_way(w)

    def node(self, n):
        self.writer.add_node(n)

    def relation(self, r):
        self.writer.add_relation(r)

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python apply_tag_overrides.py input.pbf output.pbf tag_overrides.json")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]
    config_file = sys.argv[3]

    load_override_config(config_file)

    handler = WayModifier()
    writer = osmium.SimpleWriter(output_file)

    logging.info(f"Processing input file: {input_file}")
    logging.info(f"Output will be written to: {output_file}")
    logging.info(f"Loaded tag overrides from: {config_file}")
    logging.info(f"Total target way_ids: {len(ALL_TARGET_IDS)}")

    try:
        handler.apply_writer(writer)
        handler.apply_file(input_file, locations=False)
    finally:
        writer.close()

    MISSING_IDS = ALL_TARGET_IDS - FOUND_IDS
    logging.info(f"Total ways processed: {TOTAL_WAYS}")
    logging.info(f"Total ways modified: {MODIFIED_COUNT}")
    if MISSING_IDS:
        logging.warning(f"{len(MISSING_IDS)} way_ids from config not found in input PBF:")
        for wid in sorted(MISSING_IDS):
            logging.warning(f"  Missing way_id: {wid}")
    else:
        logging.info("All target way_ids were found and modified.")
