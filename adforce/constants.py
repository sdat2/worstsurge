"""Constants for adforce package."""

import os
from pathlib import Path
from sithom.place import BoundingBox, Point

# regional bounding boxes for ERA5 download.
# Gulf of Mexico box (lons, lats)
GOM_BBOX = BoundingBox([-100, -80], [15, 35], desc="Gulf of Mexico Bounding Box")
# New Orleans box (lons, lats)
NO_BBOX = BoundingBox([-92, -86.5], [28.5, 30.8], desc="New Orleans Area Bounding Box")

# Significant places (lon, lat)
NEW_ORLEANS = Point(-90.0715, 29.9511, desc="New Orleans")  # lon , lat
MIAMI = Point(-80.1918, 25.7617, desc="Miami")
GALVERSTON = Point(-94.7977, 29.3013, desc="Galverston")

# Paths
SRC_PATH = Path(__file__).parent
SETUP_PATH = os.path.join(SRC_PATH, "setup")
PROJ_PATH = Path(SRC_PATH).parent
DATA_PATH = os.path.join(PROJ_PATH, "data")
CONFIG_PATH = os.path.join(SRC_PATH, "config")
FIGURE_PATH = os.path.join(PROJ_PATH, "img", "adforce")
FORT63_EXAMPLE = os.path.join(DATA_PATH, "fort.63.nc")
