"""
The Trees Project (Uganda) - PyQGIS automation | Carlo Piccillo
End-to-end script: load the source CSV -> save it as a GeoPackage ->
create and calculate the analysis fields -> add the result to the QGIS project.
Re-run this whenever a new monitoring dataset arrives.
"""

from qgis.core import (QgsVectorLayer, QgsVectorFileWriter, QgsProject,
                       QgsField, QgsCoordinateTransformContext)
from qgis.PyQt.QtCore import QVariant

# --- 1. PARAMETERS ---------------------------------------------------------
# Set BASE to the folder that holds the dataset, then keep the file name below.
BASE = "path/to/data/"
csv_path = BASE + "Green Project Dataset May 2026.xlsx - Sheet1.csv"
gpkg_path = BASE + "trees_project.gpkg"
gpkg_layer_name = "trees"

# Single source of truth for species: raw CSV column -> clean display name.
# The raw spellings are intentional; they must match the CSV headers exactly.
species_clean = {
    "Teak": "Teak", "Eucaliptus": "Eucalyptus", "Gravelia": "Grevillea",
    "White Teak": "White Teak", "Pines": "Pines", "Mahogany": "Mahogany",
    "Jerk Fruit": "Jackfruit", "Oranges": "Oranges", "Mangoes": "Mangoes",
    "Sour soup": "Soursop", "Cocoa": "Cocoa",
}
species_fields = list(species_clean.keys())

# --- 2. LOAD CSV AS POINT LAYER --------------------------------------------
uri = f"file:///{csv_path}?delimiter=,&xField=gps_lon&yField=gps_lat&crs=EPSG:4326"
csv_layer = QgsVectorLayer(uri, "trees_csv", "delimitedtext")
if not csv_layer.isValid():
    raise Exception("CSV layer failed to load. Check the path and column names.")
print("CSV loaded:", csv_layer.featureCount(), "features")

# --- 3. SAVE AS GEOPACKAGE (writable, overwrites existing) ------------------
options = QgsVectorFileWriter.SaveVectorOptions()
options.driverName = "GPKG"
options.layerName = gpkg_layer_name
options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile
QgsVectorFileWriter.writeAsVectorFormatV3(
    csv_layer, gpkg_path, QgsCoordinateTransformContext(), options)
print("GeoPackage written:", gpkg_path)

# Load the GeoPackage layer back (this is the writable working layer)
layer = QgsVectorLayer(f"{gpkg_path}|layername={gpkg_layer_name}", gpkg_layer_name, "ogr")
if not layer.isValid():
    raise Exception("GeoPackage layer failed to load.")

# --- 4. CREATE ANALYSIS FIELDS ---------------------------------------------
new_fields = [
    QgsField("n_species", QVariant.Int),
    QgsField("max_trees", QVariant.Int),
    QgsField("dominant_species", QVariant.String, len=30),
    QgsField("cultivation", QVariant.String, len=15),
]
existing = [f.name() for f in layer.fields()]
layer.startEditing()
for fld in new_fields:
    if fld.name() not in existing:
        layer.addAttribute(fld)
layer.updateFields()

# Column names actually present in the working layer.
field_names = set(layer.fields().names())

# Read a species value as an integer. A missing column or an empty value both
# count as 0, so an older CSV that lacks a species (e.g. no "Cocoa") still runs.
def val(feat, field):
    if field not in field_names:
        return 0
    v = feat[field]
    if v is None or v == "":
        return 0
    try:
        return int(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return 0

# --- 5. CALCULATE FIELD VALUES ---------------------------------------------
for feat in layer.getFeatures():
    counts = {f: val(feat, f) for f in species_fields}
    n_species = sum(1 for c in counts.values() if c > 0)
    max_trees = max(counts.values()) if counts else 0

    if max_trees > 0:
        dominant = species_clean[max(counts, key=counts.get)]
    else:
        dominant = None

    if n_species == 1:
        cultivation = "Monoculture"
    elif n_species > 1:
        cultivation = "Polyculture"
    else:
        cultivation = None

    feat["n_species"] = n_species
    feat["max_trees"] = max_trees
    feat["dominant_species"] = dominant
    feat["cultivation"] = cultivation
    layer.updateFeature(feat)

layer.commitChanges()

# --- 6. ADD TO PROJECT ------------------------------------------------------
# Remove any existing layer with the same name first (avoid duplicates)
for lyr in QgsProject.instance().mapLayersByName(gpkg_layer_name):
    QgsProject.instance().removeMapLayer(lyr)
QgsProject.instance().addMapLayer(layer)

print("Done. Clean layer ready with", layer.featureCount(), "features.")
