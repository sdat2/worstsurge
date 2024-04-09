"""Run the CLE15 model with json files."""

from typing import Callable, Tuple, Optional, Dict
import os
import numpy as np
from scipy.interpolate import interp1d
from matplotlib import pyplot as plt
from oct2py import Oct2Py, get_log
from sithom.io import read_json, write_json
from sithom.plot import plot_defaults
from sithom.time import timeit
from chavas15.intersect import curveintersect
from .constants import (
    TEMP_0K,
    BACKGROUND_PRESSURE,
    DEFAULT_SURF_TEMP,
    DATA_PATH,
    FIGURE_PATH,
    SRC_PATH,
)

plot_defaults()

os.environ["OCTAVE_CLI_OPTIONS"] = str(
    "--no-gui --no-gui-libs"  # disable gui to improve performance
)
oc = Oct2Py(logger=get_log())
oc.eval(f"addpath(genpath('{os.path.join(SRC_PATH, 'mcle')}'))")
# oc.addpath(".")
# oc.addpath("mfiles/")
# path = "/Users/simon/tcpips/cle/"
# oc.addpath("/Users/simon/tcpips/cle/")
# oc.addpath("/Users/simon/tcpips/cle/mfiles")
# oc.eval("addpath(genpath('.'))")
# oc.eval("addpath(genpath('mfiles/'))")
# print("dir", dir(oc))


@timeit
def _run_cle15_oct2py(
    **kwargs,
) -> dict:  # Tuple[np.ndarray, np.ndarray, float, float, float]:
    """
    Run the CLE15 model using oct2py.

    Returns:
        dict: dict(rr=rr, VV=VV, rmax=rmax, rmerge=rmerge, Vmerge=Vmerge)
    """
    in_dict = read_json(os.path.join(DATA_PATH, "inputs.json"))
    in_dict.update(kwargs)
    # print(in_dict)
    # oc.eval("path")
    rr, VV, rmax, rmerge, Vmerge = oc.feval(
        "ER11E04_nondim_r0input",
        in_dict["Vmax"],
        in_dict["r0"],
        in_dict["fcor"],
        in_dict["Cdvary"],
        in_dict["Cd"],
        in_dict["w_cool"],
        in_dict["CkCdvary"],
        in_dict["CkCd"],
        in_dict["eye_adj"],
        in_dict["alpha_eye"],
        nout=5,
    )
    return dict(rr=rr, VV=VV, rmax=rmax, rmerge=rmerge, Vmerge=Vmerge)


@timeit
def _run_cle15_octave(inputs: dict, execute: bool) -> dict:
    """
    Run the CLE15 model using octave.

    Args:
        inputs (dict): Input parameters.
        execute (bool): Whether to execute the model.

    Returns:
        dict: dict(rr=rr, VV=VV, rmax=rmax, rmerge=rmerge, Vmerge=Vmerge)
    """

    ins = read_json(os.path.join(DATA_PATH, "inputs.json"))
    if inputs is not None:
        for key in inputs:
            if key in ins:
                ins[key] = inputs[key]

    # Storm parameters
    write_json(ins, os.path.join(DATA_PATH, "inputs.json"))

    # run octave file r0_pm.m
    if execute:
        # disabling gui leads to one order of magnitude speedup
        # also the pop-up window makes me feel sick due to the screen moving about.
        os.system(
            f"octave --no-gui --no-gui-libs {os.path.join(SRC_PATH, 'mcle', 'r0_pm.m')}"
        )

    # read in the output from r0_pm.m
    return read_json(os.path.join(DATA_PATH, "outputs.json"))


