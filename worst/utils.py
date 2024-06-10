"""Worst.utils.py"""

from typing import Optional
import numpy as np
from scipy.stats import genextreme
import matplotlib.pyplot as plt


# assume gamma < 0 (Weibull class)
def z_star_from_alpha_beta_gamma(alpha: float, beta: float, gamma: float) -> float:
    return alpha - beta / gamma


def alpha_from_z_star_beta_gamma(z_star: float, beta: float, gamma: float) -> float:
    return z_star + beta / gamma


def bg_cdf(z: np.ndarray, z_star: float, beta: float, gamma: float) -> np.ndarray:
    return np.exp(-((gamma / beta * (z - z_star)) ** (-1 / gamma)))


def plot_rp(
    alpha: float,
    beta: float,
    gamma: float,
    color: str = "blue",
    label: str = "",
    ax=None,
    plot_alpha: float = 0.8,
) -> None:
    """
    Plot the return period vs return value curve for the given parameters.

    Args:
        alpha (float): The location parameter.
        beta (float): The scale parameter.
        gamma (float): The shape parameter.
        color (str, optional): The color of the line. Defaults to "blue".
        label (str, optional): The line label. Defaults to "".
        ax (_type_, optional): The axes to add the figure too. Defaults to None.
        plot_alpha (float, optional): Transparency parameter of line. Defaults to 0.8.
    """
    z1yr = genextreme.isf(0.8, c=-gamma, loc=alpha, scale=beta)
    z1myr = genextreme.isf(1 / 1_000_000, c=-gamma, loc=alpha, scale=beta)
    znew = np.linspace(z1yr, z1myr, num=100)

    if ax is None:
        _, ax = plt.subplots(
            1,
            1,
        )

    print(label, "rp1yr", z1yr, "rv1Myr", z1myr)
    if gamma < 0:  # Weibull class have upper bound
        z_star = z_star_from_alpha_beta_gamma(alpha, beta, gamma)
        ax.hlines(z_star, 2, 1_000_000, color=color, linestyles="dashed")
        rp = 1 / (1 - bg_cdf(znew, z_star, beta, gamma))
    else:
        rp = 1 / genextreme.sf(znew, c=-gamma, loc=alpha, scale=beta)

    ax.semilogx(rp, znew, color=color, label=label, alpha=plot_alpha)
    ax.set_ylabel("Return Value [m]")
    ax.set_xlabel("Return Period [years]")


def plot_sample_points(
    data: np.ndarray,
    color: str = "black",
    ax: Optional[any] = None,
    label: str = "Sampled data points",
):
    """
    Plot the sample points on the return period vs return value curve.

    Args:
        data (np.ndarray): The sample points to plot.
        color (str, optional): The color of the points. Defaults to "black".
        ax (_type_, optional): The axes to add the figure too. Defaults to None.
    """
    if ax is None:
        _, ax = plt.subplots(
            1,
            1,
        )
    sorted_zs = np.sort(data)
    empirical_rps = len(data) / np.arange(1, len(data) + 1)[::-1]

    ax.scatter(
        empirical_rps,
        sorted_zs,
        s=3,
        alpha=0.8,
        color=color,
        label=label,
    )
    ax.set_ylabel("Return Value [m]")
    ax.set_xlabel("Return Period [years]")
