import numpy as np
from scipy.interpolate import interp1d
from chavas15.e04.outerwind_r0input_MM0 import E04_outerwind_r0input_nondim_MM0
from chavas15.er11.radprof import ER11_radprof
from chavas15.intersect import curveintersect


def ER11E04_nondim_r0input(
    Vmax, r0, fcor, Cdvary, C_d, w_cool, CkCdvary, CkCd, eye_adj, alpha_eye
):
    fcor = abs(fcor)

    # Overwrite CkCd if want varying (quadratic fit to Vmax from Chavas et al. 2015)
    if CkCdvary == 1:
        CkCd_coefquad = 5.5041e-04
        CkCd_coeflin = -0.0259
        CkCd_coefcnst = 0.7627
        CkCd = CkCd_coefquad * Vmax**2 + CkCd_coeflin * Vmax + CkCd_coefcnst

    if CkCd > 1.9:
        CkCd = 1.9
        print("Ck/Cd is capped at 1.9 and has been set to this value.")

    # Step 1: Calculate E04 M/M0 vs. r/r0
    Nr = 100000
    # Define the function E04_outerwind_r0input_nondim_MM0
    rrfracr0_E04, MMfracM0_E04 = E04_outerwind_r0input_nondim_MM0(
        r0, fcor, Cdvary, C_d, w_cool, Nr
    )

    M0_E04 = 0.5 * fcor * r0**2

    # Step 2: Converge rmaxr0 geometrically until ER11 M/M0 has tangent point with E04 M/M0
    # This step involves several iterations and calls to other functions like ER11_radprof
    # The detailed implementation of this step will depend on the logic and calculation specifics of the original MATLAB code

    soln_converged = False
    while not soln_converged:
        # break up into 3 points, take 2 between which intersection vanishes, repat until this converges.
        rmaxr0_min = 0.001
        rmaxr0_max = 0.75
        rmaxr0_new = (rmaxr0_max + rmaxr0_min) / 1  # guess middle
        rmaxr0 = rmaxr0_new
        drmaxr0 = rmaxr0_max - rmaxr0
        drmaxr0_thresh = 1e-6
        i = 0
        rfracrm_min = 0  # [dimensionless] # start at r=0
        rfracrm_max = 50  # [dimensionless] # many rmaxs away
        while abs(drmaxr0) >= drmaxr0_thresh:
            i += 1
            rmax = rmaxr0_new * r0
            drfacrm = 0.01
            if rmax > 100 * 1000:  # large storm > 100km to rmax
                drfracrm = drfracrm / 10  # extra precision for large storm
            rrfracrm_ER11 = np.linspace(
                rfracrm_min, rfracrm_max, num=(rfracrm_max - rfracrm_min) // drfacrm
            )
            rr_ER11 = rrfracrm_ER11 * rmax
            rmax_or_r0 = "rmax"
            VV_ER11, _ = ER11_radprof(Vmax, rmax, rmax_or_r0, fcor, CkCd, rr_ER11)

            # what does this mean in matlab?
            if np.isnan(max(VV_ER11)):  # ER11_radprof converged.
                rrfracr0_ER11 = rr_ER11 / r0
                MMfracM0_ER11 = (rr_ER11 * VV_ER11 + 0.5 * fcor * rr_ER11) / M0_E04

                x0, y0 = curveintersect(
                    rrfracr0_E04, MMfracM0_E04, rrfracr0_ER11, MMfracM0_ER11
                )
                if len(x0) == 0:
                    drmaxr0 = abs(drmaxr0) / 2
                else:
                    drmaxr0 = -abs(drmaxr0) / 2
                    rmerger0 = np.mean(x0)
                    MmergeM0 = np.mean(y0)
            else:
                drmaxr0 = -abs(drmaxr0) / 2

            rmaxr0 = rmaxr0_new
            rmaxr0_new = rmaxr0_new + drmaxr0

        if np.isnan(max(VV_ER11)) and rmerger0 is not None and var is not None:
            soln_converged = True
        else:
            soln_converged = False
            CkCd = CkCd + 0.1
            print("Adjusting CkCd to find convergence.")
    M0 = 0.5 * fcor * r0**2
    Mm = 0.5 * fcor * rmax**2 + rmax * Vmax
    MmM0 = Mm / M0
    ii_ER11 = rrfracr0_ER11 < rmerger0 and MMfracM0_ER11 < MmergeM0
    ii_E04 = rrfracr0_E04 >= rmerger0 and MMfracM0_E04 > MmergeM0
    rrfracr0_temp = np.concat([rrfracr0_ER11(ii_ER11), rrfracr0_E04(ii_E04)])
    MMfracM0_temp = np.concat([MMfracM0_ER11(ii_ER11), MMfracM0_E04(ii_E04)])

    # Final Step: Implement interpolation and calculation of final outputs
    # This will involve using the interp1d function from SciPy and the results from the previous steps

    # Example of interpolation (details depend on the actual data and logic)
    # interpolator = interp1d(rrfracr0_temp, MMfracM0_temp, kind='cubic')
    # MMfracM0 = interpolator(rrfracr0)

    # Return the calculated values
    return (
        rr,
        VV,
        rmax,
        rmerge,
        Vmerge,
        rrfracr0,
        MMfracM0,
        rmaxr0,
        MmM0,
        rmerger0,
        MmergeM0,
    )


# Example usage
# rr, VV, rmax, rmerge, Vmerge, rrfracr0, MMfracM0, rmaxr0, MmM0, rmerger0, MmergeM0 = ER11E04_nondim_r0input(Vmax, r0, fcor, Cdvary, C_d, w_cool, CkCdvary, CkCd, eye_adj, alpha_eye)
