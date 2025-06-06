"""Run BayesOpt experiments.

Should contain all tensorflow imports so that other scripts
are easier to use/test without waiting for tensorflow to load.
"""

from typing import Callable, Optional, List
import os
import yaml
import numpy as np
import xarray as xr
import matplotlib
import time

start_tf_import = time.time()
import tensorflow as tf
import tensorflow_probability as tfp
import gpflow
import trieste
from trieste.acquisition import (
    ExpectedImprovement,
    MinValueEntropySearch,
    NegativeLowerConfidenceBound,
)
from omegaconf import OmegaConf
from trieste.acquisition.rule import EfficientGlobalOptimization
from trieste.experimental.plotting.plotting import plot_bo_points, plot_regret
from trieste.objectives.single_objectives import check_objective_shapes

end_tf_import = time.time()
print(
    "tf import time", end_tf_import - start_tf_import
)  # takes about 270 seconds on ARCHER2 (?why?)
from sithom.time import timeit
from sithom.plot import plot_defaults
from sithom.io import write_json
import matplotlib.pyplot as plt
from adforce.wrap import idealized_tc_observe, get_default_config
from adforce.constants import NEW_ORLEANS
from .ani import plot_gps
from .rescale import rescale_inverse
from .constants import FIGURE_PATH, EXP_PATH, CONFIG_PATH

# archer 2:
matplotlib.use("Agg")
plot_defaults()


@timeit
def setup_tf(seed: int = 1793, log_name: str = "experiment1") -> None:
    """
    Set up the tensorflow environment by seeding and setting up logging/tensorboard.

    Args:
        seed (int, optional): Random seed for numpy/tensorflow. Defaults to 1793.
        log_name (str, optional): Name for the log. Defaults to "experiment1".
    """
    np.random.seed(seed)
    tf.random.set_seed(seed)
    print("trieste.__version__", trieste.__version__)
    print("tf.__version__", tf.__version__)
    print("Num GPUs Available: ", len(tf.config.list_physical_devices("GPU")))
    # sess = tf.Session(config=tf.ConfigProto(log_device_placement=True))
    tf.debugging.set_log_device_placement(True)
    TENSORBOARD_LOG_DIR = os.path.join("logs", "tensorboard", log_name)
    os.makedirs(TENSORBOARD_LOG_DIR, exist_ok=True)
    files = os.listdir(TENSORBOARD_LOG_DIR)
    for file in files:
        os.remove(os.path.join(TENSORBOARD_LOG_DIR, file))
    summary_writer = tf.summary.create_file_writer(TENSORBOARD_LOG_DIR)
    trieste.logging.set_tensorboard_writer(summary_writer)
    print("summary_writer", summary_writer)


