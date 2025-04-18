"""Functions to calculate potential size from xarray inputs in parallel."""

import os
from joblib import Parallel, delayed
import numpy as np
import xarray as xr
from tqdm import tqdm
from sithom.io import read_json
from sithom.time import timeit, time_stamp
from sithom.misc import get_git_revision_hash
from .constants import (
    TEMP_0K,
    DATA_PATH,
    PROJECT_PATH,
    W_COOL_DEFAULT,
    GAS_CONSTANT,
    GAS_CONSTANT_FOR_WATER_VAPOR,
    SUPERGRADIENT_FACTOR,
    LOWER_RADIUS_BISECTION,
    UPPER_RADIUS_BISECTION,
    PRESSURE_DIFFERENCE_BISECTION_TOLERANCE,
    LOWER_Y_WANG_BISECTION,
    UPPER_Y_WANG_BISECTION,
    W22_BISECTION_TOLERANCE,
    CK_CD_DEFAULT,
    CD_DEFAULT,
    ENVIRONMENTAL_HUMIDITY_DEFAULT,
)
from .potential_size import run_cle15, wang_diff, wang_consts
from .utils import (
    coriolis_parameter_from_lat,
    buck_sat_vap_pressure,
    pressure_from_wind,
)
from .solve import bisection


@timeit
def point_solution_ps(
    ds: xr.Dataset,
    supergradient_factor: float = SUPERGRADIENT_FACTOR,
    include_profile: bool = False,
    pressure_assumption="isothermal",
) -> xr.Dataset:
    """
    Find the solution for a given point in the grid.

    Args:
        ds (xr.Dataset): Dataset with the input values.
        supergradient_factor (float, optional): Supergradient. Defaults to 1.2.
        include_profile (bool, optional)
        pressure_assumption (str, optional): Assumption for pressure calculation. Defaults to "isothermal". Alternative is "isopycnal".

    Returns:
        xr.Dataset: Find the solution dataset.

    Example:
        >>> in_ds = xr.Dataset(data_vars={
        ...     "msl": 1016.7, # mbar or hPa
        ...     "vmax": 49.5, # m/s, potential intensity
        ...     "sst": 28, # degC
        ...     "t0": 200, # degK
        ...     "rh": 0.9, # [dimensionless], relative humidity
        ...     },
        ...     coords={"lat":28})
        >>> out_ds = point_solution_ps(in_ds)
    """

    # read compuslory parameters
    p_a = float(ds["msl"].values)  # ambient surface pressure in mbars
    near_surface_air_temperature = (
        ds["sst"].values + TEMP_0K - 1
    )  # Celsius Kelvin, subtract 1K for parameterization for near surface
    outflow_temperature = float(ds["t0"].values)
    vmax = float(ds["vmax"].values)
    coriolis_parameter = abs(coriolis_parameter_from_lat(ds["lat"].values))
    # optional parameters, set to default if they are not in the dataset
    if "ck_cd" not in ds:
        ck_cd = CK_CD_DEFAULT
    else:
        ck_cd = float(ds["ck_cd"].values)
    if "cd" not in ds:
        cd = CD_DEFAULT
    else:
        cd = float(ds["cd"].values)
    if "w_cool" not in ds:
        w_cool = W_COOL_DEFAULT
    else:
        w_cool = float(ds["w_cool"].values)
    if "supergradient_factor" not in ds:
        supergradient_factor = SUPERGRADIENT_FACTOR
    else:
        supergradient_factor = float(ds["supergradient_factor"].values)
    if "rh" not in ds:
        env_humidity = ENVIRONMENTAL_HUMIDITY_DEFAULT
    else:
        env_humidity = float(ds["rh"].values)
    if "rho_air" not in ds:
        water_vapour_pressure = env_humidity * buck_sat_vap_pressure(
            near_surface_air_temperature
        )
        rho_air = (p_a * 100 - water_vapour_pressure) / (
            GAS_CONSTANT * near_surface_air_temperature
        ) + water_vapour_pressure / (
            GAS_CONSTANT_FOR_WATER_VAPOR * near_surface_air_temperature
        )
    else:
        rho_air = float(ds["rho_air"].values)

    def try_for_r0(r0: float):
        pm_cle, rmax_cle, pc_cle = run_cle15(
            plot=False,
            inputs={
                "r0": r0,
                "Vmax": vmax,
                "w_cool": w_cool,
                "fcor": coriolis_parameter,
                "p0": p_a,  # in hPa / mbar
                "CkCd": ck_cd,
                "Cd": cd,
            },
            rho0=rho_air,
            pressure_assumption=pressure_assumption,
        )

        ys = bisection(
            wang_diff(
                *wang_consts(
                    radius_of_max_wind=rmax_cle,
                    radius_of_inflow=r0,
                    maximum_wind_speed=vmax * supergradient_factor,
                    coriolis_parameter=coriolis_parameter,
                    pressure_dry_at_inflow=p_a * 100  # 100 to convert from hPa to Pa
                    - env_humidity
                    * buck_sat_vap_pressure(
                        near_surface_air_temperature
                    ),  # env humidity intially assumed to be 1, now assumed to be 0.9 in default
                    near_surface_air_temperature=near_surface_air_temperature,
                    outflow_temperature=outflow_temperature,
                )
            ),
            LOWER_Y_WANG_BISECTION,
            UPPER_Y_WANG_BISECTION,
            W22_BISECTION_TOLERANCE,  # threshold
        )
        # convert solution to pressure
        pm_car = (  # 100 to convert from hPa to Pa
            p_a * 100 - buck_sat_vap_pressure(near_surface_air_temperature)
        ) / ys + buck_sat_vap_pressure(near_surface_air_temperature)
        # if match_center:
        #    return pc_cle - pm_car
        # else:
        return pm_cle - pm_car
        # print("r0, rmax_cle, pm_cle, pm_car", r0, rmax_cle, pm_cle, pm_car)

    r0 = bisection(
        try_for_r0,
        LOWER_RADIUS_BISECTION,
        UPPER_RADIUS_BISECTION,
        PRESSURE_DIFFERENCE_BISECTION_TOLERANCE,
    )  # find potential size \(r_a\) between 200 and 5000 km with 1 Pa absolute tolerance

    pm_cle, rmax_cle, pc = run_cle15(
        plot=False,
        inputs={
            "r0": r0,
            "Vmax": vmax,
            "w_cool": w_cool,
            "fcor": coriolis_parameter,
            "p0": p_a,  # in hPa / mbar
            "CkCd": ck_cd,
            "Cd": cd,
        },
        rho0=rho_air,
        pressure_assumption=pressure_assumption,
    )
    # read the solution
    ds["r0"] = r0
    ds["r0"].attrs = {
        "units": "m",
        "long_name": "Potential size of tropical cyclone, $r_a$",
    }
    ds["pm"] = pm_cle
    ds["pm"].attrs = {"units": "Pa", "long_name": "Pressure at maximum winds, $p_m$"}
    ds["pc"] = pc
    ds["pc"].attrs = {"units": "Pa", "long_name": "Central pressure for CLE15 profile"}
    ds["rmax"] = rmax_cle
    ds["rmax"].attrs = {
        "units": "m",
        "long_name": "Radius of maximum winds, $r_{\mathrm{max}}$",
    }
    ds["rho_air"] = rho_air
    ds["rho_air"].attrs = {
        "units": "kg m-3",
        "long_name": "Air density at surface",
    }
    if include_profile:
        # TODO: This is reading the wrong data.
        out = read_json(os.path.join(DATA_PATH, "outputs.json"))
        ds["radii"] = ("r", out["rr"], {"units": "m", "long_name": "Radius"})
        ds["velocities"] = (
            "r",
            out["VV"],
            {"units": "m s-1", "long_name": "Azimuthal Velocity"},
        )
        ds["pressures"] = (
            "r",
            pressure_from_wind(
                np.array(out["rr"]),  # [m]
                np.array(out["VV"]),  # [m/s]
                p_a * 100,  # [Pa] 100 to convert from hPa to Pa
                rho_air,  # [kg m-3]
                coriolis_parameter,  # [rad s-1]
                assumption=pressure_assumption,
            )
            / 100,
            {"units": "mbar", "long_name": "Surface Pressure"},
        )
    return ds


