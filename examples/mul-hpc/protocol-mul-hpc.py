import sys
import logging
import itertools
import numpy as np
from interactive import IonicStepFinished
from interactive.runner import execute_coro, run_vasp_calculation

from pymatgen.core import Structure
from pymatgen.io.vasp import Potcar, Kpoints

_, executable, *_ = sys.argv

potcar = Potcar.from_file('POTCAR')  # load POTCAR file
kpoints = Kpoints.gamma_automatic((4, 4, 4))  # generate you custom KPOINTS file here

# put your INCAR here, tags such as INTERACTIVE, ISYM and IBRION will be updated automatically -> you might get a warning
incar = dict(
    ENCUT=400, 
    ALGO='Fast', 
    LWAVE=False, 
    LCHARG=False,
    #ML_LMLFF=True,
    #ML_ISTART=0,
    # MDALGO=3
)  


# will be passed with the stdout_proc keyword -> This function get's executed whenever a line is written to stdout
def log_stdout(l):
    pass
    # logging.info(l.decode().rstrip())


def make_positions():
    import random

    fact = 5

    coords = np.array(
        [[0.0, 0.0 , 0.0],
        [0.5, 0.5, 0.0],
        [0.5, 0.0, 0.5],
        [0.0, 0.5, 0.5]]
    )
    nitems = np.prod(coords.shape)
    displacements = np.array([random.random()/fact - 1.0/(2*fact) for _ in range(nitems)]).reshape(coords.shape)
    return coords * (np.ones_like(coords) + displacements)



chain = itertools.chain(range(-6, 7))

positions = (Structure(4.05*np.eye(3), ['Al']*4, np.array(make_positions())) for _ in range(2000))

# next_structure get's called whenever VASP demands a structure. In other words at the beginning and after each ionic step
# the parameter "p" is the "process_handle" which allows you to access forces and all the history of the calculation so far
# interactive-vasp will stop once "next_structure" raises "StopIteration"
# Use this function to generate all the intermediate structures
def next_structure(p):
    return next(positions)


import time

def ionic_step_finished(*args, **kwargs):
    #time.sleep(1)
    #print(args, kwargs)
    pass

if __name__ == '__main__':
    execute_coro(
        run_vasp_calculation(
            next_structure, 
            incar, 
            kpoints, 
            potcar, 
            executable=executable, 
            callbacks={IonicStepFinished: ionic_step_finished},
            directory='calc', # execute everything in a new folder named "calc"
            stdout_proc=log_stdout
        )
    )
