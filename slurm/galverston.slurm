#!/bin/bash --login

#SBATCH --job-name=galverston
#SBATCH --nodes=1
#SBATCH --tasks-per-node=128
#SBATCH --cpus-per-task=1
#SBATCH --time=24:00:00

# slurm job name as output log file name
#SBATCH --output=logs/%x-%j.out

# Replace [budget code] below with your project code (e.g. t01)

#SBATCH --account=n01-biopole
#SBATCH --partition=standard
#SBATCH --qos=standard

# emailing for start and end.
#SBATCH --mail-type=BEGIN
#SBATCH --mail-type=END
#SBATCH --mail-user=sdat2@cam.ac.uk

# # try to activate micromamba
# source /work/n02/n02/sdat2/.bashrc
# which micromamba
# micromamba --version
# micromamba activate t1

source /work/n01/n01/sithom/.bashrc
which conda
conda --version
conda activate base

# print out the python version
echo "which python"
which python

# define variables
#case_name=$SLURM_JOB_NAME # name for printing
# np=$SLURM_NTASKS  # how many parallel tasks to define
# export OMP_NUM_THREADS=1

# Propagate the cpus-per-task setting from script to srun commands
#    By default, Slurm does not propagate this setting from the sbatch
#    options to srun commands in the job script. If this is not done,
#    process/thread pinning may be incorrect leading to poor performance
# export SRUN_CPUS_PER_TASK=$SLURM_CPUS_PER_TASK
p15=2015_galverston_profile_r4i1p1f1
p100=2100_galverston_profile_r4i1p1f1
obs_lon=-94.7977
obs_lat=29.3013
seed=30

# 1
# python -m adbo.exp_3d --exp_name=galverston-2015-2 --profile_name=$p15 --resolution=mid --obs_lat=$obs_lat --obs_lon=$obs_lon --seed=$seed
python -m adbo.exp_3d --exp_name=galverston-2100-2 --profile_name=$p100 --resolution=mid --obs_lat=$obs_lat --obs_lon=$obs_lon --seed=$seed
