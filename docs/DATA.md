# Data sources and attribution

All inputs are free and open. Raw files are not committed. They are re-downloaded by [`uri/fetch.py`](../uri/fetch.py), [`uri/osm.py`](../uri/osm.py), [`uri/wbgt.py`](../uri/wbgt.py), [`uri/satellite.py`](../uri/satellite.py) and [`scripts/geocode_flood.py`](../scripts/geocode_flood.py). Access date: October 2026.

## data.gov.sg (Singapore Open Data Licence v1.0)

| File | Dataset | ID | Publisher | Used for |
|---|---|---|---|---|
| `hdb_property_info.json` | HDB Property Information | d_17f5382f26140b1fdae0ba2ef6239d2f | HDB | units, rental units, year, MSCP |
| `hdb_buildings.geojson` | HDB Existing Building | d_16b157c52ed637edd6ba1232e026258d | HDB | block footprints |
| `subzones.geojson` | Master Plan 2019 Subzone Boundary (No Sea) | d_8594ae9ff96d0c708bc2af633048edfb | URA | subzones, land mask |
| `pop_age_subzone_2020.csv` | Resident Population by Planning Area/Subzone, Age Group and Sex (Census 2020) | d_d95ae740c0f8961a0b10435836660ce0 | SingStat | senior share |
| `hawker_centres.geojson` | Hawker Centres | d_4a086da0a5553be1d89383cd90d07ecd | NEA | access |
| `chas_clinics.geojson` | CHAS Clinics | d_548c33ea2d99e29ec63a7cc9edcccedc | MOH | access |
| `mrt_exits.geojson` | LTA MRT Station Exit | d_b39d3a0871985372d7e1637193335da5 | LTA | access |
| `bus_stops.geojson` | LTA Bus Stop | d_3f172c6feb3f4f92a2f47d93eed2908a | LTA | access |
| `eldercare.geojson` | Eldercare Services | d_f0fd1b3643ed8bd34bd403dedd7c1533 | MOH | access |
| `nparks_parks_reserves.geojson` | NParks Parks and Nature Reserves | d_77d7ec97be83d44f61b85454f844382f | NParks | green-blue |
| `park_connector.geojson` | Park Connector Loop | d_a69ef89737379f231d2ae93fd1c5707f | NParks | green-blue |
| `waterbody.geojson` | Master Plan 2019 SDCP Waterbody | d_0b0792ae30cd6cce62e5ea55fc37860e | URA | green-blue |
| `community_in_bloom.geojson` | Community in Bloom (CIB) | d_f91a8b057cfb2bebf2e531ad8061e1c1 | NParks | community proxy |
| `landuse_mp2025.geojson` | Master Plan 2025 Land Use | d_a8c3546b26712e35021f3a681d0353ae | URA | tweak candidates |
| `resale_2017on.csv` | Resale flat prices (registration date, Jan 2017 onwards) | d_8b84c4ee58e3cfc0ece0d773c8ca6abc | HDB | value lens |
| `wbgt_2026_MarMay.json` | WBGT (real-time API, history) | d_87884af1f85d702d4f74c6af13b4853d | NEA | context layer |

*Contains information from the datasets listed above, accessed October 2026 from data.gov.sg, made available under the terms of the [Singapore Open Data Licence version 1.0](https://data.gov.sg/open-data-licence).*

## Other sources

| Source | Licence / terms | Used for |
|---|---|---|
| PUB, *List of Flood Prone Areas in Singapore (as of Nov 2025)*, PDF | Public document; locations geocoded with OneMap | flood pillar |
| OneMap Search API and Grey basemap tiles, Singapore Land Authority | OneMap terms of use; attribution shown on maps | geocoding, basemap |
| Landsat 5/8/9 Collection 2 Level-2 (USGS), via Microsoft Planetary Computer | Public domain (USGS) | land surface temperature |
| Copernicus Sentinel-2 L2A (ESA), via Microsoft Planetary Computer | Copernicus open licence: "contains modified Copernicus Sentinel data 2024–2025" | NDVI, true colour |
| OpenStreetMap, BBBike Singapore extract (base 2026-10-09) | ODbL 1.0, © OpenStreetMap contributors | walking network, covered ways |
| Wikimedia Commons photographs | CC0 / CC BY / CC BY-SA, per [`credits.json`](../web/assets/img/photos/credits.json) | website imagery |
