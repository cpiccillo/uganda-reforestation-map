"""
The Trees Project (Uganda) - PyQGIS | Carlo Piccillo
Processing tool (GUI): the same pipeline as build_trees_dataset, exposed as a
QGIS Processing algorithm with parameters - source CSV, a minimum-trees filter
for the Atlas, and optional elevation sampling from a DEM.
"""

from qgis.core import (QgsProcessingAlgorithm,
                       QgsProcessingParameterFile,
                       QgsProcessingParameterNumber,
                       QgsProcessingParameterRasterLayer,
                       QgsProcessingException,
                       QgsVectorLayer, QgsVectorFileWriter, QgsProject,
                       QgsField, QgsCoordinateTransformContext,
                       QgsCoordinateTransform, QgsRaster,
                       QgsApplication, QgsProcessingProvider)
from qgis.PyQt.QtCore import QVariant

# Set BASE to the folder where the output GeoPackage should be written.
BASE = "path/to/data/"
GPKG_PATH = BASE + "trees_atlas.gpkg"
GPKG_LAYER = "trees_atlas"

# Single source of truth for species: raw CSV column -> clean display name.
SPECIES_CLEAN = {
    "Teak": "Teak", "Eucaliptus": "Eucalyptus", "Gravelia": "Grevillea",
    "White Teak": "White Teak", "Pines": "Pines", "Mahogany": "Mahogany",
    "Jerk Fruit": "Jackfruit", "Oranges": "Oranges", "Mangoes": "Mangoes",
    "Sour soup": "Soursop", "Cocoa": "Cocoa",
}
SPECIES_FIELDS = list(SPECIES_CLEAN.keys())


class BuildTreesDataset(QgsProcessingAlgorithm):

    INPUT_CSV = 'INPUT_CSV'
    THRESHOLD = 'THRESHOLD'
    DEM = 'DEM'

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(
            self.INPUT_CSV, 'Source CSV (trees dataset)', extension='csv'))
        self.addParameter(QgsProcessingParameterNumber(
            self.THRESHOLD, 'Minimum total trees (Atlas filter)', defaultValue=500))
        self.addParameter(QgsProcessingParameterRasterLayer(
            self.DEM, 'DEM for elevation (optional)', optional=True))

    def processAlgorithm(self, parameters, context, feedback):
        csv_path = self.parameterAsFile(parameters, self.INPUT_CSV, context)
        threshold = self.parameterAsInt(parameters, self.THRESHOLD, context)
        dem = self.parameterAsRasterLayer(parameters, self.DEM, context)
        feedback.pushInfo(f"CSV: {csv_path} | threshold: {threshold} | DEM: {'yes' if dem else 'no'}")

        # --- 1. LOAD CSV AS POINT LAYER ------------------------------------
        uri = f"file:///{csv_path}?delimiter=,&xField=gps_lon&yField=gps_lat&crs=EPSG:4326"
        csv_layer = QgsVectorLayer(uri, "trees_csv", "delimitedtext")
        if not csv_layer.isValid():
            raise QgsProcessingException("CSV failed to load. Check path/columns.")
        feedback.pushInfo(f"CSV loaded: {csv_layer.featureCount()} features")

        # --- 2. SAVE AS GEOPACKAGE (overwrite) -----------------------------
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "GPKG"
        options.layerName = GPKG_LAYER
        options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile
        QgsVectorFileWriter.writeAsVectorFormatV3(
            csv_layer, GPKG_PATH, QgsCoordinateTransformContext(), options)

        layer = QgsVectorLayer(f"{GPKG_PATH}|layername={GPKG_LAYER}", GPKG_LAYER, "ogr")
        if not layer.isValid():
            raise QgsProcessingException("GeoPackage layer failed to load.")

        # --- 3. CREATE ANALYSIS FIELDS -------------------------------------
        new_fields = [
            QgsField("n_species", QVariant.Int),
            QgsField("max_trees", QVariant.Int),
            QgsField("total_trees", QVariant.Int),
            QgsField("dominant_species", QVariant.String, len=30),
            QgsField("cultivation", QVariant.String, len=15),
            QgsField("elevation", QVariant.Double),
        ]
        existing = [f.name() for f in layer.fields()]
        layer.startEditing()
        for fld in new_fields:
            if fld.name() not in existing:
                layer.addAttribute(fld)
        layer.updateFields()

        # Column names actually present in the working layer.
        field_names = set(layer.fields().names())

        # Read a species value as an integer. A missing column or an empty value
        # both count as 0, so a CSV that lacks a species still runs without error.
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

        # Prepare DEM sampling (transform points into DEM CRS, sample band 1)
        if dem is not None:
            dem_provider = dem.dataProvider()
            to_dem = QgsCoordinateTransform(layer.crs(), dem.crs(), QgsProject.instance())

        # --- 4. CALCULATE + COLLECT IDs BELOW THRESHOLD --------------------
        to_delete = []
        for feat in layer.getFeatures():
            counts = {f: val(feat, f) for f in SPECIES_FIELDS}
            n_species = sum(1 for c in counts.values() if c > 0)
            max_trees = max(counts.values()) if counts else 0
            total_trees = sum(counts.values())
            dominant = SPECIES_CLEAN[max(counts, key=counts.get)] if max_trees > 0 else None

            if n_species == 1:
                cultivation = "Monoculture"
            elif n_species > 1:
                cultivation = "Polyculture"
            else:
                cultivation = None

            feat["n_species"] = n_species
            feat["max_trees"] = max_trees
            feat["total_trees"] = total_trees
            feat["dominant_species"] = dominant
            feat["cultivation"] = cultivation

            # Optional elevation
            if dem is not None:
                pt = to_dem.transform(feat.geometry().asPoint())
                res = dem_provider.identify(pt, QgsRaster.IdentifyFormatValue).results()
                elev = res.get(1)
                if elev is None or elev < -1000:   # nodata guard
                    feat["elevation"] = None
                else:
                    feat["elevation"] = round(float(elev), 1)

            layer.updateFeature(feat)

            if total_trees < threshold:
                to_delete.append(feat.id())

        # --- 5. APPLY THE FILTER -------------------------------------------
        if to_delete:
            layer.deleteFeatures(to_delete)
        layer.commitChanges()
        feedback.pushInfo(f"Kept {layer.featureCount()} sites with total_trees >= {threshold}")

        # --- 6. ADD TO PROJECT ---------------------------------------------
        for lyr in QgsProject.instance().mapLayersByName(GPKG_LAYER):
            QgsProject.instance().removeMapLayer(lyr)
        QgsProject.instance().addMapLayer(layer)

        return {}

    def name(self):
        return 'build_trees_dataset'

    def displayName(self):
        return 'Build Trees Dataset'

    def group(self):
        return 'The Trees Project'

    def groupId(self):
        return 'trees_project'

    def createInstance(self):
        return BuildTreesDataset()


# --- REGISTER (re-runnable) -------------------------------------------------
class TreesProjectProvider(QgsProcessingProvider):
    def loadAlgorithms(self):
        self.addAlgorithm(BuildTreesDataset())
    def id(self):
        return 'trees_project'
    def name(self):
        return 'The Trees Project'


reg = QgsApplication.processingRegistry()
existing = reg.providerById('trees_project')
if existing is not None:
    reg.removeProvider(existing)
reg.addProvider(TreesProjectProvider())

print("Provider registered. Open: The Trees Project > Build Trees Dataset.")
