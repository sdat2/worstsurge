#!/bin/bash --login

# Slurm settings
#SBATCH --job-name=i3b47t0
#SBATCH --nodes=1
#SBATCH --tasks-per-node=128
#SBATCH --cpus-per-task=1
#SBATCH --time=24:00:0
#SBATCH --output=logs/%x-%j.out
#SBATCH --account=n02-bas
#SBATCH --partition=standard
#SBATCH --qos=standard

p25=2025_new_orleans_profile_r4i1p1f1
p97=2097_new_orleans_profile_r4i1p1f1
obs_lon=-90.0715
obs_lat=29.9511
init_steps=3
daf_steps=47

# try to activate micromamba
source /work/n02/n02/sdat2/.bashrc
which micromamba
micromamba --version
micromamba activate t1

# print out the python version
echo "which python"
which python

for trial in {0..0}; do
    seed=$(( $init_steps * 10000 + $daf_steps * 100 + $trial ))
    echo "trial = $trial, seed = $seed"
    if trial == 0; then
        exp_name=i${init_steps}b${daf_steps}
    else
        exp_name=i${init_steps}b${daf_steps}t${trial}
    fi
    python -m adbo.exp_3d --exp_name=$exp_name --profile_name=$p25 --resolution=mid --obs_lat=$obs_lat --obs_lon=$obs_lon --init_steps=$init_steps --daf_steps=$daf_steps --seed=$seed
done
