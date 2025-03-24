"""Plot the new potential size calculation results for PIPS chapter/paper"""

import os
from typing import List
import numpy as np
import numpy.ma as ma
import xarray as xr
import matplotlib.pyplot as plt
from sithom.io import write_json
from sithom.plot import feature_grid, label_subplots, plot_defaults, get_dim, pairplot
from sithom.curve import fit
from uncertainties import ufloat
from .constants import DATA_PATH, FIGURE_PATH
from .potential_size import profile_from_stats
from .utils import coriolis_parameter_from_lat


def plot_panels() -> None:
    plot_defaults()

    # initial calculation with Ck/Cd = 1 for C15, gamma =1.2
    example_ds = xr.open_dataset(
        os.path.join(DATA_PATH, "example_potential_size_output_small_2.nc")
    )
    # to km
    del example_ds["time"]  # was annoying to have overly precise time
    example_ds["r0"][:] /= 1000
    example_ds["rmax"][:] /= 1000
    var = [["sst", "vmax"], ["msl", "rmax"], ["t0", "r0"]]
    units = [[r"$^{\circ}$C", r"m s$^{-1}$"], ["hPa", "km"], ["K", "km"]]
    names = [
        ["Sea surface temp., $T_s$", "Potential intensity, $V_p$"],
        ["Sea level pressure, $p_0$", r"Radius max winds, $r_{\mathrm{max}}$"],
        ["Outflow temperature, $T_0$", "Potential size, $r_a$"],
    ]
    cbar_lims = [
        [(28, 33, "cmo.thermal"), None],
        [(1010, 1020, "cmo.dense"), None],
        [(200, 210, "cmo.thermal"), None],
    ]
    super_titles = ["Inputs", "Outputs"]

    xy = [
        ("lon", "Longitude", r"$^{\circ}$E"),
        ("lat", "Latitude", r"$^{\circ}$N"),
    ]

    # pc, pm

    _, axs = feature_grid(
        example_ds, var, units, names, cbar_lims, super_titles, figsize=(6, 6), xy=xy
    )

    label_subplots(axs)

    plt.suptitle("August 2015")

    plt.savefig(os.path.join(FIGURE_PATH, "new_ps_calculation_output_gom.pdf"))


def safe_grad(xt, yt) -> ufloat:
    # get rid of nan values
    xt, yt = xt[~np.isnan(xt)], yt[~np.isnan(xt)]
    xt, yt = xt[~np.isnan(yt)], yt[~np.isnan(yt)]
    # normalize the data between 0 and 10
    xrange = np.max(xt) - np.min(xt)
    yrange = np.max(yt) - np.min(yt)
    xt = (xt - np.min(xt)) / xrange * 10
    yt = (yt - np.min(yt)) / yrange * 10
    # fit the data with linear fit using OLS
    param, _ = fit(xt, yt)  # defaults to y=mx+c fit
    return param[0] * yrange / xrange


def safe_corr(xt, yt):
    corr = ma.corrcoef(ma.masked_invalid(xt), ma.masked_invalid(yt))
    return corr[0, 1]


def _float_to_latex(x, precision=2):
    """
    Convert a float x to a LaTeX-formatted string with the given number of significant figures.

    Args:
        x (float): The number to format.
        precision (int): Number of significant figures (default is 2).

    Returns:
        str: A string like "2.2\\times10^{-6}" or "3.1" (if no exponent is needed).
    """
    # Handle the special case of zero.
    if x == 0:
        return "0"

    # Format the number using general format which automatically uses scientific notation when needed.
    s = f"{x:.{precision}g}"

    # If scientific notation is used, s will contain an 'e'
    if "e" in s:
        mantissa, exp = s.split("e")
        # Convert the exponent string to an integer (this removes any extra zeros)
        exp = int(exp)
        # Choose the multiplication symbol.
        mult = "\\times"
        return f"{mantissa}{mult}10^{{{exp}}}"
    else:
        # If no exponent is needed, just return the number inside math mode.
        return f"{s}"