@timeit
def parallelized_ps(
    ds: xr.Dataset, jobs=10, pressure_assumption="isothermal"
) -> xr.Dataset:
    """
    Apply point solution to all of the points in the dataset, using joblib to paralelize.

    Args:
        ds (xr.Dataset): contains msl, vmax, sst, t0, rh, and lat.
        jobs (int, optional): Number of threads, defaults to 10.
        pressure_assumption (str, optional): Assumption for pressure calculation. Defaults to "isothermal". Alternative is "isopycnal".

    Returns:
        xr.Dataset: additionally contains r0, pm, pc, and rmax.
    """
    # the dataset might have a series of dimensions: time, lat, lon, member, etc.
    # it must have variables msl, vmax, sst, and t0, and coordinate lat for each point
    # we want to loop through these (in parallel) and apply the point_solution function
    # to each point, so that we end up with a new dataset with the same dimensions
    # that now has additional variables r0, pm, pc, rmax
    # we should call point_solution(ds_part, include_profile=False)
    # Step 1: Stack all spatial dimensions into a single dimension
    # ds.dims
    dims = list(ds.dims)

    def ps_skip(ids: xr.Dataset) -> xr.Dataset:
        try:
            assert not np.isnan(ids.vmax.values)  # did not converge
            assert ids["vmax"].values > 0.01  # is positive
            assert not np.isnan(ids.sst.values)  # is sea surface
            return point_solution_ps(
                ids, include_profile=False, pressure_assumption=pressure_assumption
            )
        except AssertionError as e:
            print(e.args[0] if e.args else "error")
            print(e)
            ids["pm"] = np.nan
            ids["pc"] = np.nan
            ids["r0"] = np.nan
            ids["rmax"] = np.nan
            return ids
        except Exception as e:
            print("Exception:", e)
            ids["pm"] = np.nan
            ids["pc"] = np.nan
            ids["r0"] = np.nan
            ids["rmax"] = np.nan
            return ids

    if len(dims) == 0:
        assert False
    elif len(dims) == 1:

        def process_point(index: int) -> xr.Dataset:
            """Apply point_solution to a single data point."""
            # return point_solution(ds_stacked.isel(stacked_dim=index), include_profile=False)
            return ps_skip(ds.isel({dims[0]: index}))

        print(f"About to conduct {ds.sizes[dims[0]]} jobs in parallel")
        results = Parallel(n_jobs=jobs)(
            delayed(process_point)(i) for i in range(ds.sizes[dims[0]])
        )
        output_ds = xr.concat(results, dim=dims[0])
    else:
        ds_stacked = ds.stack(stacked_dim=dims)

        def process_point(index: int) -> xr.Dataset:
            """Apply point_solution to a single data point."""
            # return point_solution(ds_stacked.isel(stacked_dim=index), include_profile=False)
            return ps_skip(ds_stacked.isel(stacked_dim=index))

        print(f"About to conduct {ds_stacked.sizes['stacked_dim']} jobs in parallel")
        # Step 2: Parallelize computation across all stacked points
        results = Parallel(n_jobs=jobs)(
            delayed(process_point)(i)
            for i in tqdm(range(ds_stacked.sizes["stacked_dim"]))
        )

        # Step 3: Reconstruct the original dataset dimensions
        output_ds = (
            xr.concat(results, dim="stacked_dim")
            .set_index(stacked_dim=dims)  # Restore multi-index before unstacking
            .unstack("stacked_dim")
        )
    output_ds.attrs["potential_size_pressure_assumption"] = pressure_assumption
    output_ds.attrs["pi_calculated_at_git_hash"] = get_git_revision_hash(
        path=str(PROJECT_PATH)
    )
    output_ds.attrs["pi_calculated_at_time"] = time_stamp()
    return output_ds