def pressure_from_wind(
    rr: np.ndarray,  # [m]
    vv: np.ndarray,  # [m/s]
    p0: float = 1015 * 100,  # Pa
    rho0: float = 1.15,  # kg m-3
    fcor: float = 5e-5,  # m s-2
) -> np.ndarray:  # [Pa]
    """
    Use coriolis force and pressure gradient force to find physical
    pressure profile to correspond to the velocity profile.

    TODO: decrease air density in response to decreased pressure (will make central pressure lower).

    Args:
        rr (np.ndarray): radii array [m].
        vv (np.ndarray): velocity array [m/s]
        p0 (float): ambient pressure [Pa].
        rho0 (float): Air density at ambient pressure [kg/m3].
        fcor (float): Coriolis force.

    Returns:
        np.ndarray: Pressure array [Pa].
    """
    p = np.zeros(rr.shape)  # [Pa]
    # rr ascending
    assert np.all(rr == np.sort(rr))
    p[-1] = p0
    for j in range(len(rr) - 1):
        i = -j - 2
        # Assume Coriolis force and pressure-gradient balance centripetal force.
        # delta P = - rho * ( v^2/r + fcor * vv[i] ) * delta r
        p[i] = p[i + 1] - rho0 * (
            vv[i] ** 2 / (rr[i + 1] / 2 + rr[i] / 2) + fcor * vv[i]
        ) * (rr[i + 1] - rr[i])
        # centripetal pushes out, pressure pushes inward, coriolis pushes inward
    return p  # pressure profile [Pa]


@timeit
def run_cle15(
    execute: bool = True,
    plot: bool = False,
    inputs: Optional[Dict[str, any]] = None,
    oct2py: bool = True,
) -> Tuple[float, float, float, float]:  # pm, rmax, vmax, pc
    """
    Run the CLE15 model.

    Args:
        execute (bool, optional): Execute the model. Defaults to True.
        plot (bool, optional): Plot the output. Defaults to False.
        inputs (Optional[Dict[str, any]], optional): Input parameters. Defaults to None.
        oct2py (bool, optional): Use oct2py. Defaults to False.

    Returns:
        Tuple[float, float, float, float]: pm [Pa], rmax [m], vmax [m/s], pc [Pa]
    """

    if oct2py:  # should be faster if graphical element disabled
        ou = _run_cle15_oct2py(inputs)
    else:
        ou = _run_cle15_octave(inputs, execute)
    ins = read_json(os.path.join(DATA_PATH, "inputs.json"))

    if plot:
        # print(ou)
        # plot the output
        rr = np.array(ou["rr"]) / 1000
        rmerge = ou["rmerge"] / 1000
        vv = np.array(ou["VV"])
        plt.plot(rr[rr < rmerge], vv[rr < rmerge], "g", label="ER11 inner profile")
        plt.plot(rr[rr > rmerge], vv[rr > rmerge], "orange", label="E04 outer profile")
        plt.plot(
            ou["rmax"] / 1000, ins["Vmax"], "b.", label="$r_{\mathrm{max}}$ (output)"
        )
        plt.plot(
            ou["rmerge"] / 1000,
            ou["Vmerge"],
            "kx",
            label="$r_{\mathrm{merge}}$ (input)",
        )
        plt.plot(ins["r0"] / 1000, 0, "r.", label="$r_a$ (input)")

        def _f(x: any) -> float:
            if isinstance(x, float):
                return x
            else:
                return np.nan

        plt.ylim(
            [0, np.nanmax([_f(v) for v in vv]) * 1.10]
        )  # np.nanmax(out["VV"]) * 1.05])
        plt.legend()
        plt.xlabel("Radius, $r$, [km]")
        plt.ylabel("Rotating wind speed, $V$, [m s$^{-1}$]")
        plt.title("CLE15 Wind Profile")
        plt.savefig(os.path.join(FIGURE_PATH, "r0_pm.pdf"), format="pdf")
        plt.clf()

    # integrate the wind profile to get the pressure profile
    # assume wind-pressure gradient balance
    p0 = ins["p0"] * 100  # [Pa]
    rho0 = 1.15  # [kg m-3]
    rr = np.array(ou["rr"])  # [m]
    vv = np.array(ou["VV"])  # [m/s]
    p = pressure_from_wind(rr, vv, p0=p0, rho0=rho0, fcor=ins["fcor"])  # [Pa]

    if plot:
        plt.plot(rr / 1000, p / 100, "k")
        plt.xlabel("Radius, $r$, [km]")
        plt.ylabel("Pressure, $p$, [hPa]")
        plt.title("CLE15 Pressure Profile")
        plt.ylim([np.min(p) / 100, np.max(p) * 1.0005 / 100])
        plt.xlim([0, rr[-1] / 1000])
        plt.savefig(os.path.join(FIGURE_PATH, "r0_pmp.pdf"), format="pdf")
        plt.clf()

    # plot the pressure profile

    return (
        interp1d(rr, p)(
            ou["rmax"]
        ),  # find the pressure at the maximum wind speed radius [Pa]
        ou["rmax"],  # rmax radius [m]
        ins["Vmax"],  # maximum wind speed [m/s]
        p[0],
    )  # p[0]  # central pressure [Pa]