@timeit
def objective_f(
    cfg: dict,
) -> Callable[[tf.Tensor], tf.Tensor]:
    """
    Return a wrapper function for the ADCIRC model that is compatible with being used as an observer in trieste after processing.

    At each objective function call the model is run and the result is returned and saved.

    Returns:
        Callable[[tf.Tensor], tf.Tensor]: trieste observer function.
    """
    call_number = -1
    output = {}
    dimension_inputs = len(cfg["constraints"]["order"])
    exp_dir = cfg["exp_dir"]
    print("dimension_inputs", dimension_inputs)

    def temp_dir() -> str:
        """
        Return a temporary directory for the current experiment.

        Returns:
            str: Temporary directory based on the call number.
        """
        nonlocal exp_dir
        tmp_dir = os.path.join(exp_dir, f"exp_{call_number:04}")
        os.makedirs(tmp_dir, exist_ok=True)
        return tmp_dir

    def add_query_to_output(real_query: tf.Tensor, real_result: tf.Tensor) -> None:
        """
        Add the query and result to the output dictionary.

        Args:
            real_query (tf.Tensor): The resecaled query.
            real_result (tf.Tensor): The result with the correct sign.
        """
        nonlocal output
        output[call_number] = {
            "": temp_dir(),
            "res": float(real_result),
            **{
                name: float(real_query[j])
                for j, name in enumerate(cfg["constraints"]["order"])
            },
        }
        write_json(output, os.path.join(exp_dir, "experiments.json"))

    @check_objective_shapes(d=dimension_inputs)
    def obj(x: tf.Tensor) -> tf.Tensor:
        """
        Run the ADCIRC model and return the result.

        Args:
            x (tf.Tensor): Possibly a batch of scaled queries.

        Returns:
            tf.Tensor: The negative of the result of the ADCIRC model at the selected point.
        """
        nonlocal call_number
        # put in real space
        returned_results = []  # new results, negative height [m]
        real_queries = rescale_inverse(x, cfg["constraints"])  # convert to real space
        for i in range(real_queries.shape[0]):
            call_number += 1
            inputs = {
                name: float(real_queries[i][j])
                for j, name in enumerate(cfg["constraints"]["order"])
            }
            wrap_cfg = get_default_config()

            print("read config", wrap_cfg)
            # I want to generalize this so it's relative to the observation point not New Orleans
            tmp_dir = temp_dir()
            wrap_cfg.files.run_folder = tmp_dir
            # delete fort.22.nc after run
            wrap_cfg.files.low_storage = True
            wrap_cfg.tc.profile_name.value = cfg["profile_name"]
            wrap_cfg.adcirc.attempted_observation_location.value = [
                cfg["obs_lon"],
                cfg["obs_lat"],
            ]
            wrap_cfg.adcirc["resolution"].value = cfg["resolution"]
            for inp in inputs:
                if inp != "displacement":
                    if inp == "trans_speed":
                        wrap_cfg.tc["translation_speed"].value = inputs[inp]
                    else:
                        wrap_cfg.tc[inp].value = inputs[inp]
                if inp == "displacement":
                    wrap_cfg.tc.impact_location.value = [
                        cfg["obs_lon"] + inputs["displacement"],
                        cfg["obs_lat"],
                    ]
            # if "displacement" in inputs:
            #    # assume impact lon relative to New Orleans
            #    inputs["impact_lon"] = NEW_ORLEANS.lon + inputs["displacement"]
            #    del inputs["displacement"]

            if cfg["wrap_test"]:
                real_result = min(7 + np.random.normal(), 10)
                yaml_str = OmegaConf.to_yaml(wrap_cfg)
                with open(os.path.join(tmp_dir, "wrap_cfg.yaml"), "w") as file:
                    file.write(yaml_str)
            else:
                # wrap_cfg.tc["displacement"].value = x
                real_result = idealized_tc_observe(wrap_cfg)
                # out_path=tmp_dir,
                # profile_name=profile_name,
                # resolution=resolution,
                # **inputs,

            add_query_to_output(real_queries[i], real_result)
            # flip sign to make it a minimisation problem
            returned_results.append([-real_result])

        return tf.constant(returned_results, dtype=tf.float64)

    return obj


# maybe shift this to constants?
DEFAULT_CONSTRAINTS: dict = yaml.safe_load(
    open(os.path.join(CONFIG_PATH, "3d_constraints.yaml"))
)


