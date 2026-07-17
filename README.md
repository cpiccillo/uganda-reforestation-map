# Uganda Reforestation Map - The Trees Project

An interactive web map of reforestation sites in northern Uganda, built from field-collected GPS data for the NGO **Amici di Angal OdV** and its *The Trees Project* initiative.

**[View the live map](https://cpiccillo.github.io/uganda-reforestation-map/)**

---

## About the project

*The Trees Project* is a reforestation initiative run by the Italian NGO **Amici di Angal OdV** in the West Nile region of northern Uganda. Local farmers receive tree seedlings and ongoing support, and each planting site is surveyed on the ground: location, species, tree counts, and management notes are recorded by a field officer using GPS.

This map turns that field data into something you can explore. Each point is a real planting site, with a pop-up showing the beneficiary, the village, the species breakdown, and the field officer's remarks. The goal is to make the project's footprint visible - to the NGO, to supporters, and to anyone curious about where the trees actually are.

The current dataset reflects the **May 2026** field survey.

## The data

The May 2026 survey covers:

- **132** planting sites (GPS-unique locations)
- **32,319** trees
- **11** tree species (Teak dominant, plus eucalyptus, grevillea, mahogany, fruit trees, and others)
- **7** sub-counties across the West Nile region

Each site carries its own attributes: beneficiary, village, sub-county, coordinates, per-species counts, cultivation type (monoculture / polyculture), and a management remark from the field.

## How it was built

The map is a static Leaflet site generated from a QGIS project:

- **Data preparation & cartography** - [QGIS](https://qgis.org), with sites styled by cultivation type and pop-ups built from per-species expressions.
- **Web export** - [qgis2web](https://github.com/tomchadwin/qgis2web), exporting the styled QGIS layers to a self-contained Leaflet map.
- **Basemaps** - Esri World Imagery (satellite) and OpenTopoMap, switchable by the user.
- **Hosting** - [GitHub Pages](https://pages.github.com), serving the static site directly from this repository.

Coordinate reference systems: source data in EPSG:4326 (WGS 84); web map in EPSG:3857 (Web Mercator).

## Automation (`pyqgis/`)

The map shows the *result*, but the data behind it doesn't clean itself. Every
survey arrives as a raw spreadsheet - one row per site, one column per species -
and turning that into analysis-ready spatial data by hand, every time, is slow
and easy to get wrong. So I automated it with PyQGIS.

The `pyqgis/` folder holds three scripts. Each one takes the raw CSV, writes a
clean GeoPackage, and derives the fields the map relies on (number of species,
dominant species, total trees, monoculture / polyculture):

- **`build_trees_dataset.py`** - the core script. CSV in, analysis-ready layer
  out. Re-run it whenever a new survey arrives.
- **`gui_build_trees.py`** - the same pipeline wrapped as a QGIS Processing tool,
  so it runs from a dialog: pick the CSV, set a minimum-trees threshold for the
  map series, optionally sample elevation from a DEM.
- **`build_expansion_map.py`** - compares two surveys (November 2025 and May
  2026) and tags each site as *Existing* or *New* by matching coordinates. An
  honest before/after of where the project grew - a map of expansion, not a
  survival rate.

## Repository contents

```
index.html        - the map page
data/             - site data (GeoJSON)
js/               - Leaflet and supporting libraries
css/              - styles and marker assets
legend/           - legend graphics
webfonts/         - icon fonts
pyqgis/       - PyQGIS automation scripts
```

## About me

I'm Carlo Piccillo, transitioning into GIS for the environmental and renewable-energy sector. I handle the technical/GIS side of *The Trees Project* as a volunteer, working with field data collected on the ground in Uganda.

[LinkedIn](https://www.linkedin.com/in/carlopiccillo)

---

*Data: Amici di Angal OdV - The Trees Project - Basemap: Esri World Imagery, OpenTopoMap*