def wang_diff(
    a: float = 0.062, b: float = 0.031, c: float = 0.008
) -> Callable[[float], float]:
    """
    Wang difference function.

    Args:
        a (float, optional): a. Defaults to 0.062.
        b (float, optional): b. Defaults to 0.031.
        c (float, optional): c. Defaults to 0.008.

    Returns:
        Callable[[float], float]: Function to find root of.
    """

    def f(y: float) -> float:  # y = exp(a*y + b*log(y)*y + c)
        return y - np.exp(a * y + b * np.log(y) * y + c)

    return f


@timeit
def bisection(f: Callable, left: float, right: float, tol: float) -> float:
    """
    Bisection numerical method.

    https://en.wikipedia.org/wiki/Root-finding_algorithms#Bisection_method

    Args:
        f (Callable): Function to find root of.
        left (float): Left boundary.
        right (float): Right boundary.
        tol (float): tolerance for convergence.

    Returns:
        float: x such that |f(x)| < tol.
    """
    fleft = f(left)
    fright = f(right)
    if fleft * fright > 0:
        print("Error: f(left) and f(right) must have opposite signs.")
        return np.nan

    while fleft * fright < 0 and right - left > tol:
        mid = (left + right) / 2
        fmid = f(mid)
        if fleft * fmid < 0:
            right = mid
            fright = fmid
        else:
            left = mid
            fleft = fmid
    return (left + right) / 2


def buck(temp: float) -> float:  # temp in K -> saturation vapour pressure in Pa
    """
    Arden Buck equation.

    https://en.wikipedia.org/wiki/Arden_Buck_equation

    Args:
        temp (float): temperature in Kelvin.

    Returns:
        float: saturation vapour pressure in Pa.
    """
    # https://en.wikipedia.org/wiki/Arden_Buck_equation
    temp: float = temp - TEMP_0K  # convert from degK to degC
    return 0.61121 * np.exp((18.678 - temp / 234.5) * (temp / (257.14 + temp))) * 1000


def carnot(temp_hot: float, temp_cold: float) -> float:
    """
    Calculate carnot factor.

    Args:
        temp_hot (float): Temperature of hot reservoir [K].
        temp_cold (float): Temperature of cold reservoir [K].

    Returns:
        float: Carnot factor [dimensionless].
    """
    return (temp_hot - temp_cold) / temp_hot


def absolute_angular_momentum(v: float, r: float, f: float) -> float:
    """
    Calculate absolute angular momentum.

    Args:
        v (float): Azimuthal wind speed [m/s].
        r (float): Radius from storm centre [m].
        f (float): Coriolis parameter [s-1].

    Returns:
        float: Absolute angular momentum [m2/s].
    """
    return v * r + 0.5 * f * r**2  # [m2/s]


