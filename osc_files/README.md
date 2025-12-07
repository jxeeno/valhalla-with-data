# Change Files Directory

This directory contains OSM change files (.osc, .osm, .opl) that will be applied to the OSM extract during the build process.

## Supported File Formats

- **.osc files** - OpenStreetMap Change files (XML format with create/modify/delete operations)
- **.osm files** - Full OSM data files (XML format with complete OSM elements)
- **.opl files** - OSM Protocol format (compact text-based format)

## How to Use

### Exporting Change Files from JOSM

1. **Open JOSM** and load the area you want to edit
   - File → Download from OSM
   - Or open an existing OSM file

2. **Make your edits**:
   - Add new nodes, ways, or relations
   - Modify existing elements (tags, geometry)
   - Delete elements if needed

3. **Export your changes** (choose one format):
   - **As OSC**: File → Export → Export as OSM Change File (.osc)
   - **As OSM**: File → Export → Export as OSM XML (.osm)
   - **As OPL**: File → Export → Export as OPL (.opl)
   - Save the file to this directory (`osc_files/`)

4. **Naming convention**:
   - Files are processed in **alphabetical order** (all formats together)
   - Use numeric prefixes if order matters:
     - `01_highway_fixes.osc`
     - `02_roundabout_updates.osm`
     - `03_poi_additions.opl`
   - Use descriptive names for clarity

### Example OSC File Structure

OSC files are XML format and look like this:

```xml
<?xml version='1.0' encoding='UTF-8'?>
<osmChange version="0.6" generator="JOSM">
  <modify>
    <way id="123456" version="2" timestamp="2024-01-01T00:00:00Z">
      <nd ref="111"/>
      <nd ref="222"/>
      <tag k="highway" v="primary"/>
      <tag k="name" v="Main Street"/>
    </way>
  </modify>
  <create>
    <node id="-1" version="1" lat="-27.4698" lon="153.0251">
      <tag k="amenity" v="restaurant"/>
      <tag k="name" v="New Restaurant"/>
    </node>
  </create>
  <delete>
    <way id="999999" version="1"/>
  </delete>
</osmChange>
```

### Processing Order

- Change files are applied **before** tag overrides from `modifications.json`
- All file types (.osc, .osm, .opl) are processed together in alphabetical order
- Each file is applied sequentially to the OSM extract
- **.osc files**: Use `osmium apply-changes` (applies create/modify/delete operations)
- **.osm and .opl files**: Use `osmium merge` (merges data, may create duplicates if elements exist)
- If multiple files modify the same element, later files (alphabetically) will override earlier changes

### Best Practices

1. **Test locally first**: Apply your change files locally before committing
2. **Use descriptive names**: Make it clear what each file contains
3. **Keep files focused**: One file per logical set of changes
4. **Choose the right format**:
   - Use `.osc` for incremental changes (create/modify/delete operations)
   - Use `.osm` or `.opl` for adding complete new data or bulk imports
5. **Document changes**: Add comments or notes about what each file does
6. **Version control**: Commit change files to git so changes are tracked

### Troubleshooting

- **Change files not applied**: 
  - Check that files have `.osc`, `.osm`, or `.opl` extension
  - Verify `osmium-tool` is installed: `osmium --version`
- **Changes not reflected**: 
  - Verify the OSM element IDs exist in your extract
  - For .osm/.opl files, elements are merged (not replaced) - check for conflicts
- **Build fails**: Check the build logs for specific errors about change file processing
- **Duplicate elements**: .osm and .opl files merge data, which may create duplicates if elements already exist

