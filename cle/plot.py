"""
Plot the relationships between the variables including potential size."""

from typing import Callable, Tuple, Optional, Dict, List
import os
import numpy as np
import xarray as xr
from matplotlib import pyplot as plt
from scipy.stats import pearsonr

from sithom.plot import plot_defaults, pairplot, label_subplots
from sithom.time import timeit
from sithom.io import write_json
from sithom.curve import fit
from tcpips.pi import gom_bbox_combined_inout_timestep_cmip6
from tcpips.constants import GOM
from .constants import (
    TEMP_0K,
    BACKGROUND_PRESSURE,
    DEFAULT_SURF_TEMP,
    FIGURE_PATH,
    DATA_PATH,
    SUP_PATH,
)

from .solve import bisection
from .potential_size import (
    profile_from_vals,
    run_cle15,
    wang_diff,
    wang_consts,
)
from .utils import buck_sat_vap_pressure, carnot_factor
from .ps_dataset import find_solution_ds, gom_timestep

plot_defaults()


def vary_r0_c15_plot(r0s: np.ndarray) -> np.ndarray:
    """
    Plot the pressure at maximum winds for different radii.

    Args:
        r0s (np.ndarray): Outer radii.

    Returns:
        np.ndarray: Pressure at maximum winds.
    """

    pms = np.array([run_cle15(plot=False, inputs={"r0": r0})[0] for r0 in r0s])
    plt.plot(r0s / 1000, pms / 100, "k")
    plt.xlabel("Outer wind radius, $r_a$, [km]")
    plt.ylabel("Pressure at maximum winds, $p_m$, [hPa]")
    plt.savefig(os.path.join(DATA_PATH, "r0_pc.pdf"))
    plt.clf()
    return pms


def vary_r0_w22_plot(r0s: np.ndarray, plot=False) -> np.ndarray:
    """
    Plot the pressure at maximum winds for different radii.

    Args:
        r0s (np.ndarray): Outer radii.

    Returns:
        np.ndarray: Pressure at maximum winds.
    """
    ys = np.array(
        [
            bisection(wang_diff(*wang_consts(radius_of_inflow=r0)), 0.3, 1.2, 1e-6)
            for r0 in r0s
        ]
    )
    pms = (
        BACKGROUND_PRESSURE - buck_sat_vap_pressure(DEFAULT_SURF_TEMP)
    ) / ys + buck_sat_vap_pressure(DEFAULT_SURF_TEMP)
    plt.plot(r0s / 1000, np.array(pms) / 100, "r")
    plt.xlabel("Radius, $r_a$, [km]")
    plt.ylabel("Pressure at maximum winds, $p_m$, [hPa]")
    plt.savefig(os.path.join(FIGURE_PATH, "r0_pc_wang.pdf"))
    plt.clf()
    return pms