def wang_consts(
    near_surface_air_temperature: float = 299,  # K
    outflow_temperature: float = 200,  # K
    latent_heat_of_vaporization: float = 2.27e6,  # J/kg
    gas_constant_for_water_vapor: float = 461,  # J/kg/K
    gas_constant: float = 287,  # J/kg/K
    beta_lift_parameterization: float = 1.25,  # dimensionless
    efficiency_relative_to_carnot: float = 0.5,  # dimensionless
    pressure_dry_at_inflow: float = 985 * 100,  # Pa
    coriolis_parameter: float = 5e-5,  # s-1
    maximum_wind_speed: float = 83,  # m/s
    radius_of_inflow: float = 2193 * 1000,  # m
    radius_of_max_wind: float = 64 * 1000,  # m
) -> Tuple[float, float, float]:  # a, b, c
    """
    Wang carnot engine model parameters.

    Args:
        near_surface_air_temperature (float, optional): Defaults to 299 [K].
        outflow_temperature (float, optional): Defaults to 200 [K].
        latent_heat_of_vaporization (float, optional): Defaults to 2.27e6 [J/kg].
        gas_constant_for_water_vapor (float, optional): Defaults to 461 [J/kg/K].
        gas_constant (float, optional): Defaults to 287 [J/kg/K].
        beta_lift_parameterization (float, optional): Defaults to 1.25 [dimesionless].
        efficiency_relative_to_carnot (float, optional): Defaults to 0.5 [dimensionless].
        pressure_dry_at_inflow (float, optional): Defaults to 985 * 100 [Pa].
        coriolis_parameter (float, optional): Defaults to 5e-5 [s-1].
        maximum_wind_speed (float, optional): Defaults to 83 [m/s].
        radius_of_inflow (float, optional): Defaults to 2193 * 1000 [m].
        radius_of_max_wind (float, optional): Defaults to 64 * 1000 [m].

    Returns:
        Tuple[float, float, float]: a, b, c
    """
    # a, b, c
    absolute_angular_momentum_at_vmax = absolute_angular_momentum(
        maximum_wind_speed, radius_of_max_wind, coriolis_parameter
    )
    carnot_efficiency = carnot(near_surface_air_temperature, outflow_temperature)
    near_surface_saturation_vapour_presure = buck(near_surface_air_temperature)

    return (
        (
            near_surface_saturation_vapour_presure
            / pressure_dry_at_inflow
            * (
                efficiency_relative_to_carnot
                * carnot_efficiency
                * latent_heat_of_vaporization
                / gas_constant_for_water_vapor
                / near_surface_air_temperature
                - 1
            )
            / (
                (
                    beta_lift_parameterization
                    - efficiency_relative_to_carnot * carnot_efficiency
                )
            )
        ),
        (
            near_surface_saturation_vapour_presure
            / pressure_dry_at_inflow
            / (
                beta_lift_parameterization
                - efficiency_relative_to_carnot * carnot_efficiency
            )
        ),
        (
            beta_lift_parameterization
            * (
                0.5 * maximum_wind_speed**2
                - 0.25 * coriolis_parameter**2 * radius_of_inflow**2
                + 0.5 * coriolis_parameter * absolute_angular_momentum_at_vmax
            )
            / (
                (
                    beta_lift_parameterization
                    - efficiency_relative_to_carnot * carnot_efficiency
                )
                * near_surface_air_temperature
                * gas_constant
            )
        ),
    )


