"""Dask utilities for parallel processing."""

from typing import Callable
import time
from dask.distributed import Client, LocalCluster
from sithom.time import hr_time


def dask_cluster_wrapper(
    func: Callable,
    *args,
    **kwargs,
) -> None:
    """
    A wrapper to run a function on a Dask cluster.
    This is useful for running functions that take a long time to compute
    and can be parallelized across multiple workers.
    """
    tick = time.perf_counter()
    cluster = LocalCluster()  # n_workers=10, threads_per_worker=1)
    client = Client(cluster)
    print(f"Dask dashboard link: {client.dashboard_link}")

    func(*args, **kwargs)

    client.close()
    cluster.close()  # Also a good idea to close the cluster
    tock = time.perf_counter()
    print(
        f"Function {func.__name__} for {str(args)}, {str(kwargs)} completed in {hr_time(tock-tick)} seconds."
    )
