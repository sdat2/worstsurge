#!/bin/bash --login

#SBATCH --job-name=miami
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

# try to activate micromamba
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

p15=2015_miami_profile_r4i1p1f1
p100=2100_miami_profile_r4i1p1f1
obs_lon=-80.1918
obs_lat=25.7617
name=miami

daf=ei

seed=90
exp=2
python -m adbo.exp_3d --exp_name=${name}-2015-${exp}-${daf} --profile_name=$p15 --resolution=mid --obs_lat=$obs_lat --obs_lon=$obs_lon --seed=$seed --daf=$daf
python -m adbo.exp_3d --exp_name=${name}-2100-${exp}-${daf} --profile_name=$p100 --resolution=mid --obs_lat=$obs_lat --obs_lon=$obs_lon  --seed=$seed --daf=$daf

seed=95
exp=3
python -m adbo.exp_3d --exp_name=${name}-2015-${exp}-${daf} --profile_name=$p15 --resolution=mid --obs_lat=$obs_lat --obs_lon=$obs_lon  --seed=$seed --daf=$daf
python -m adbo.exp_3d --exp_name=${name}-2100-${exp}-${daf}  --profile_name=$p100 --resolution=mid --obs_lat=$obs_lat --obs_lon=$obs_lon  --seed=$seed --daf=$daf


seed=100
exp=4
python -m adbo.exp_3d --exp_name=${name}-2015-${exp}-${daf} --profile_name=$p15 --resolution=mid --obs_lat=$obs_lat --obs_lon=$obs_lon  --seed=$seed --daf=$daf
python -m adbo.exp_3d --exp_name=${name}-2100-${exp}-${daf}  --profile_name=$p100 --resolution=mid --obs_lat=$obs_lat --obs_lon=$obs_lon  --seed=$seed --daf=$daf