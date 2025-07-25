"""Potential Intensity Calculation script."""

from typing import Callable
import numpy as np
import xarray as xr
from tcpyPI import pi
from sithom.time import timeit, time_stamp
from sithom.misc import get_git_revision_hash
from .constants import PROJECT_PATH
from .xr_utils import standard_name_to_long_name

CKCD: float = 0.9  # Enthalpy exchange coefficient / drag coefficient [dimensionless]
PTOP: float = 50.0  # Top pressure level for the calculation [hPa]


def fix_temp_profile(ds: xr.Dataset, offset_temp_param: float = 1) -> xr.Dataset:
    """
    Fix the temperature profile in the dataset.

    Problem in calculating the potential intensity with incomplete temperature profiles.

    At some places such as the Gulf of Tonkin and the Bay of Bengal, the mean sea level
    pressure in CESM2 in August is low, leading to NaN values in the temperature profile
    at the 1000 hPa level.

    To fix this, we could assume an approximation that the temperature at these low levels
    is equal to sea surface temperature minus one kelvin (a standard parameterization for near surface air temperature).

    TODO: Make this only effect the bottom NaNs of the profile.
    TODO: convert all very high values to NaN (i.e. if t > 300 C, set to NaN).

    Args:
        ds (xr.Dataset): xarray dataset containing the necessary variables "t" and "sst".
        offset_temp_param (float, optional): Temperature offset parameter. Defaults to 1.

    Returns:
        xr.Dataset: xarray dataset with fixed temperature profile.

    Example:
        >>> ds = xr.Dataset(data_vars={"sst": (["x", "y"], [[1, 2], [3, 4]],
        ...                                    {"units": "degrees_Celsius"}),
        ...                            "t": (["x", "y", "p"],
        ...                              [[[np.nan, 2], [3, 4]], [[5, 6], [np.nan, 8]]],
        ...                              {"units": "degrees_Celsius"})},
        ...                 coords={"x": (["x"], [-80, -85], {"units": "degrees_East"}),
        ...                         "y": (["y"], [20, 25], {"units": "degrees_North"}),
        ...                         "p": (["p"], [1000, 850], {"units": "hPa"})})
        >>> ds_fixed = fix_temp_profile(ds, offset_temp_param=1)
        >>> np.allclose(ds_fixed.isel(p=0).t.values, [[0, 3], [5, 3]])
        True
    """
    # Fix the temperature profile (doesn't check how)
    sea_level_temp = ds["sst"] - offset_temp_param
    # make all implausibly high values NaN
    # if air temperature > 300 C, set to NaN
    ds["t"] = ds["t"].where(ds["t"] < 300, np.nan)
    # fill in NaN values in the temperature profile with the sea level temperature
    # If air temperature is NaN, set to sea level temperature
    ds["t"] = ds["t"].where(ds["t"].notnull(), sea_level_temp)
    return ds