def _m_to_text(m):
    if m.s in (np.nan, np.inf, -np.inf):
        if m.s not in (np.nan, np.inf, -np.inf):
            return "$m={:}$".format(_float_to_latex(m))
        else:
            return "NaN"
    else:
        if m.n > 1000 or m.n < 0.1:
            return "$m={:.1eL}$".format(m)
        else:
            return "$m={:.2L}$".format(m)


def timeseries_plot(
    name: str = "new_orleans",
    plot_name: str = "New Orleans",
    years: List[int] = [2025, 2097],
    members: List[int] = [4, 10, 11],
) -> None:
    # plot CESM2 ensemble members for ssp585 near New Orleans
    plot_defaults()
    colors = ["purple", "green", "orange"]
    file_names = [
        os.path.join(DATA_PATH, f"{name}_august_ssp585_r{member}i1p1f1.nc")
        for member in members
    ]
    ds_l = [xr.open_dataset(file_name) for file_name in file_names]
    _, axs = plt.subplots(4, 1, sharex=True, figsize=get_dim(ratio=1.5))
    vars = ["sst", "vmax", "rmax", "r0"]
    var_labels = [
        "Sea surface temp., $T_s$",
        "Potential intensity, $V_p$",
        r"Radius max winds, $r_{\mathrm{max}}$",
        "Potential size, $r_a$",
    ]
    units = ["$^{\circ}$ C", "m s$^{-1}$", "km", "km"]

    for i, var in enumerate(vars):
        for j, ds in enumerate(ds_l):
            ds_l[j][var].attrs["long_name"] = var_labels[i]
            ds_l[j][var].attrs["units"] = units[i]

    for i, var in enumerate(vars):
        for j, ds in enumerate(ds_l):
            x = np.array([time.year for time in ds.time.values])
            y = ds[var].values
            if var == "rmax" or var == "r0":
                y /= 1000  # divide by 1000 to go to km
            axs[i].plot(x, y, color=colors[j], label=f"r{members[j]}i1p1f1")
            m = safe_grad(x, y)
            rho = safe_corr(x, y)
            corr_bit = f"ρ = {rho:.2f}"
            m_bit = _m_to_text(m) + " " + units[i] + " yr$^{-1}$"
            print(f"r{members[j]}i1p1f1 " + var + " " + corr_bit + ", " + m_bit)
            axs[i].annotate(
                corr_bit + ", " + m_bit,
                xy=(0.44, 0.21 - j * 0.1),
                xycoords=axs[i].transAxes,
                color=colors[j],
            )

        axs[i].set_xlabel("")
        axs[i].set_ylabel(var_labels[i] + " [" + units[i] + "]")
        if i == len(vars) - 1:
            axs[i].legend()
            axs[i].set_xlabel("Year [A.D.]")
    axs[2].set_xlim(2015, 2100)
    label_subplots(axs)
    axs[0].set_title(f"{plot_name} CESM2 SSP585")
    plt.legend(loc="lower center", bbox_to_anchor=(0.5, -0.5), ncol=3)
    plt.savefig(os.path.join(FIGURE_PATH, f"{name}_timeseries.pdf"))
    plt.clf()
    colors = ["Green", "Blue"]
    vars = ["p", "VV"]
    var_labels = ["Pressure [hPa]", "Velocity [m s$^{-1}$]"]
    plot_defaults()
    for j, member in enumerate(members):
        fig, axs = plt.subplots(2, 1, sharex=True)
        for k, year in enumerate(years):
            tp = ds_l[j].isel(time=[t.year == year for t in ds_l[j].time.values])
            vmax = float(tp.vmax.values.ravel())
            fcor = float(coriolis_parameter_from_lat(tp.lat.values.ravel()))
            r0 = float(tp.r0.values.ravel()) * 1000  # back to m
            p0 = float(tp.msl.values.ravel())  # hPa
            if not np.isnan(vmax) and not np.isnan(r0):
                profile = profile_from_stats(
                    vmax,
                    fcor,
                    r0,
                    p0,
                )
                write_json(
                    profile,
                    os.path.join(
                        DATA_PATH, f"{year}_{name}_profile_r{member}i1p1f1.json"
                    ),
                )
                for i, var in enumerate(vars):
                    axs[i].plot(
                        np.array(profile["rr"]) / 1000,
                        profile[var],
                        color=colors[k],
                        label=f"August {year}",
                    )
                    if k == 0:
                        axs[i].set_ylabel(var_labels[i])
        label_subplots(axs)
        plt.legend(ncols=2)
        plt.xlabel("Radius [km]")
        plt.savefig(
            os.path.join(
                FIGURE_PATH,
                f"{name}_profiles_{years[0]}_{years[1]}_r{member}i1p1f1.pdf",
            )
        )
        plt.clf()

    vars = ["sst", "vmax", "rmax", "r0"]
    for j, member in enumerate(members):
        del ds_l[j]["time"]
        _, axs = pairplot(ds_l[j][vars], label=True)
        plt.savefig(os.path.join(FIGURE_PATH, f"{name}_pairplot_r{member}i1p1f1.pdf"))
        plt.clf()