def single_point_example() -> None:
    in_ds = xr.Dataset(
        data_vars={
            "msl": 1016.7,  # mbar or hPa
            "vmax": 49.5,  # m/s, potential intensity
            "sst": 28,  # degC
            "t0": 200,  # degK
        },
        coords={"lat": 28},  # degNorth
    )
    out_ds = point_solution_ps(in_ds)
    print(out_ds)


def multi_point_example_1d() -> None:
    in_ds = xr.Dataset(
        data_vars={
            "msl": ("y", [1016.7, 1016.7]),  # mbar or hPa
            "vmax": ("y", [49.5, 49.5]),  # m/s, potential intensity
            "sst": ("y", [28, 28]),  # degC
            "t0": ("y", [200, 200]),  # degK
        },
        coords={"lat": ("y", [28, 29])},  # degNorth
    )
    out_ds = parallelized_ps(in_ds)
    print(out_ds)


def multi_point_example_2d() -> None:
    in_ds = xr.Dataset(
        data_vars={
            "msl": (("y", "x"), [[1016.7, 1016.7], [1016.7, 1016.7]]),  # mbar or hPa
            "vmax": (
                ("y", "x"),
                [[50, 51], [49, 49.5]],
            ),  # m/s, potential intensity
            "rh": (("y", "x"), [[0.9, 0.9], [0.9, 0.9]]),
            "rh": (("y", "x"), [[0.9, 0.9], [0.9, 0.9]]),
            "sst": (("y", "x"), [[29, 30], [28, 28]]),  # degC
            "ck_cd": (("y", "x"), [[0.95, 0.95], [0.95, 0.95]]),
            "t0": (("y", "x"), [[200, 200], [200, 200]]),  # degK
        },
        coords={"lat": (("y", "x"), [[30, 30], [45, 45]])},  # degNorth
    )
    print(in_ds)
    out_ds = parallelized_ps(in_ds)
    print(out_ds)


if __name__ == "__main__":
    # python -m w22.ps
    # single_point_example()
    multi_point_example_2d()
