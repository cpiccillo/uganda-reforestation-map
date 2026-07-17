"""
The Trees Project (Uganda) - PyQGIS automation - Carlo Piccillo
EXPANSION MAP: load the May 2026 dataset (current full state) -> tag each site as
"Existing" (coordinates already present in Nov 2025) or "New" -> save as a
GeoPackage with the usual analysis fields + site_status -> add to the project.

Honest temporal comparison: one layer, the current project state, coloured by
when each site first appeared. This is the "expansion map", not a survival rate.
"""

from qgis.core import (QgsVectorLayer, QgsVectorFileWriter, QgsProject,
                       QgsField, QgsCoordinateTransformContext)
from qgis.PyQt.QtCore import QVariant

# --- 1. PARAMETERS ---
# Set BASE to the folder that holds both datasets.
BASE = "path/to/data/"
nov_csv = BASE + "Green Project Dataset Nov 2025.xlsx - Sheet1.csv"
may_csv = BASE + "Green Project Dataset May 2026.xlsx - Sheet1.csv"
gpkg_path = BASE + "trees_expansion.gpkg"
gpkg_layer_name = "trees_expansion"

# Coordinate rounding used to match Nov vs May sites (6 decimals ~ 0.1 m)
COORD_PRECISION = 6

# Single source of truth for species: raw CSV column -> clean display name.
species_clean = {
    "Teak": "Teak", "Eucaliptus": "Eucalyptus", "Gravelia": "Grevillea",
    "White Teak": "White Teak", "Pines": "Pines", "Mahogany": "Mahogany",
    "Jerk Fruit": "Jackfruit", "Oranges": "Oranges", "Mangoes": "Mangoes",
    "Sour soup": "Soursop", "Cocoa": "Cocoa",
}
species_fields = list(species_clean.keys())

# --- 2. BUILD THE SET OF NOVEMBER COORDINATES ---
# We load Nov only to learn which coordinates already existed.
nov_uri = f"file:///{nov_csv}?delimiter=,&xField=gps_lon&yField=gps_lat&crs=EPSG:4326"
nov_layer = QgsVectorLayer(nov_uri, "nov_tmp", "delimitedtext")
if not nov_layer.isValid():
    raise Exception("Nov CSV failed to load. Check path and column names.")

def coord_key(feat):
    try:
        return (round(float(feat["gps_lat"]), COORD_PRECISION),
                round(float(feat["gps_lon"]), COORD_PRECISION))
    except (TypeError, ValueError):
        return None

nov_keys = set(filter(None, (coord_key(f) for f in nov_layer.getFeatures())))
print("November coordinate keys:", len(nov_keys))

# --- 3. LOAD MAY CSV AS POINT LAYER (current full state) ---
may_uri = f"file:///{may_csv}?delimiter=,&xField=gps_lon&yField=gps_lat&crs=EPSG:4326"
may_layer = QgsVectorLayer(may_uri, "may_tmp", "delimitedtext")
if not may_layer.isValid():
    raise Exception("May CSV failed to load. Check path and column names.")
print("May loaded:", may_layer.featureCount(), "features")

# --- 4. SAVE AS GEOPACKAGE (writable, overwrites existing) ---
options = QgsVectorFileWriter.SaveVectorOptions()
options.driverName = "GPKG"
options.layerName = gpkg_layer_name
options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile
QgsVectorFileWriter.writeAsVectorFormatV3(
    may_layer, gpkg_path, QgsCoordinateTransformContext(), options)
print("GeoPackage written:", gpkg_path)

layer = QgsVectorLayer(f"{gpkg_path}|layername={gpkg_layer_name}", gpkg_layer_name, "ogr")
if not layer.isValid():
    raise Exception("GeoPackage layer failed to load.")

# --- 5. CREATE ANALYSIS FIELDS + site_status ---
new_fields = [
    QgsField("n_species", QVariant.Int),
    QgsField("max_trees", QVariant.Int),
    QgsField("dominant_species", QVariant.String, len=30),
    QgsField("cultivation", QVariant.String, len=15),
    QgsField("site_status", QVariant.String, len=10),   # "New" / "Existing"
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
# count as 0, so a CSV that lacks a species still runs without error.
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

# --- 6. CALCULATE FIELD VALUES ---
for feat in layer.getFeatures():
    counts = {f: val(feat, f) for f in species_fields}
    n_species = sum(1 for c in counts.values() if c > 0)
    max_trees = max(counts.values()) if counts else 0

    dominant = species_clean[max(counts, key=counts.get)] if max_trees > 0 else None

    if n_species == 1:
        cultivation = "Monoculture"
    elif n_species > 1:
        cultivation = "Polyculture"
    else:
        cultivation = None

    # site_status by coordinate match against November
    k = coord_key(feat)
    if k is None:
        status = None                      # row without valid coordinates
    elif k in nov_keys:
        status = "Existing"
    else:
        status = "New"

    feat["n_species"] = n_species
    feat["max_trees"] = max_trees
    feat["dominant_species"] = dominant
    feat["cultivation"] = cultivation
    feat["site_status"] = status
    layer.updateFeature(feat)

layer.commitChanges()

# --- 7. ADD TO PROJECT ---
for lyr in QgsProject.instance().mapLayersByName(gpkg_layer_name):
    QgsProject.instance().removeMapLayer(lyr)
QgsProject.instance().addMapLayer(layer)

# --- 8. SUMMARY ---
new = sum(1 for f in layer.getFeatures() if f["site_status"] == "New")
ex = sum(1 for f in layer.getFeatures() if f["site_status"] == "Existing")
none = sum(1 for f in layer.getFeatures() if f["site_status"] is None)
print(f"Done. {layer.featureCount()} features | New: {new} | Existing: {ex} | no coords: {none}")
