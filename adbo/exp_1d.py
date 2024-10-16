"""
Conduct a 1D experiment for ease of plotting.
"""

import os
from adbo.constants import CONFIG_PATH
from yaml import safe_load


constraints = safe_load(open(os.path.join(CONFIG_PATH, "1d_constraints.yaml")))

print(constraints)
