import sys
import logging
import numpy as np
from pymatgen.core import Structure
from pymatgen.io.vasp import Potcar, Poscar, Kpoints
from interactive.runner import execute_coro, run_vasp_calculation

_, executable, *_ = sys.argv

potcar = Potcar.from_file('POTCAR')  # load POTCAR file
kpoints = Kpoints.gamma_automatic((4, 4, 4))  # generate you custom KPOINTS file here

incar = dict(ENCUT=400, ALGO='Fast')  # put your INCAR here, tags such as INTERACTIVE, ISYM and IBRION will be updated automatically -> you might get a warning


# will be passed with the stdout_proc keyword -> This function get's executed whenever a line is written to stdout
def log_stdout(l):
    logging.info(l.decode().rstrip())


def make_positions(i):
    return [[float(i)/10.0, 0.0 , 0.0],
            [0.5, 0.5, 0.0],
            [0.5, 0.0, 0.5],
            [0.0, 0.5, 0.5]]

positions = (Structure(4.05*np.eye(3), ['Al']*4, np.array(make_positions(i))) for i in range(6))

# next_structure get's called whenever VASP demands a structure. In other words at the beginning and after each ionic step
# the parameter "p" is the "process_handle" which allows you to access forces and all the history of the calculation so far
# interactive-vasp will stop once "next_structure" raises "StopIteration"
# Use this function to generate all the intermediate structures
def next_structure(p):
    return next(positions)


if __name__ == '__main__':
    execute_coro(
        run_vasp_calculation(
            next_structure, 
            incar, 
            kpoints, 
            potcar, 
            executable=executable, 
            directory='calc', 
            stdout=None, 
            stdout_proc=log_stdout
        )
    )