def gp_model_callback_maker(
    direc: str,
    constraints: dict = DEFAULT_CONSTRAINTS,
    acq_rule: Optional[EfficientGlobalOptimization] = None,
) -> Callable[[any, any, any], bool]:
    """
    Return a callback function that saves the GP model at each step.

    TODO: problem from the animation: the x1 and x2 are not the right way around. Could be a problem in the scaled results.

    Args:
        direc (str): Directory to save the models.
        constraints (dict, optional): Dictionary with the constraints for the optimization. Defaults to DEFAULT_CONSTRAINTS.
        acq_rule (Optional[EfficientGlobalOptimization], optional): The acquisition rule. Defaults to None.

    Returns:
        Callable[[any, any, any], bool]: Callback function for early_stop_callback.
    """
    # https://github.com/secondmind-labs/trieste/blob/develop/trieste/models/gpflow/models.py
    os.makedirs(direc, exist_ok=True)
    # saver = gpflow.saver.Saver()
    call: int = 0
    dimensions = len(constraints["order"])

    if dimensions == 1:  # if 1D save GP model output
        nx1 = 100
        x1 = np.linspace(0, 1, num=nx1)
        x1_r = rescale_inverse(np.column_stack([x1]), constraints=constraints)[:, 0]
        assert x1.shape == (nx1,)
        assert x1_r.shape == x1.shape
        x_input = np.column_stack([x1])
        assert x_input.shape == (nx1, 1)
        ypred_list: List[np.ndarray] = []
        ystd_list: List[np.ndarray] = []
        acq_list: List[np.ndarray] = []
        # x_r = rescale_inverse(np.column_stack([x1]), constraints=constraints)

    elif dimensions == 2:  # if 2D save GP model output

        nx1, nx2 = 100, 102  # resolution of the plot
        # added some asymmetry to try to see if axes flip.
        x1 = np.linspace(0, 1, num=nx1)
        x2 = np.linspace(0, 1, num=nx2)
        # x1, x2 = np.linspace(0, 1, num=nx1), np.linspace(0, 1, num=nx2)
        # To to get different lengths of x1 and
        # x2 to be rescaled, need to do them separately.
        x1_r = rescale_inverse(
            np.column_stack([x1, np.linspace(0, 1, num=nx1)]), constraints=constraints
        )[:, 0]
        x2_r = rescale_inverse(
            np.column_stack([np.linspace(0, 1, num=nx2), x2]), constraints=constraints
        )[:, 1]
        assert x2_r.shape == x2.shape
        assert x1.shape == (nx1,)
        assert x1_r.shape == x1.shape
        # x_r = rescale_inverse(np.column_stack([x1, x2]), constraints=constraints)
        # x1_r, x2_r = x_r[:, 0], x_r[:, 1]
        X1, X2 = np.meshgrid(x1, x2, indexing="ij")
        print("X1", X1.shape)
        assert X1.shape == (nx1, nx2)
        print("X2", X2.shape)
        assert X2.shape == (nx1, nx2)
        x_input = np.column_stack([X1.flatten(), X2.flatten()])
        assert x_input.shape == (nx1 * nx2, 2)
        assert np.allclose(x_input[:, 0].reshape((nx1, nx2)), X1)
        assert np.allclose(x_input[:, 1].reshape((nx1, nx2)), X2)
        ypred_list: List[np.ndarray] = []
        ystd_list: List[np.ndarray] = []
        acq_list: List[np.ndarray] = []

    @timeit
    def gp_model_callback(datasets, gp_models, state) -> bool:
        """
        Save the GP model at each step.

        Args:
            datasets (any): The datasets.
            gp_models (any): The GP models.
            state (any): The state.

        Returns:
            bool: Whether to stop the optimization.
        """
        # could either save the whole model or just the predictions at particular points.
        nonlocal call, direc, nx1, nx2, x1, x2, X1, X2, x_input, ypred_list, ystd_list, constraints, dimensions
        call += 1  # increment the call number

        print("dimension", dimensions)
        print("datasets", datasets)
        print("state", state)
        # use the early_stop_callback to save the GP at each step
        print("gp_model_out_callback", gp_models)
        for i, model in enumerate(gp_models):
            print(i, model, type(model))
            print(i, gp_models[model], type(gp_models[model]))
            print(
                "gp_models[model].model", gp_models[model].model
            )  # .save(f"gp_model_{i}.h5")
            # setting up a checkpoint every time is probably overwriting the previous one
            ckpt = tf.train.Checkpoint(model=gp_models[model].model)
            manager = tf.train.CheckpointManager(ckpt, direc, max_to_keep=100)
            # TODO: pass manager to callback so that it can be saved every time
            manager.save()
            # plt.show()
            plt.clf()
            plt.close()
            if dimensions == 1:
                # fig, axs = plt.subplots(1, 1, figsize=(10, 5))
                y_mean, y_var = gp_models[model].predict_y(x_input)
                y_mean, y_var = y_mean.numpy(), y_var.numpy()
                y_mean, y_var = y_mean.reshape((nx1)), y_var.reshape((nx1))

                ypred_list.append(y_mean)
                ystd_list.append(np.sqrt(y_var))
                print("np.array(ypred_list))", np.array(ypred_list).shape)
                print("np.array(yvar_list))", np.array(ystd_list).shape)
                data_vars = {
                    "ypred": (
                        ("call", "x1"),
                        np.array(ypred_list),
                        {"units": "m", "long_name": "Mean prediction"},
                    ),
                    "ystd": (
                        ("call", "x1"),
                        np.array(ystd_list),
                        {"units": "m", "long_name": "Std. Dev. in prediction"},
                    ),
                }
                if acq_rule is not None:
                    if acq_rule.acquisition_function is not None:
                        acq = acq_rule.acquisition_function(
                            tf.expand_dims(x_input, axis=-2)
                        )
                        acq = np.reshape(acq, (nx1,))
                    else:
                        acq = np.zeros((nx1,))
                    acq_list.append(acq)
                    print("np.array(acq_list))", np.array(acq_list).shape)
                    data_vars["acq"] = (
                        ("call", "x1"),
                        np.array(acq_list),
                        {"units": "dimensionless", "long_name": "acquisition function"},
                    )
                    print("np.array(acq_list))", np.array(acq_list).shape)

                print(
                    "np.array([x + 1 for x in range(call)]))",
                    [x + 1 for x in range(len(ypred_list))],
                )
                xr.Dataset(
                    data_vars=data_vars,
                    coords={
                        "x1": (
                            ("x1"),
                            x1_r,
                            {"units": constraints[constraints["order"][0]]["units"]},
                        ),
                        "call": (
                            ("call"),
                            [x + 1 for x in range(len(ypred_list))],
                            {"units": "dimensionless", "long_name": "call number"},
                        ),
                    },
                ).to_netcdf(os.path.join(direc, f"gp_model_outputs.nc"))
            if dimensions == 2:
                # what's a good way to check that this puts the dimensions the right way around?
                # fig, axs = plt.subplots(1, 2, figsize=(10, 5))
                y_mean, y_var = gp_models[model].predict_y(x_input)
                y_mean, y_var = y_mean.numpy(), y_var.numpy()
                y_mean, y_var = y_mean.reshape((nx1, nx2)), y_var.reshape((nx1, nx2))

                ypred_list.append(y_mean)
                ystd_list.append(np.sqrt(y_var))
                print("np.array(ypred_list))", np.array(ypred_list).shape)
                print("np.array(yvar_list))", np.array(ystd_list).shape)
                data_vars = {
                    "ypred": (
                        ("call", "x1", "x2"),
                        np.array(ypred_list),
                        {"units": "m", "long_name": "Mean prediction"},
                    ),
                    "ystd": (
                        ("call", "x1", "x2"),
                        np.array(ystd_list),
                        {"units": "m", "long_name": "Std. Dev. in prediction"},
                    ),
                }
                if acq_rule is not None:
                    if acq_rule.acquisition_function is not None:
                        acq = acq_rule.acquisition_function(
                            tf.expand_dims(x_input, axis=-2)
                        )
                        acq = np.reshape(acq, (nx1, nx2))
                    else:
                        acq = np.zeros((nx1, nx2))
                    acq_list.append(acq)
                    print("np.array(acq_list))", np.array(acq_list).shape)
                    data_vars["acq"] = (
                        ("call", "x1", "x2"),
                        np.array(acq_list),
                        {"units": "dimensionless", "long_name": "acquisition function"},
                    )
                    print("np.array(acq_list))", np.array(acq_list).shape)

                print(
                    "np.array([x + 1 for x in range(call)]))",
                    [x + 1 for x in range(len(ypred_list))],
                )
                xr.Dataset(
                    data_vars=data_vars,
                    coords={
                        "x1": (
                            ("x1"),
                            x1_r,
                            {"units": constraints[constraints["order"][0]]["units"]},
                        ),
                        "x2": (
                            ("x2"),
                            x2_r,
                            {"units": constraints[constraints["order"][1]]["units"]},
                        ),
                        "call": (
                            ("call"),
                            [x + 1 for x in range(len(ypred_list))],
                            {"units": "dimensionless", "long_name": "call number"},
                        ),
                    },
                ).to_netcdf(os.path.join(direc, f"gp_model_outputs.nc"))

                # im = axs[0].contourf(X1, X2, y_mean, levels=1000)
                # # add colorbar to the plot with the right scale and the same size as the plot
                # fig.colorbar(im, ax=axs[0], fraction=0.046, pad=0.04)
                # # axs[0].colorbar()
                # axs[0].set_title("Mean")
                # im = axs[1].contourf(X1, X2, np.sqrt(y_var), levels=1000)
                # fig.colorbar(im, ax=axs[1], fraction=0.046, pad=0.04)
                # # axs[1].colorbar()
                # axs[1].set_title("Std. Dev., $\sigma$")
                # axs[0].set_xlabel("x$_1$")
                # axs[0].set_ylabel("x$_2$")
                # axs[1].set_xlabel("x$_1$")
                # # plt.show()
                # plt.clf()
                # plt.close()
            #  model.save(os.path.join(f"gp_model_{i}.h5"))
            # saver.save(os.path.join(direc, f"gp_model_{call}"), model)

        return False  # False means don't stop

    return gp_model_callback


