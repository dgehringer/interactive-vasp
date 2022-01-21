#!/bin/bash
#SBATCH -J VASP
#SBATCH -N 1
#SBATCH -o job.%j.out
#SBATCH -p E5-1650
#SBATCH -q E5-1650-batch
#SBATCH --ntasks-per-node=6
#SBATCH --mem=50G
#SBATCH --exclusive


module purge
module load intel
module load mkl
module load mpich
module load scalapack


export OMP_NUM_THREADS=1

VASP_MODE="std"
VASP_ROOT="/calc/dnoeger/software/e5-1650/vasp-intel-mpich-mkl"

VASP5_VERSION="5.4.1"
VASP6_VERSION="6.2.1"

VASP5_EXECUTABLE="${VASP_ROOT}/${VASP5_VERSION}/bin/vasp_${VASP_MODE}"
VASP6_EXECUTABLE="${VASP_ROOT}/${VASP6_VERSION}/bin/vasp_${VASP_MODE}"

ulimit -s unlimited

INTERACTIVE_LIB_DIR=/calc/dnoeger/software/python/interactive-vasp

# make "conda" command available by sourcing the shell initialization script

source /calc/dnoeger/software/anaconda3/etc/profile.d/conda.sh
conda activate base

PYTHONPATH=$PYTHONPATH:$INTERACTIVE_LIB_DIR python protocol-mul-hpc.py "mpirun -np 6 ${VASP5_EXECUTABLE}"

conda deactivate