def find_solution_rmaxv(
    vmax_pi: float = 86,  # m/s
    coriolis_parameter: float = 5e-5,  # s-1
    background_pressure: float = BACKGROUND_PRESSURE,  # Pa
    near_surface_air_temperature: float = DEFAULT_SURF_TEMP,  # K
    w_cool: float = 0.002,
    outflow_temperature: float = 200,  # K
    supergradient_factor: float = 1.2,  # dimensionless
    plot: bool = False,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Find the solution for rmax and vmax.

    Args:
        vmax_pi (float, optional): Maximum wind speed. Defaults to 86 m/s.
        coriolis_parameter (float, optional): Coriolis parameter. Defaults to 5e-5 s-1.
        background_pressure (float, optional): Background pressure. Defaults to 1015 hPa.
        near_surface_air_temperature (float, optional): Near surface air temperature. Defaults to 299 K.
        w_cool (float, optional): Cooling rate. Defaults to 0.002.
        outflow_temperature (float, optional): Outflow temperature. Defaults to 200 K.
        supergradient_factor (float, optional): Supergradient factor. Defaults to 1.2.
        plot (bool, optional): Plot the output. Defaults to False.

    Returns:
        Tuple[float, float, float]: rmax, vmax_pi, pm
    """
    r0s = np.linspace(200, 5000, num=30) * 1000
    pcs = []
    pcw = []
    rmaxs = []
    for r0 in r0s:
        pm_cle, rmax_cle, vmax, pc = run_cle15(
            plot=False,
            inputs={
                "r0": r0,
                "Vmax": vmax_pi,
                "w_cool": w_cool,
                "fcor": coriolis_parameter,
                "p0": background_pressure / 100,
            },
        )

        ys = bisection(
            wang_diff(
                *wang_consts(
                    radius_of_max_wind=rmax_cle,
                    radius_of_inflow=r0,
                    maximum_wind_speed=vmax * supergradient_factor,
                    coriolis_parameter=coriolis_parameter,
                    pressure_dry_at_inflow=background_pressure
                    - buck(near_surface_air_temperature),
                    near_surface_air_temperature=near_surface_air_temperature,
                    outflow_temperature=outflow_temperature,
                )
            ),
            0.9,
            1.2,
            1e-6,
        )
        # convert solution to pressure
        pm_car = (background_pressure - buck(near_surface_air_temperature)) / ys + buck(
            near_surface_air_temperature
        )

        pcs.append(pm_cle)
        pcw.append(pm_car)
        rmaxs.append(rmax_cle)
        print("r0, rmax_cle, pm_cle, pm_car", r0, rmax_cle, pm_cle, pm_car)
    pcs = np.array(pcs)
    pcw = np.array(pcw)
    rmaxs = np.array(rmaxs)
    intersect = curveintersect(r0s, pcs, r0s, pcw)

    if plot:
        plt.plot(r0s / 1000, pcs / 100, "k", label="CLE15")
        plt.plot(r0s / 1000, pcw / 100, "r", label="W22")
        print("intersect", intersect)
        # plt.plot(intersect[0][0] / 1000, intersect[1][0] / 100, "bx", label="Solution")
        plt.xlabel("Radius, $r_a$, [km]")
        plt.ylabel("Pressure at maximum winds, $p_m$, [hPa]")
        if len(intersect) > 0:
            plt.plot(
                intersect[0][0] / 1000, intersect[1][0] / 100, "bx", label="Solution"
            )
        plt.legend()
        plt.savefig(os.path.join(FIGURE_PATH, "r0_pc_rmaxadj.pdf"))
        plt.clf()
        plt.plot(r0s / 1000, rmaxs / 1000, "k")
        plt.xlabel("Radius, $r_a$, [km]")
        plt.ylabel("Radius of maximum winds, $r_m$, [km]")
        plt.savefig(os.path.join(FIGURE_PATH, "r0_rmax.pdf"))
        plt.clf()
        run_cle15(inputs={"r0": intersect[0][0], "Vmax": vmax_pi}, plot=True)
    return intersect[0][0], vmax_pi, intersect[1][0]  # rmax, vmax, pm


if __name__ == "__main__":
    # python -m cle.find
    # find_solution()
    # find_solution_rmaxv()
    # calc_solns_for_times(num=50)
    # plot_gom_solns()
    # ds_solns(num=2, verbose=True, ds_name="gom_soln_2.nc")
    # plot_from_ds()  # ds_name="gom_soln_2.nc")
    # plot_soln_curves()
    # plot_gom_bbox()
    # ds_solns(num=50, verbose=True, ds_name="data/gom_soln_new.nc")
    # find_solution_rmaxv()

    # from timeit import timeit

    for _ in range(10):
        _run_cle15_oct2py()

    for _ in range(10):
        _run_cle15_octave({}, True)