def plot_seasonal_profiles():
    """
    Plot the seasonal profiles for New Orleans.
    """
    in_path = os.path.join(DATA_PATH, "new_orleans_10year3.nc")
    ds = xr.open_dataset(in_path)
    # plot season for msl, rh,  sst, t0, vmax, rmax, r0
    # shared x -axis = months
    # seperate y-axes = values
    plt.figure(figsize=(6, 6))
    var = ["msl", "rh", "sst", "t0", "vmax", "rmax", "r0"]
    var_labels = [
        "Sea level pressure, $p_a$",
        r"Relative humidity, $\mathcal{H}_e$",
        "Sea surface temperature, $T_s$",
        "Outflow temperature, $T_0$",
        r"Potential intensity, $V_{p}$",
        "Radius of maximum winds, $r_{\max}$",
        "Potential size, $r_a$",
    ]
    # only symbols to save space
    var_labels = [
        "$p_a$",
        r"$\mathcal{H}_e$",
        "$T_s$",
        "$T_0$",
        r"$V_{p}$",
        "$r_{\max}$",
        "$r_a$",
    ]
    ds["rh"] *= 100
    ds["rmax"] /= 1000
    ds["r0"] /= 1000
    ds["t0"] -= 273.15
    # units = ["fraction", "K", "m s$^{-1}$", "hPa", "$^{\circ}$C"]
    units = ["hPa", "%", r"$^{\circ}$C", r"$^{\circ}$C", r"m s$^{-1}$", "km", "km"]
    fig, axs = plt.subplots(len(var), 1, figsize=get_dim(ratio=1.5), sharex=True)

    # 10 dark colors
    colors = [
        "black",
        "red",
        "green",
        "blue",
        "purple",
        "orange",
        "brown",
        "pink",
        "gray",
        "cyan",
    ]
    for i, v in enumerate(var):
        for j in range(10):
            axs[i].plot(
                ds[v].values[j * 12 : (j + 1) * 12], linewidth=0.5, color=colors[j]
            )
        axs[i].set_ylabel(var_labels[i] + " [" + units[i] + "]")
        # blank x ticks axs[i].set_xticks([])
        # get error message now with new version of matplotlib

    axs[-1].set_xlabel("Month")
    months = [
        "Jan",
        "Feb",
        "Mar",
        "Aug",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ]
    axs[-1].set_xticks(
        np.arange(0, 12),
        months,
    )
    plt.xlim(0, 11)
    label_subplots(axs)
    plt.tight_layout()
    plt.savefig(os.path.join(FIGURE_PATH, "new_orleans_seasons.pdf"))
    plt.clf()
    plt.close()
    # let's plot the temperature profile and humidity profile
    fig, axs = plt.subplots(1, 2, figsize=get_dim(ratio=0.7), sharey=True)
    # four dark colors
    colors = ["black", "red", "green", "blue"]
    # ds["t"] -= 273.15 # OC has already been taken away
    for i, j in enumerate(list(range(0, 12, 3))):
        k = (j - 2) % 12
        ids = ds.isel(time=k)
        axs[0].plot(
            ids["t"].values,
            ids["p"].values,
            color=colors[i],
            linewidth=0.5,
            label=months[k],
        )
        axs[0].scatter(ids["t0"].values, ids["otl"].values, color=colors[i], marker="x")
        axs[1].plot(ids["q"].values, ids["p"].values, color=colors[i], linewidth=0.5)

    axs[0].set_ylabel("Pressure level [hPa]")
    axs[0].set_xlabel(r"Temperature [$^{\circ}$C]")
    axs[1].set_xlabel("Specific humidity [g/kg]")
    label_subplots(axs, override="outside")
    axs[0].legend()
    # set a legend above the plot
    # axs[0].legend(loc="lower center", bbox_to_anchor=(1, 1.1))
    # reverse the y-axis
    axs[0].invert_yaxis()
    axs[0].set_ylim(1000, 0)  # between 0 and 1000 hPa
    plt.tight_layout()
    plt.savefig(os.path.join(FIGURE_PATH, "new_orleans_vertical_profiles.pdf"))
    plt.clf()
    plt.close()