def plot_from_ds(ds_name: str = os.path.join(DATA_PATH, "gom_soln_new.nc")) -> None:
    """
    Plot the relationships between the variables.

    Args:
        ds_name (str, optional): Defaults to os.path.join(DATA_PATH, "gom_soln_new.nc").
    """
    ds = xr.open_dataset(ds_name)
    folder = SUP_PATH
    os.makedirs(folder, exist_ok=True)
    print("ds", ds)
    fig, axs = plt.subplots(3, 1, figsize=(6, 8), sharex=True)
    axs[0].plot(ds["time"], ds["r0"] / 1000, "k")
    axs[1].plot(ds["time"], ds["vmax"], "k")
    axs[2].plot(ds["time"], ds["pm"] / 100, "k")
    label_subplots(axs)
    plt.xlabel("Year")
    axs[0].set_ylabel("Radius of outer winds, $r_a$, [km]")
    axs[1].set_ylabel("Maximum wind speed, $V_{\mathrm{max}}$, [m s$^{-1}$]")
    axs[2].set_ylabel("Pressure at maximum winds, $p_m$, [hPa]")
    label_subplots(axs)
    plt.savefig(os.path.join(folder, "rmax_time_new.pdf"))
    plt.clf()

    im = plt.scatter(
        ds["vmax"].values, ds["r0"].values / 1000, c=ds["time"], marker="x"
    )
    plt.colorbar(im, label="Year", shrink=0.5)
    plt.xlabel("Maximum wind speed, $V_{\mathrm{max}}$, [m s$^{-1}$]")
    plt.ylabel("Radius of outer winds, $r_a$, [km]")
    plt.savefig(os.path.join(FIGURE_PATH, "rmax_vmax.pdf"))
    plt.clf()
    ds["year"] = ("time", ds["time"].values)
    vars: List[str] = ["r0", "vmax", "pm", "sst", "msl", "t0", "year"]  # , "time"]

    pairplot(ds[vars].to_dataframe()[vars])
    plt.savefig(os.path.join(folder, "pairplot.pdf"))
    plt.clf()

    vars = ["t", "q", "vmax", "r0", "pm", "t0", "year"]
    pairplot(ds.isel(p=0)[vars].to_dataframe()[vars])
    plt.savefig(os.path.join(folder, "pairplot2.pdf"))
    plt.clf()

    # do a line plot of sst, vmax, and r0
    fig, axs = plt.subplots(3, 1, figsize=(6, 8), sharex=True)
    axs[0].plot(ds["time"], ds["sst"], "k")
    axs[1].plot(ds["time"], ds["vmax"], "k")
    axs[2].plot(ds["time"], ds["r0"] / 1000, "k")
    label_subplots(axs)
    plt.xlabel("Year")
    axs[0].set_ylabel("Sea surface temperature, $T_s$, [$^\circ$C]")
    axs[1].set_ylabel("Maximum wind speed, $V_{\mathrm{max}}$, [m s$^{-1}$]")
    axs[2].set_ylabel("Radius of outer winds, $r_a$, [km]")
    plt.savefig(os.path.join(folder, "sst_vmax_rmax.pdf"))

    # do a line plot of carnot factor, vmax, and r0
    fig, axs = plt.subplots(3, 1, figsize=(6, 8), sharex=True)
    ds["carnot"] = (
        "time",
        1 / carnot_factor(ds["sst"].values + TEMP_0K, ds["t0"].values),
    )
    axs[0].plot(ds["time"], ds["carnot"], "k")
    axs[1].plot(ds["time"], ds["vmax"], "k")
    axs[2].plot(ds["time"], ds["r0"] / 1000, "k")
    label_subplots(axs)
    plt.xlabel("Year")
    axs[0].set_ylabel(
        r"Carnot factor, $\eta_c$, $\frac{T_h}{T_h- T_c}$ [dimensionless]"
    )
    axs[1].set_ylabel("Maximum wind speed, $V_{\mathrm{max}}$, [m s$^{-1}$]")
    axs[2].set_ylabel("Radius of outer winds, $r_a$, [km]")
    plt.savefig(os.path.join(folder, "carnot_vmax_rmax.pdf"))

    # pairplot of carnot factor, vmax, and r0
    vars = ["carnot", "vmax", "r0", "year"]
    pairplot(ds[vars].to_dataframe()[vars])
    plt.savefig(os.path.join(folder, "pairplot3.pdf"))
    plt.clf()


