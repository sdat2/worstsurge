from typing import Tuple
import numpy as np
from scipy.interpolate import pchip_interpolate
from sithom.time import timeit
from chavas15.er11.radprof_raw import ER11_radprof_raw


@timeit
def ER11_radprof(
    Vmax: float,
    r_in: float,
    rmax_or_r0: str,
    fcor: float,
    CkCd: float,
    rr_ER11: np.ndarray,
) -> Tuple[np.ndarray, float]:
    # find increment in rr_ER11 vector
    dr = rr_ER11[1] - rr_ER11[0]
    print("dr = ", dr)

    # Call ER11_radprof_raw to get velocity profile and the radius not given as input.
    V_ER11, r_out = ER11_radprof_raw(Vmax, r_in, rmax_or_r0, fcor, CkCd, rr_ER11)

    # Calculate error in r_in
    if rmax_or_r0 == "rmax":
        drin_temp = r_in - rr_ER11[np.argmax(V_ER11)]
    elif rmax_or_r0 == "r0":
        drin_temp = r_in - pchip_interpolate(V_ER11[2:], rr_ER11[2:], 0)

    # Calculate error in Vmax
    dVmax_temp = Vmax - np.max(V_ER11)

    # Check if errors are too large and adjust accordingly
    r_in_save = r_in
    Vmax_save = Vmax

    # r_in first
    n_iter = 0
    while (
        abs(drin_temp) > dr / 2 or abs(dVmax_temp / Vmax_save) >= 1e-2 and n_iter < 21
    ):
        #
        # limit to 20 iterations
        n_iter += 1
        if n_iter > 20:
            # Convergence not achieved, return NaNs
            V_ER11 = np.full_like(rr_ER11, np.nan)
            r_out = np.nan

        r_in += drin_temp

        while abs(dVmax_temp / Vmax) >= 1e-2:
            Vmax += dVmax_temp
            # print("Vmax = ", Vmax)
            V_ER11, r_out = ER11_radprof_raw(
                Vmax, r_in, rmax_or_r0, fcor, CkCd, rr_ER11
            )
            Vmax_prof = np.max(V_ER11)
            dVmax_temp = Vmax_save - Vmax_prof

        V_ER11, r_out = ER11_radprof_raw(Vmax, r_in, rmax_or_r0, fcor, CkCd, rr_ER11)
        Vmax_prof = np.max(V_ER11)
        dVmax_temp = Vmax_save - Vmax_prof

        if rmax_or_r0 == "rmax":
            drin_temp = r_in_save - rr_ER11[np.argmax(V_ER11 == Vmax_prof)]

            from matplotlib import pyplot as plt

            plt.plot(rr_ER11, V_ER11, "k")
            plt.plot(r_in, 0, "r*")
            plt.xlabel("$r$ [m]")
            plt.ylabel("$V$ [m/s]")
            plt.title("ER11 inner radial profile, iteration={}".format(n_iter))
            plt.savefig("test/er11_test.pdf")
            plt.clf()
            plt.close()

        elif rmax_or_r0 == "r0":
            drin_temp = r_in_save - pchip_interpolate(V_ER11[2:], rr_ER11[2:], 0)
            from matplotlib import pyplot as plt

            plt.plot(rr_ER11, V_ER11, "k")
            plt.plot(r_in, 0, "r*")
            plt.xlabel("$r$ [m]")
            plt.ylabel("$V$ [m/s]")
            plt.title("ER11 inner radial profile")
            plt.savefig("test/er11_test.pdf")
            plt.clf()
            plt.close()
    return V_ER11, r_out


# Example usage
# V_ER11, r_out = ER11_radprof(Vmax_ER11, r0_ER11, 'r0', fcor, CkCd, rr_mean)

if __name__ == "__main__":
    # python chavas15/er11/radprof.py
    # some made up inputs (not currently working).
    Vmax_ER11 = 80  # [m s-1]
    r0_ER11 = 2500 * 1000  # [m]
    CkCd = 0.9  # [dimensionless]
    fcor = 5e-5  # [s-1]
    rr_mean = np.linspace(1000, 2500 * 1000, num=100)

    V_ER11, r_out = ER11_radprof(Vmax_ER11, r0_ER11, "r0", fcor, CkCd, rr_mean)
