# P4 Data Sources and Processing

## Current Data Status

The current AVASYA MVP uses synthetic demo datasets stored in `data/raw/`. These records are not government data and are not claimed to be derived from government sources. Every generated evidence record is labelled:

* `data_source: SYNTHETIC_DEMO`
* `data_quality: SYNTHETIC_DEMO`

The files are structured so that appropriately licensed real datasets can replace them later without changing the habitation evidence interface.

## Datasets Used by the Pipeline

### 1. `habitations.geojson`

* **Purpose:** Defines the habitation polygons and their identity, name, and district.
* **Source:** Synthetic demo geometry created for the AVASYA MVP.
* **Status:** `SYNTHETIC_DEMO`, not real government data.
* **CRS:** EPSG:4326 (WGS84).
* **Main fields used:** `habitation_id`, `name`, `district`, `geometry`, and `data_source`.
* **Technique applied:** GeoPandas loading, required-field and geometry validation, geometry repair where possible, CRS normalization, projected centroid calculation.
* **Evidence produced:** `habitation_id`, `name`, `district`, and output `geometry` as a WGS84 GeoJSON Point.

### 2. `hazards.geojson`

* **Purpose:** Represents hazard polygons used to estimate the portion of each habitation affected by a hazard.
* **Source:** Synthetic demo hazard polygons created for the AVASYA MVP.
* **Status:** `SYNTHETIC_DEMO`, not real government data.
* **CRS:** EPSG:4326 (WGS84).
* **Main fields used:** `geometry`; hazard properties are retained as source metadata.
* **Technique applied:** Geometry validation, CRS normalization, reprojection to projected CRS EPSG:32643 for area measurement, hazard union, and habitation-hazard spatial intersection.
* **Evidence produced:** `hazard_exposure`, calculated as intersection area divided by habitation area, clamped to `[0, 1]`.

### 3. `roads.geojson`

* **Purpose:** Represents road segments used to estimate access from each habitation to the nearest road.
* **Source:** Synthetic demo road network created for the AVASYA MVP.
* **Status:** `SYNTHETIC_DEMO`, not real government data.
* **CRS:** EPSG:4326 (WGS84).
* **Main fields used:** `geometry`; `road_id`, `road_type`, and source metadata identify the demo road records. The accessibility score is derived from distance in the current pipeline.
* **Technique applied:** Reprojection to EPSG:32643, nearest-geometry distance calculation in metres, conversion to kilometres, and inverse-distance normalization.
* **Evidence produced:** `nearest_road_distance_km` and `road_accessibility`, where closer roads receive higher scores in `[0, 1]`.

### 4. `roads_thanjavur_overpass.geojson` (optional real-data replacement)

* **Purpose:** Provides mapped road ways for the Thanjavur district area when the pipeline is run with `--fetch-real-roads`.
* **Source:** OpenStreetMap contributors, retrieved through the Overpass API endpoint `https://overpass-api.de/api/interpreter`.
* **Status:** Real volunteered geographic data; not government data. Each feature is labelled `data_source: OpenStreetMap Overpass API`.
* **CRS:** EPSG:4326 (WGS84).
* **Main fields used:** `geometry`, `road_id`, and `road_type`.
* **Fallback:** Without `--fetch-real-roads`, the pipeline continues to use `roads.geojson` with `SYNTHETIC_DEMO` records.

### 5. `hospitals.geojson`

* **Purpose:** Represents hospital locations used to estimate the nearest hospital distance for each habitation.
* **Source:** Synthetic demo hospital points created for the AVASYA MVP.
* **Status:** `SYNTHETIC_DEMO`, not real government data.
* **CRS:** EPSG:4326 (WGS84).
* **Main fields used:** `geometry`, `hospital_id`, and hospital metadata.
* **Technique applied:** Reprojection to EPSG:32643 and nearest-point distance calculation in metres, converted to kilometres.
* **Evidence produced:** `hospital_distance_km`.

### 6. `relief_centers.geojson`

* **Purpose:** Represents relief-centre locations and supporting capacity information for habitation-level emergency evidence.
* **Source:** Synthetic demo relief-centre points created for the AVASYA MVP.
* **Status:** `SYNTHETIC_DEMO`, not real government data.
* **CRS:** EPSG:4326 (WGS84).
* **Main fields used:** `geometry`, `center_id`, `capacity`, and `water_available`.
* **Technique applied:** Reprojection to EPSG:32643, nearest-centre distance calculation, and nearest-record attribute lookup.
* **Evidence produced:** `nearest_relief_center_id`, `nearest_relief_center_distance_km`, `nearest_relief_center_capacity`, and `nearest_relief_center_water_available`.

### 7. `population.csv`

* **Purpose:** Provides habitation-level population and vulnerability attributes.
* **Source:** Synthetic demo tabular records created for the AVASYA MVP.
* **Status:** `SYNTHETIC_DEMO`, not real Census data.
* **CRS:** Not applicable; this is a tabular file keyed by `habitation_id`.
* **Main fields used:** `habitation_id`, `population`, `vulnerability`, and `data_source`.
* **Technique applied:** CSV loading, numeric conversion, one-to-one join to habitation records, and population validation.
* **Evidence produced:** `population` and `vulnerability`.

### 8. `historical_events.csv`

* **Purpose:** Records prior hazard events associated with each habitation.
* **Source:** Synthetic demo event history created for the AVASYA MVP.
* **Status:** `SYNTHETIC_DEMO`, not real historical government records.
* **CRS:** Not applicable; this is a tabular file keyed by `habitation_id`.
* **Main fields used:** `event_id`, `habitation_id`, `event_type`, `event_year`, `severity`, and `data_source`.
* **Technique applied:** CSV loading, required-column validation, grouping by `habitation_id`, and event-count aggregation. Event history is supporting evidence only.
* **Evidence produced:** `historical_events`.

## P4 Processing Pipeline

```text
Raw data
-> Validation
-> Cleaning
-> CRS normalization
-> Population/event integration
-> Hazard spatial intersection
-> Hazard exposure
-> Population exposed
-> Road distance/accessibility
-> Hospital distance
-> Relief-centre analysis
-> Habitation evidence JSON
```

The pipeline writes `data/habitation_evidence.json`. It calculates `population_exposed` internally as `population * hazard_exposure` and exports it as evidence. P4 does not calculate the final disaster risk score, priority classification, capacity decision, or relocation recommendation.

## Intended Real-Data Sources

The following are potential future sources only. They are not currently loaded by the MVP:

* **NDEM / NRSC:** disaster-management and hazard reference layers.
* **Bhuvan / ISRO / NRSC:** satellite imagery, terrain, land use, and thematic geospatial layers.
* **IMD:** rainfall, weather observations, forecasts, and climate indicators.
* **CWC:** river, flood, water-level, and hydrological information.
* **GSI:** geological and landslide susceptibility information.
* **OpenStreetMap (OSM):** roads, hospitals, amenities, and other mapped infrastructure.
* **Census of India:** population, household, demographic, and settlement information.

Before integrating real data, each source requires licensing review, coverage and date checks, schema mapping, CRS verification, provenance metadata, and quality validation. No current output should be interpreted as official government data.
