#!/bin/bash
#PBS -N Gahenax_ATLAS
#PBS -o logs/atlas_mpi.out
#PBS -e logs/atlas_mpi.err
#PBS -l nodes=4:ppn=32
#PBS -l walltime=48:00:00
#PBS -q batch
#PBS -l pmem=2gb

cd $PBS_O_WORKDIR
module purge
module load python/3.10 openmpi/4.1.4
source venv/bin/activate
export PYTHONPATH=$(pwd)

echo "Starting P-ATLAS-NP on PBS Cluster."
mpiexec python src/supercomputing/mpi_atlas_generator.py --vars 100 --ratio 4.26 --total_instances 100000
