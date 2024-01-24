"""Fort.22.nc file reader and writer."""
import os
import xarray as xr
import datatree as dt
from netCDF4 import Dataset
from tcpips.constants import DATA_PATH


def read_fort22(fort22_path: str = None) -> xr.Dataset:
    """Read fort.22.nc file.

    Parameters
    ----------
    fort22_path : str, optional
        Path to fort.22.nc file. If not provided, the default path will be used.

    Returns
    -------
    xr.Dataset
        Dataset containing fort.22.nc data.

    """
    if fort22_path is None:
        fort22_path = os.path.join(DATA_PATH, "fort.22.nc")
    return dt.open_datatree(fort22_path)


if __name__ == "__main__":
    # python -m tcpips.fort22
    fort22 = read_fort22()
    g1 = fort22.groups[1]
    g2 = fort22.groups[2]
    # print(g1, g2)
    print(fort22)
    f22 = fort22.drop_nodes(["2004223N11301", "2004227N09314"])
    print(fort22.groups)
    print(f22.groups)
    f22["2004217N13306"].name = "TC"
    f22[""].attrs["group_order"] = ["Main", "TC"]
    # f22.rename({"2004217N13306": "TC"})
    f22.to_netcdf(os.path.join(DATA_PATH, "test.nc"))
    ds = Dataset(os.path.join(DATA_PATH, "test.nc"))
    print(ds)
    print(ds.groups["TC"])
    print(ds.groups["Main"])