def figure2() -> None:
    """Plot the solution for the GOM bbox for potential size and intensity."""
    _, axs = plt.subplots(
        2,
        2,
        figsize=(9, 6),
        width_ratios=[1, 1.5],
        height_ratios=[1, 1],
    )

    # axs[].plot(ds["time"], ds["sst"], "k")
    plot_defaults()
    ds = xr.open_dataset(os.path.join(DATA_PATH, "gom_soln_bbox.nc"))
    folder = SUP_PATH
    os.makedirs(folder, exist_ok=True)
    # print("ds", ds)
    ds["lon"].attrs = {"units": "$^{\circ}E$", "long_name": "Longitude"}
    ds["lat"].attrs = {"units": "$^{\circ}N$", "long_name": "Latitude"}
    print(ds)
    print(ds["sst"])
    lats = ds["lat"].values
    ssts = ds["sst"].values
    r0s = ds["r0"].values
    print("lats", lats.shape)
    print("ssts", ssts.shape)
    print("r0s", r0s.shape)
    lats = np.array([[lats[i] for i in range(len(lats))] for _ in range(len(ds.lon))])
    assert np.shape(lats) == np.shape(ssts)
    ssts = ssts.ravel()
    r0s = r0s.ravel()
    lats = lats.ravel()
    lats = lats[~np.isnan(ssts)]
    r0s = r0s[~np.isnan(ssts)]
    ssts = ssts[~np.isnan(ssts)]
    rho = pearsonr(lats, ssts)[0]
    print("rho (sst, lat): {:.2f}".format(rho))
    lats = lats[~np.isnan(r0s)]
    r0s = r0s[~np.isnan(r0s)]
    rho = pearsonr(lats, r0s)[0]
    print("rho (r0s, lat): {:.2f}".format(rho))

    timeseries_ds = xr.open_dataset(os.path.join(DATA_PATH, "gom_soln_new.nc"))
    (ds["r0"] / 1000).plot(ax=axs[1, 0], cbar_kwargs={"label": ""})
    axs[1, 0].set_title("Potential size, $r_a$ [km]")
    axs[1, 1].set_title("Potential size, $r_a$ [km]")
    ds["vmax"].plot(ax=axs[0, 0], cbar_kwargs={"label": ""})
    axs[0, 0].scatter(GOM[1], GOM[0], color="black", s=30, marker="x")
    axs[1, 0].scatter(GOM[1], GOM[0], color="black", s=30, marker="x")
    axs[0, 0].set_title("Potential intensity, $V_{\mathrm{max}}$ [m s$^{-1}$]")
    axs[0, 1].set_title("Potential intensity, $V_{\mathrm{max}}$ [m s$^{-1}$]")

    ## work out correlation between time and vmax between 2000 and 2099
    year_min = 2014
    year_max = 2100
    vmaxs = timeseries_ds["vmax"].sel(time=slice(year_min, year_max)).values
    r0s = timeseries_ds["r0"].sel(time=slice(year_min, year_max)).values
    years = timeseries_ds["time"].sel(time=slice(year_min, year_max)).values
    r_vmax = pearsonr(vmaxs, years)[0]
    r_r0 = pearsonr(r0s, years)[0]

    axs[0, 1].text(0.8, 0.9, f"$\\rho$ = {r_vmax:.2f}", transform=axs[0, 1].transAxes)
    axs[1, 1].text(0.8, 0.9, f"$\\rho$ = {r_r0:.2f}", transform=axs[1, 1].transAxes)

    # work out gradient with error bars for same period
    fit_vmax, _ = fit(years, vmaxs)
    fit_r0, _ = fit(years, r0s / 1000)
    axs[0, 1].text(
        0.66,
        0.05,
        f"$m=$  " "${:.1eL}$".format(fit_vmax[0]) + "\n \t\t\t m s$^{-1}$ yr$^{-1}$",
        transform=axs[0, 1].transAxes,
    )
    axs[1, 1].text(
        0.66,
        0.1,
        f"$m=$" + "${:.2L}$".format(fit_r0[0]) + " km yr$^{-1}$",
        transform=axs[1, 1].transAxes,
    )

    axs[0, 1].plot(timeseries_ds["time"], timeseries_ds["vmax"], "k")
    axs[1, 1].plot(timeseries_ds["time"], timeseries_ds["r0"] / 1000, "k")
    label_subplots(axs)
    axs[0, 0].set_xlabel("")
    axs[1, 1].set_xlabel("Year")
    axs[0, 1].set_xlim([1850, 2100])
    axs[1, 1].set_xlim([1850, 2100])
    # vertical black line at year_min
    axs[0, 1].axvline(year_min, color="black", linestyle="--", linewidth=0.5)
    axs[1, 1].axvline(year_min, color="black", linestyle="--", linewidth=0.5)
    plt.savefig(os.path.join(folder, "figure2.pdf"))
    plt.clf()
    print(timeseries_ds)


