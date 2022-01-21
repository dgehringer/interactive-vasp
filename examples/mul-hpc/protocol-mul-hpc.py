#!/usr/bin/env python
# coding: utf-8

# Add export PYTHONPATH="/path/to/interactive-vasp"
# Add export OMP_NUM_THREADS=1

import logging
import numpy as np
from interactive.runner import execute_coro, run_vasp_calculation
from pymatgen.io.vasp import Potcar, Poscar, Kpoints
from pymatgen.core import Structure


potcar = Potcar.from_file('interactive-vasp/POTCAR')
kpoints = Kpoints.gamma_automatic((4, 4, 4))
structure = Poscar.from_file('interactive-vasp/POSCAR').structure
incar = dict(ENCUT=400, ALGO='Fast')

executable_path = '/calc/dnoeger/software/e5-1650/vasp-intel-mpich-mkl/5.4.1/bin/vasp_std'

def log_stdout(l):
    logging.info(l.decode().rstrip())


def make_positions(i):
    return [[float(i)/10.0, 0.0 , 0.0],
            [0.5, 0.5, 0.0],
            [0.5, 0.0, 0.5],
            [0.0, 0.5, 0.5]]

positions = (Structure(4.05*np.eye(3), ['Al']*4, np.array(make_positions(i))) for i in range(6))

def next_structure(p):
    print("next_structure: ", p.last_ionic_step['forces'] if p.last_ionic_step else "")
    return next(positions)


if __name__ == '__main__':
    # execute_coro(run_programm())
    execute_coro(run_vasp_calculation(next_structure, incar, kpoints, potcar, executable=f"mpirun -np 4 {executable_path}", directory='calc', stdout=None, stdout_proc=log_stdout))