def run_exists(exp_name: str, num_runs: int) -> bool:
    """
    Check if the experiment has already been run.
    Check if folder exists. Check if the correct number of subdirectories have been created, and check if the summary results have been stored.

    Args:
        exp_name (str): Name of the experiment.

    Returns:
        bool: Whether the experiment has already been run.
    """
    if os.path.exists(os.path.join(EXP_PATH, exp_name)):
        if (
            len(
                [
                    x
                    for x in os.listdir(os.path.join(EXP_PATH, exp_name))
                    if x.startswith("exp_")
                ]
            )
            == num_runs
        ):
            if os.path.exists(os.path.join(EXP_PATH, exp_name, "experiments.json")):
                return True
    return False


@timeit
def run_bayesopt_exp(
    constraints: dict = DEFAULT_CONSTRAINTS,
    seed: int = 10,
    profile_name: str = "2025_new_orleans_profile_r4i1p1f1",  # 2025.json, 2097.json
    resolution: str = "mid",
    exp_name: str = "bo_test",
    root_exp_direc: str = EXP_PATH,
    obs_lon: float = NEW_ORLEANS.lon,
    obs_lat: float = NEW_ORLEANS.lat,
    init_steps: int = 10,
    daf_steps: int = 10,
    daf: str = "mes",  # mes, ei, ucb
    kernel: str = "Matern52",  # Matern32, Matern52, SE
    wrap_test: bool = False,
) -> None:
    """
    Run a Bayesian Optimisation experiment.

    Args:
        constraints (dict, optional): Dictionary with the constraints for the optimization. Defaults to DEFAULT_CONSTRAINTS.
        seed (int, optional): Seed to initialize. Defaults to 10.
        profile_name (str, optional): Name of the profile. Defaults to "2025_new_orleans_profile_r4i1p1f1".
        exp_name (str, optional): Experiment name. Defaults to "bo_test".
        root_exp_direc (str, optional): Root directory for the experiments. Defaults to "/work/n01/n01/sithom/adcirc-swan/exp".
        init_steps (int, optional): How many sobol sambles. Defaults to 10.
        daf_steps (int, optional): How many acquisition points. Defaults to 10.
        obs_lon (float, optional): Longitude of the observation point. Defaults to NEW_ORLEANS.lon.
        obs_lat (float, optional): Latitude of the observation point. Defaults to NEW_ORLEANS.lat.
        resolution (str, optional): Resolution of the model. Defaults to "mid".
        daf (str, optional): Type of acquisition function. Defaults to "mes".
        kernel (str, optional): Kernel to use. Defaults to "Matern52".
        wrap_test (bool, optional): Whether to prevent. Defaults to False.
    """
    direc = os.path.join(root_exp_direc, exp_name)

    cfg = {
        "constraints": constraints,
        "seed": seed,
        "profile_name": profile_name,
        "exp_name": exp_name,
        "init_steps": init_steps,
        "daf_steps": daf_steps,
        "obs_lon": obs_lon,
        "obs_lat": obs_lat,
        "wrap_test": wrap_test,
        "resolution": resolution,
        "exp_dir": direc,
    }

    if run_exists(exp_name, num_runs=init_steps + daf_steps):
        print(f"Experiment {exp_name} already exists")
        return

    # add existance check here
    os.makedirs(direc, exist_ok=True)
    write_json(cfg, os.path.join(direc, "bo-config.json"))
    print("BO config", cfg)

    setup_tf(seed=seed, log_name=exp_name)

    # set up BayesOpt
    dimensions_input: int = len(constraints["order"])
    # assert dimensions_input == 2
    search_space = trieste.space.Box([0] * dimensions_input, [1] * dimensions_input)
    initial_query_points = search_space.sample_sobol(init_steps)
    print("initial_query_points", initial_query_points, type(initial_query_points))
    init_objective = objective_f(cfg)

    # observer = trieste.objectives.utils.mk_observer(obs_class.objective)
    observer = trieste.objectives.utils.mk_observer(init_objective)
    print("observer", observer, type(observer))
    initial_data = observer(initial_query_points)
    print("initial_data", initial_data, type(initial_data))
    # set up bayesopt loop
    if kernel == "Matern52":
        gp_kernel = gpflow.kernels.Matern52()
    elif kernel == "Matern32":
        gp_kernel = gpflow.kernels.Matern32()
    elif kernel == "SE":
        gp_kernel = gpflow.kernels.SquaredExponential()
    else:
        raise ValueError(f"Unknown kernel {kernel}")

    gpr = trieste.models.gpflow.build_gpr(  # by default Matern 52
        initial_data, search_space, kernel=gp_kernel
    )  # should add kernel choice here.
    model = trieste.models.gpflow.GaussianProcessRegression(gpr)
    # choices mves,
    # TODO: make another choice for this.
    if daf == "mes":
        acquisition_func = MinValueEntropySearch(
            search_space
        )  # should add in acquisition function choice here.
    elif daf == "ei":
        acquisition_func = ExpectedImprovement(
            search_space  # , best_observation=initial_data.maximum()
        )
    elif daf == "ucb":
        acquisition_func = NegativeLowerConfidenceBound(search_space)
    else:
        raise ValueError(f"Unknown acquisition function {daf}")
    acquisition_rule = EfficientGlobalOptimization(acquisition_func)
    bo = trieste.bayesian_optimizer.BayesianOptimizer(observer, search_space)
    # run bayesopt loop
    result = bo.optimize(
        daf_steps,
        initial_data,
        model,
        acquisition_rule,
        track_state=True,  # there was some issue with this on mac
        early_stop_callback=gp_model_callback_maker(
            direc,
            constraints,
            acq_rule=acquisition_rule,
        ),
    ).astuple()
    trieste.logging.set_summary_filter(lambda name: True)  # enable all summaries
    # print("result", result)
    # print("history", history)
    real_res = result[0].unwrap()
    dataset = real_res.dataset
    query_points = dataset.query_points.numpy()
    observations = dataset.observations.numpy()

    rescaled_query_points = rescale_inverse(query_points, constraints)

    def save_results(
        rescaled_query_points: np.ndarray,  # shape [N, F]
        observations: np.ndarray,
        direc: str,
        exp_name: str,
    ) -> None:
        xr.Dataset(
            data_vars={
                **{
                    "x"
                    + str(i): (
                        ("call"),
                        rescaled_query_points[:, i],
                        {"units": constraints[var]["units"], "long_name": var},
                    )
                    for i, var in enumerate(constraints["order"])
                },
                **{"y": (("call"), -observations.flatten(), {"units": "m"})},
            },
            coords={"call": [x + 1 for x in range(len(observations))]},
        ).to_netcdf(os.path.join(direc, exp_name + "_results.nc"))

    save_results(rescaled_query_points, observations, direc, exp_name)

    def plot_results() -> None:
        # plot the results for 2d
        _, ax = plt.subplots(1, 1, figsize=(10, 10))
        plot_bo_points(
            query_points,
            ax,
            init_steps,
            m_init="o",
            m_add="+",  # obs_values=observations
        )  # , arg_min_idx)
        ax.scatter(
            query_points[:, 0], query_points[:, 1], c=observations, cmap="viridis"
        )
        ax.set_xlabel(r"$x_1$ [dimensionless]")
        ax.set_ylabel(r"$x_2$ [dimensionless]")
        # change name to allow choice.
        plt.savefig(os.path.join(FIGURE_PATH, "bo_exp", exp_name + "_results.pdf"))
        # plt.show()
        plt.clf()
        plt.close()

    def plt_regret() -> None:
        # plot the regret
        _, ax = plt.subplots(1, 1, figsize=(10, 10))
        plot_regret(
            dataset.observations.numpy(),
            ax,
            num_init=init_steps,
            show_obs=True,
        )
        ax.set_xlabel("Iteration")
        ax.set_ylabel("Regret [-m]")
        plt.savefig(os.path.join(FIGURE_PATH, "bo_exp", exp_name + "_regret.pdf"))
        # plt.show()
        plt.clf()
        plt.close()

    if len(constraints["order"]) == 2:
        plot_results()
    plt_regret()

    # plot the gp model changes for 2d case:
    if len(constraints["order"]) in (1, 2):
        plot_gps(path_in=direc, plot_acq=True)


if __name__ == "__main__":
    # python -m adbo.newexp
    run_bayesopt_exp(wrap_test=False, exp_name="Test3")