def plot_soln_curves(ds_name: str = os.path.join(DATA_PATH, "gom_soln_new.nc")) -> None:
    """
    Plot the solution curves for different.

    Args:
        ds_name (str, optional): Defaults to "gom_soln_new.nc".
    """
    plot_defaults()
    ds = xr.open_dataset(ds_name)
    folder = SUP_PATH
    os.makedirs(folder, exist_ok=True)
    print("ds", ds)
    for time in range(len(ds.time.values)):
        dst = ds.isel(time=time)
        plt.plot(
            dst["r0s"] / 1000,
            dst["pm_cle"] / 100,
            "b",
            label="CLE15 Dynamics",
            alpha=0.5,
            linewidth=0.5,
        )
        plt.plot(
            dst["r0s"] / 1000,
            dst["pm_car"] / 100,
            "r",
            alpha=0.5,
            label="W22 Thermodynamics",
            linewidth=0.5,
        )

        if time == 0:
            plt.legend()

    im = plt.scatter(
        ds["r0"] / 1000,
        ds["pm"] / 100,
        c=ds["time"],
        marker="x",
        label="Solution",
        linewidth=0.5,
        zorder=100,
    )
    plt.colorbar(im, label="Year", shrink=0.5)

    plt.xlabel("Outer Radius of Tropical Cyclone, $r_a$, [km]")
    plt.xlim([1000, 3000])
    plt.ylabel("Pressure at maximum winds, $p_m$, [hPa]")
    plt.ylim([875, 1000])
    plt.savefig(os.path.join(folder, "r0_solns.pdf"))
    plt.clf()

    im = plt.scatter(ds.vmax, ds.r0 / 1000, c=ds.pm / 100, marker="x", linewidth=0.5)
    plt.colorbar(im, label="Pressure at maximum winds, $p_m$, [hPa]", shrink=0.5)
    plt.xlabel("Maximum wind speed, $V_{\mathrm{max}}$, [m s$^{-1}$]")
    plt.ylabel("Outer Radius of Tropical Cyclone, $r_a$, [km]")
    plt.savefig(os.path.join(folder, "r0_vmax_pm.pdf"))
    plt.clf()

    im = plt.scatter(ds.vmax, ds.r0 / 1000, c=ds.time, marker="x", linewidth=0.5)
    plt.colorbar(im, label="Year", shrink=0.5)
    plt.xlabel("Maximum wind speed, $V_{\mathrm{max}}$, [m s$^{-1}$]")
    plt.ylabel("Outer Radius of Tropical Cyclone, $r_a$, [km]")
    plt.savefig(os.path.join(folder, "r0_vmax_time.pdf"))
    plt.clf()

    im = plt.scatter(ds.vmax, ds.pm / 100, c=ds.r0, marker="x", linewidth=0.5)
    plt.colorbar(im, label="Outer Radius of Tropical Cyclone, $r_a$, [km]", shrink=0.5)
    plt.xlabel("Maximum wind speed, $V_{\mathrm{max}}$, [m s$^{-1}$]")
    plt.ylabel("Pressure at maximum winds, $p_m$, [hPa]")
    # add in pearson correlation coefficient

    r = pearsonr(ds.vmax, ds.pm / 100)[0]
    plt.title(r"$\rho$ " + f"= {r:.2f}")
    plt.savefig(os.path.join(folder, "pm_vmax_r0.pdf"))
    plt.clf()


def plot_profiles(ds_name: str = os.path.join(DATA_PATH, "gom_soln_2.nc")) -> None:
    """
    Plot the azimuthal wind profiles for different times.

    Args:
        ds_name (str, optional): Defaults to "gom_soln_2.nc".
    """
    plot_defaults()
    ds = xr.open_dataset(ds_name)
    folder = SUP_PATH
    os.makedirs(folder, exist_ok=True)
    print("ds", ds)
    for time in range(len(ds.time.values)):
        dst = ds.isel(time=time)
        plt.plot(
            dst["radii"] / 1000,
            dst["velocities"],
            alpha=0.5,
            linewidth=0.5,
            # label=f"{[1850, 2099][time]}",
        )

    plt.legend()
    plt.xlabel("Radius, $r$, [km]")
    plt.ylabel("Wind speed, $V$, [m s$^{-1}$]")
    plt.savefig(os.path.join(folder, "profiles.pdf"))
    plt.clf()


def plot_gom_bbox() -> None:
    """Try and calculate the solution for the GOM bbox."""
    plot_defaults()

    ds = gom_bbox_combined_inout_timestep_cmip6(time="2015-01-15", pad=10)
    folder = SUP_PATH
    os.makedirs(folder, exist_ok=True)
    print(ds)
    ds.vmax.plot()
    plt.xlabel(r"Longitude, $\lambda$, [$^\circ$]")
    plt.ylabel(r"Latitude, $\phi$, [$^\circ$]")
    plt.savefig(os.path.join(folder, "gom_bbox_pi.pdf"))
    plt.clf()
    ds.sst.plot()
    plt.xlabel(r"Longitude, $\lambda$, [$^\circ$]")
    plt.ylabel(r"Latitude, $\phi$, [$^\circ$]")
    plt.savefig(os.path.join(folder, "gom_bbox_sst.pdf"))
    plt.clf()

    new_var = [
        "rmax",
        "pm",
        "pc",
        "r0",
    ]

    ds_list = []

    for i in range(len(ds.lat.values)):
        ds_list_lon = []
        for j in range(len(ds.lon.values)):
            print(i, j)  # zoom through grid.
            dsp = ds.isel(lat=i, lon=j)

            def add_nan() -> None:
                nonlocal ds_list_lon
                nonlocal dsp
                for var in new_var:
                    dsp[var] = np.nan
                ds_list_lon.append(dsp)

            def add_rmax() -> None:
                nonlocal ds_list_lon
                nonlocal dsp
                ds2 = find_solution_ds(dsp, plot=False)[new_var + [var for var in dsp]]
                for var in new_var:
                    dsp[var] = ds2[var]
                print("dsp", dsp)
                print([var for var in dsp])
                del dsp["radii"]
                del dsp["velocities"]
                ds_list_lon.append(dsp)

            # print(dsp)
            if True:
                # ok, let's just try it for one example
                # it is a big problem
                # we should check if vmax is in a reasonable range and non nan before running the calculation.
                if np.isnan(dsp.vmax.values):
                    print("nan vmax")
                    add_nan()
                elif dsp.vmax.values > 100:
                    print("vmax too high")
                    add_nan()
                elif dsp.vmax.values < 20:
                    print("vmax too low")
                    add_nan()
                else:
                    add_rmax()
        # if i == 5:
        ds_lon = xr.concat(ds_list_lon, dim="lon")
        ds_list.append(ds_lon)

    ds = xr.concat(ds_list, dim="lat")
    print("ds_list", ds_list)
    ds.to_netcdf(os.path.join(DATA_PATH, "gom_soln_bbox.nc"))