def figure_two() -> None:
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
    print("two lats", ds["sst"].isel(lat=slice(0, 2)).values.shape)
    vmaxs = ds["vmax"].values
    lats = ds["lat"].values
    ssts = ds["sst"].values
    r0s = ds["r0"].values

    print("vmaxs", vmaxs.shape)
    print("lats", lats.shape)
    print("ssts", ssts.shape)
    print("r0s", r0s.shape)
    lats = np.array([lats.tolist() for _ in range(len(ds.lon))]).T
    assert np.shape(lats) == np.shape(ssts)
    ssts = ssts.ravel()
    r0s = r0s.ravel()
    lats = lats.ravel()
    vmaxs = vmaxs.ravel()
    lats = lats[~np.isnan(ssts)]
    r0s = r0s[~np.isnan(ssts)]
    vmaxs = vmaxs[~np.isnan(ssts)]
    ssts = ssts[~np.isnan(ssts)]
    rho = safe_corr(lats, ssts)
    fit_space_sst_lat, _ = fit(lats, ssts)
    print(
        "space (sst, lat) $m={:.1eL}$ ".format(fit_space_sst_lat[0])
        + "$^{\circ}$C  $^{\circ}$N$^{-1}$",
    )
    print("space rho (sst, lat): {:.2f}".format(rho))
    lats = lats[~np.isnan(r0s)]
    ssts = ssts[~np.isnan(r0s)]
    vmaxs = vmaxs[~np.isnan(r0s)]
    coriolis_fs = coriolis_parameter_from_lat(lats)
    r0s = r0s[~np.isnan(r0s)]
    fit_space_r0s_lats = safe_grad(lats, r0s / 1000)
    print(
        "space (r0s, lat) $m={:.2eL}$ ".format(fit_space_r0s_lats[0])
        + "km  $^{\circ}$N$^{-1}$",
    )
    rho = safe_corr(lats, r0s)
    print("space rho (r0s, lat): {:.2f}".format(rho))

    ssts = ssts[~np.isnan(vmaxs)]
    coriolis_fs = coriolis_fs[~np.isnan(vmaxs)]
    vmaxs = vmaxs[~np.isnan(vmaxs)]
    fit_space_vmaxs_lats = safe_grad(lats, vmaxs)
    print(
        "space (vmax, lat) $m={:.1eL}$ ".format(fit_space_vmaxs_lats)
        + "m s$^{-1}$  $^{\circ}$N$^{-1}$",
    )
    fit_space_vmaxs_ssts = safe_grad(ssts, vmaxs)
    print(
        "space (vmax, sst) $m={:.1eL}$ ".format(fit_space_vmaxs_ssts)
        + "m s$^{-1}$  $^{\circ}$C$^{-1}$",
    )
    rho = safe_corr(ssts, vmaxs)
    print("space rho (sst, vmax): {:.2f}".format(rho))
    vmax_div_coriolis = vmaxs / coriolis_fs
    rho = safe_grad(vmax_div_coriolis, r0s)
    print("space rho (vmax/coriolis, r0): {:.2f}".format(rho))
    fit_space_vmaxs_div_coriolis_r0 = save_grad(vmax_div_coriolis, r0s)

    print(
        "space (vmax/coriolis, r0) $m={:.2eL}$ ".format(fit_space_vmaxs_div_coriolis_r0)
        + "km m$^{-1}$ s$^2$$",
    )

    timeseries_ds = xr.open_dataset(
        os.path.join(DATA_PATH, "new_orleans_august_ssp585_r4i1p1f1.nc")
    )
    (ds["r0"] / 1000).plot(ax=axs[1, 0], cbar_kwargs={"label": ""})
    axs[1, 0].set_title("Potential size, $r_a$ [km]")
    axs[1, 1].set_title("Potential size, $r_a$ [km]")
    ds["vmax"].plot(ax=axs[0, 0], cbar_kwargs={"label": ""})
    axs[0, 0].scatter(GOM[1], GOM[0], color="black", s=30, marker="x")
    axs[1, 0].scatter(GOM[1], GOM[0], color="black", s=30, marker="x")
    axs[0, 0].set_title("Potential intensity, $V_{p}$ [m s$^{-1}$]")
    axs[0, 1].set_title("Potential intensity, $V_{p}$ [m s$^{-1}$]")

    ## work out correlation between time and vmax between 2000 and 2099
    year_min = 2014
    year_max = 2100
    ssts = timeseries_ds["sst"].sel(time=slice(year_min, year_max)).values
    vmaxs = timeseries_ds["vmax"].sel(time=slice(year_min, year_max)).values
    r0s = timeseries_ds["r0"].sel(time=slice(year_min, year_max)).values
    years = timeseries_ds["time"].sel(time=slice(year_min, year_max)).values
    rho_vmax = safe_corr(vmaxs, years)
    rho_r0 = safe_corr(r0s, years)
    rho_sst = safe_corr(ssts, years)
    rho_sst_vmax = safe_corr(ssts, vmaxs)
    rho_sst_r0 = safe_corr(ssts, r0s)
    print("rho_sst_vmax", rho_sst_vmax)
    print("rho_sst_r0", rho_sst_r0)
    print("rho_sst", rho_sst)

    axs[0, 1].text(0.8, 0.9, f"$\\rho$ = {rho_vmax:.2f}", transform=axs[0, 1].transAxes)
    axs[1, 1].text(0.8, 0.9, f"$\\rho$ = {rho_r0:.2f}", transform=axs[1, 1].transAxes)

    # work out gradient with error bars for same period
    fit_vmax = safe_grad(years, vmaxs)
    fit_r0 = safe_grad(years, r0s / 1000)
    fit_r0_sst = safe_grad(ssts, r0s / 1000)
    print("fit_r0_sst timeseries", fit_r0_sst, "km $^{\circ}$C$^{-1}$")
    fit_vmax_sst = safe_grad(ssts, vmaxs)
    print("fit_vmax_sst timeseries", fit_vmax_sst, "m s$^{-1}$C$ ^{-1}$")

    axs[0, 1].text(
        0.66,
        0.05,
        f"$m=$  " + "${:.1eL}$".format(fit_vmax[0]) + "\n \t\t\t m s$^{-1}$ yr$^{-1}$",
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
    plt.savefig(os.path.join(folder, "figure_two.pdf"))
    plt.clf()
    print(timeseries_ds)


if __name__ == "__main__":
    # python -m w22.plot
    # plot_panels()
    # figure_two()
    plot_seasonal_profiles()
    # years = [2015, 2100]
    # timeseries_plot(
    #     name="new_orleans",
    #     plot_name="New Orleans",
    #     years=years,
    #     members=[4, 10],
    # )
    # timeseries_plot(name="miami", plot_name="Miami", years=years, members=[4, 10])
    # timeseries_plot(
    #     name="galverston",
    #     plot_name="Galverston",
    #     years=years,
    #     members=[4, 10],
    # )
