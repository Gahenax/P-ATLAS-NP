#!/bin/bash
#SBATCH --job-name=Gahenax_ATLAS
#SBATCH --output=logs/atlas_mpi_%j.out
#SBATCH --nodes=4                   
#SBATCH --ntasks-per-node=32        
#SBATCH --time=48:00:00             
#SBATCH --partition=compute         

module purge
module load python/3.10 openmpi/4.1.4
source venv/bin/activate
export PYTHONPATH=$(pwd)

echo "Starting P-ATLAS-NP on $SLURM_JOB_NUM_NODES nodes."
mpirun python src/supercomputing/mpi_atlas_generator.py --vars 100 --ratio 4.26 --total_instances 100000