def plot_gom_bbox_soln() -> None:
    """Plot the solution for the GOM bbox."""
    plot_defaults()
    ds = xr.open_dataset(os.path.join(DATA_PATH, "gom_soln_bbox.nc"))
    folder = SUP_PATH
    os.makedirs(folder, exist_ok=True)
    print("ds", ds)
    ds["lon"].attrs = {"units": "$^{\circ}E$", "long_name": "Longitude"}
    ds["lat"].attrs = {"units": "$^{\circ}N$", "long_name": "Latitude"}

    fig, axs = plt.subplots(2, 3, figsize=(12, 6), sharex=True)
    axs = axs.T
    ds["sst"].where(~np.isnan(ds["t0"])).plot(
        ax=axs[0, 0],
        cbar_kwargs={
            "label": "Sea surface temperature, $T_s$ [$^\circ$C]",
        },
    )
    ds["t0"].plot(
        ax=axs[1, 0], cbar_kwargs={"label": "Outflow temperature, $T_0$, [K]"}
    )
    (ds["msl"] / 1).where(~np.isnan(ds["t0"])).plot(
        ax=axs[2, 0], cbar_kwargs={"label": "Mean sea level pressure, $P_0$, [hPa]"}
    )
    (ds["r0"] / 1000).plot(
        ax=axs[0, 1], cbar_kwargs={"label": "Potential size, $r_a$, [km]"}
    )
    ds["vmax"].plot(
        ax=axs[1, 1],
        cbar_kwargs={"label": "Potential intensity, $V_{\mathrm{max}}$, [m s$^{-1}$]"},
    )
    (ds["pm"] / 100).plot(
        ax=axs[2, 1], cbar_kwargs={"label": "Pressure at maximum winds, $P_m$, [hPa]"}
    )
    for i in range(3):
        for j in range(2):
            if j != 1:
                axs[i, j].set_xlabel("")
            if i != 0:
                axs[i, j].set_ylabel("")
    label_subplots(axs, override="outside")
    # axs[1].plot(ds["lat"], ds["vmax"], "k")
    # axs[2].plot(ds["lat"], ds["pc"] / 100, "k")
    plt.savefig(os.path.join(folder, "gom_bbox_r0_pm_rmax.pdf"))
    print("saving to ", folder + "/gom_bbox_r0_pm_rmax.pdf")

    vars: List[str] = ["t", "q", "vmax", "r0", "pc", "t0"]
    pairplot(ds.isel(p=0)[vars].to_dataframe()[vars])
    plt.savefig(os.path.join(folder, "gom_bbox_pairplot2.pdf"))
    plt.clf()


@timeit
def plot_gom_solns() -> None:
    """Plot the solution timeseries for the Gulf of Mexico."""
    ds = xr.open_dataset(os.path.join(DATA_PATH, "gom_solns.nc"))
    fig, axs = plt.subplots(3, 1, figsize=(6, 8), sharex=True)
    axs[0].plot(ds["year"], ds["r0"] / 1000, "k")
    axs[1].plot(ds["year"], ds["vmax"], "k")
    axs[2].plot(ds["year"], ds["pm"] / 100, "k")
    plt.xlabel("Year")
    axs[0].set_ylabel("Radius of outer winds, $r_a$, [km]")
    axs[1].set_ylabel("Maximum wind speed, $V_{\mathrm{max}}$, [m s$^{-1}$]")
    axs[2].set_ylabel("Pressure at maximum winds, $p_m$, [hPa]")
    label_subplots(axs)
    plt.savefig(os.path.join(FIGURE_PATH, "rmax_time.pdf"))


