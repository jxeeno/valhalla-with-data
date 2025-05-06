import osmium
import sys

OVERRIDE_GROUPS = [
    {
        "way_ids": [
          1135684894, 24210972, 511190501, 652167419, 836638129, 144053760,

          198994800, 198994809
        ],
        "tags": {"highway": "motorway_link", "name": ""}
    },
    {
        "way_ids": [11111111],
        "tags": {"access": "no"}
    }
]

# Build a map from way_id to tag overrides for fast lookup
WAY_TAG_OVERRIDES = {}
for group in OVERRIDE_GROUPS:
    for way_id in group["way_ids"]:
        WAY_TAG_OVERRIDES[way_id] = group["tags"]

class WayModifier(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.writer = None

    def apply_writer(self, writer):
        self.writer = writer

    def way(self, w):
        if w.id in WAY_TAG_OVERRIDES:
            tags_dict = dict(w.tags)
            override_tags = WAY_TAG_OVERRIDES[w.id]
            tags_dict.update(override_tags)

            # Build a new OSM way with overridden tags
            new_way = osmium.osm.mutable.Way(w)
            new_way.tags = osmium.osm.TagList()
            for k, v in tags_dict.items():
                new_way.tags.add(k, v)

            self.writer.add_way(new_way)
        else:
            self.writer.add_way(w)

    def node(self, n):
        self.writer.add_node(n)

    def relation(self, r):
        self.writer.add_relation(r)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python apply_tag_overrides.py input.pbf output.pbf")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    handler = WayModifier()
    writer = osmium.SimpleWriter(output_file)

    try:
        handler.apply_writer(writer)
        handler.apply_file(input_file, locations=False)
    finally:
        writer.close()