@timeit
def calculate_pi(
    ds: xr.Dataset, dim: str = "p", fix_temp=False, V_reduc=1.0
) -> xr.Dataset:
    """Calculate the potential intensity using the tcpyPI package.

    Data must have been converted to the tcpyPI units by `tcpips.convert'.

    Args:
        ds (xr.Dataset): xarray dataset containing the necessary variables.
        dim (str, optional): Vertical dimension. Defaults to "p" for pressure level.
        fix_temp (bool, optional): Whether to fix the temperature profile. Defaults to True.
        V_reduc (float, optional): Reduction factor for the wind speed. Defaults to 1.0.


    Returns:
        xr.Dataset: xarray dataset containing the calculated variables.

    Example:
        >>> ds = xr.Dataset(data_vars={"sst": (["x", "y"], [[20, 30], [30, 32]],
        ...                                    {"units": "degrees_Celsius"}),
        ...                            "msl": (["x", "y"], [[1000, 1005], [1010, 1015]],
        ...                                    {"units": "hPa"}),
        ...                            "t": (["x", "y", "p"],
        ...                                  [[[np.nan, 23], [30, 21]], [[30, 21], [np.nan, 23]]],
        ...                                  {"units": "degrees_Celsius"}),
        ...                            "q": (["x", "y", "p"],
        ...                                  [[[10, 20], [30, 40]], [[50, 60], [70, 80]]],
        ...                                  {"units": "g/kg"})},
        ...                 coords={"x": (["x"], [-80, -85], {"units": "degrees_East"}),
        ...                         "y": (["y"], [20, 25], {"units": "degrees_North"}),
        ...                         "p": (["p"], [1000, 850], {"units": "hPa"})})
        >>> pi_ds = calculate_pi(ds, fix_temp=True) # doctest: +SKIP
    """
    if fix_temp:
        ds = fix_temp_profile(ds)

    result = xr.apply_ufunc(
        pi,
        ds["sst"],
        ds["msl"],
        ds[dim],
        ds["t"],
        ds["q"],
        kwargs=dict(
            CKCD=CKCD,
            ascent_flag=0,
            diss_flag=1,
            ptop=PTOP,
            miss_handle=1,
            V_reduc=V_reduc,
        ),
        input_core_dims=[
            [],
            [],
            [
                dim,
            ],
            [
                dim,
            ],
            [
                dim,
            ],
        ],
        output_core_dims=[[], [], [], [], []],
        vectorize=True,
        # dask="allowed", # maybe this could work with dask, but at the moment I get an error
        dask="parallelized",
    )

    # store the result in an xarray data structure
    vmax, pmin, ifl, t0, otl = result
    out_ds = xr.Dataset(
        {
            "vmax": vmax,  # maybe change to vp
            "pmin": pmin,
            "ifl": ifl,
            "t0": t0,
            "otl": otl,
        }
    )

    # add names and units to the structure
    out_ds.vmax.attrs["standard_name"], out_ds.vmax.attrs["units"] = (
        "Potential Intensity",
        "m/s",
    )
    out_ds.pmin.attrs["standard_name"], out_ds.pmin.attrs["units"] = (
        "Minimum Central Pressure",
        "hPa",
    )
    out_ds.ifl.attrs["standard_name"] = "tcpyPI Flag"
    out_ds.t0.attrs["standard_name"], out_ds.t0.attrs["units"] = (
        "Outflow Temperature",
        "K",
    )
    out_ds.otl.attrs["standard_name"], out_ds.otl.attrs["units"] = (
        "Outflow Temperature Level",
        "hPa",
    )
    out_ds.attrs["V_reduc"] = V_reduc
    out_ds.attrs["CKCD"] = CKCD
    out_ds.attrs["ptop"] = PTOP
    ds.attrs["pi_calculated_at_git_hash"] = get_git_revision_hash(
        path=str(PROJECT_PATH)
    )
    ds.attrs["pi_calculated_at_time"] = time_stamp()

    return standard_name_to_long_name(out_ds)


def simple_sensitivity(delta_t=1, k=0.07, m=1, avg_to_tropical_ocean=0.8):
    """
    Simple sensitivity analysis for the change in potential intensity
    based on the change in temperature and humidity.

    Args:
        delta_t (float): Change in temperature in Kelvin.
        k (float): Scaling factor for humidity change based on CC (default 0.07).
        m (float): Scaling factor for the change in outflow temperature (default 1).
        avg_to_tropical_ocean (float): Average temperature change for tropical ocean compared to global temperature (default 0.8).
    """
    delta_t = (
        delta_t * avg_to_tropical_ocean
    )  # scale to tropical ocean average temperature change
    # let's start by doing a simple sensitivty for potential intensity
    T_s0 = 300  # K
    T_00 = 200  # K
    # approx as Bister 1998 and use 7% scaling for humidity CC per degree to scale enthalpy change
    # T_s = T_s0 + delta_t  # K
    # T_0 = T_00 + m* delta_t  # K

    vp1_div_vp0 = np.sqrt(
        (T_s0 - T_00 + (1 - m) * delta_t)
        / (T_00 + m * delta_t)
        * T_00
        / (T_s0 - T_00)
        * (1 + k * delta_t)
    )
    print(
        f"vp1/vp0 = {vp1_div_vp0:.3f} for delta_t = {delta_t} K, T_s0 = {T_s0} K, T_00 = {T_00} K, m = {m}, k = {k}"
    )
    print(f"fractional change = {(vp1_div_vp0 - 1)* 100:.3f}%")


# vp1/vp0 = 1.042 for delta_t = 0.8 K, T_s0 = 300 K, T_00 = 200 K, m = -1.7, k = 0.07
# fractional change = 4.221%
# vp1/vp0 = 1.038 for delta_t = 0.8 K, T_s0 = 300 K, T_00 = 200 K, m = -1, k = 0.07
# fractional change = 3.788%
# vp1/vp0 = 1.026 for delta_t = 0.8 K, T_s0 = 300 K, T_00 = 200 K, m = 1, k = 0.07
# fractional change = 2.557%
# vp1/vp0 = 1.024 for delta_t = 0.8 K, T_s0 = 300 K, T_00 = 200 K, m = 1.2, k = 0.07
# fractional change = 2.434%
# vp1/vp0 = 1.022 for delta_t = 0.8 K, T_s0 = 300 K, T_00 = 200 K, m = 1.5, k = 0.07
# fractional change = 2.250%


if __name__ == "__main__":
    # python -m tcpips.pi
    simple_sensitivity(1, k=0.07, m=-1.7)
    simple_sensitivity(1, k=0.07, m=-1)
    simple_sensitivity(1)
    simple_sensitivity(1, k=0.07, m=1.2)
    simple_sensitivity(1, k=0.07, m=1.5)