def plot_and_calc_gom() -> None:
    """Plot the solution curves for different years
    for the Gulf of Mexico."""
    solns = []
    # times = [1850, 1900, 1950, 2000, 2050, 2099]
    times = [int(x) for x in range(1850, 2100, 20)]

    # pick the August average in the data sets
    for time in [str(t) + "-08-15" for t in times]:
        solns += [gom_timestep(time=time, plot=False)]

    solns = np.array(solns)
    print("solns", solns)
    fig, axs = plt.subplots(3, 1, figsize=(6, 8), sharex=True)
    axs[0].plot(times, solns[:, 0] / 1000, "k")
    axs[1].plot(times, solns[:, 1], "k")
    axs[2].plot(times, solns[:, 2] / 100, "k")
    plt.xlabel("Year")
    axs[0].set_ylabel("Radius of outer winds, $r_a$, [km]")
    axs[1].set_ylabel("Maximum wind speed, $V_{\mathrm{max}}$, [m s$^{-1}$]")
    axs[2].set_ylabel("Pressure at maximum winds, $p_m$, [hPa]")
    label_subplots(axs)
    plt.savefig(os.path.join(FIGURE_PATH, "rmax_time.pdf"))


@timeit
def plot_c15_profiles_over_time(marker_size: int = 1, linewidth=0.5) -> None:
    """Plot the profiles over time.

    Args:
        marker_size (int, optional): Marker size. Defaults to 1.
        linewidth ([type], optional): Line width. Defaults to 0.5.
    """

    ds = xr.open_dataset(os.path.join(DATA_PATH, "gom_soln_new.nc"))
    print(ds)
    print(ds["rmax"])
    print(ds["vmax"])
    print(ds["r0"])
    plot_defaults()
    print(ds.time.values)

    fig, axs = plt.subplots(2, 1, sharex=True)
    colors = ["red", "blue"]

    for i, t in enumerate([-2, -60]):  # range(0, len(ds.time.values), 20):
        dst = ds.isel(time=t)
        time = dst.time.values
        ou = profile_from_vals(
            dst["rmax"].values,
            dst["vmax"].values,
            dst["r0"].values,
            p0=dst["msl"].values * 100,
        )
        print("rr", ou["rr"])
        axs[0].plot(
            ou["rr"] / 1000, ou["VV"], color=colors[i], linewidth=linewidth, label=time
        )
        print("vv", ou["VV"])
        axs[0].scatter(dst["r0"].values / 1000, 0, color="red", s=marker_size)
        axs[0].scatter(
            dst["rmax"].values / 1000, dst["vmax"].values, color="red", s=marker_size
        )
        axs[1].plot(
            ou["rr"] / 1000, ou["p"] / 100, color=colors[i], linewidth=linewidth
        )
        print("p", ou["p"])
        axs[1].scatter(
            dst["rmax"].values / 1000,
            dst["pm"].values / 100,
            color="red",
            s=marker_size,
        )
        write_json(ou, os.path.join(DATA_PATH, f"{time}.json"))

    axs[0].set_ylabel("Wind speed, $V$ [m s$^{-1}$]")
    axs[0].legend()
    axs[1].set_ylabel("Pressure, $p$ [hPa]")
    label_subplots(axs)
    plt.xlabel("Radius, $r$, [km]")
    plt.savefig(os.path.join(FIGURE_PATH, "c15_timeseries_profiles.pdf"))
    plt.clf()


if __name__ == "__main__":
    # python -m cle.plot
    # python plot.py
    # plot_gom_bbox()
    # plot_gom_bbox_soln()
    # plot_soln_curves()
    # plot_profiles()
    # plot_from_ds()
    # plot_and_calc_gom()
    # plot_gom_solns()
    # plot_c15_profiles_over_time()
    # plot_and_calc_gom()
    # plot_gom_solns()
    # plot_gom_bbox_soln()
    # plot_soln_curves()
    # plot_profiles()
    # plot_from_ds()
    # ds = xr.open_dataset(os.path.join(DATA_PATH, "gom_soln_new.nc"))
    # print(ds)
    # print([var for var in ds])
    # print(ds["msl"].values)
    figure2()
