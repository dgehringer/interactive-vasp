
import os
import sys
import shutil
import logging
import asyncio
import warnings
import functools
import numpy as np
from .aio import execute_coro
from .vasp import VaspInteractiveProcess
from .utils import ensure_iterable_of_type

try:
    import pymatgen
except ImportError:
    warnings.warn('Cannot import pymatgen')


logging.basicConfig(
    format = '▸ %(asctime)s.%(msecs)03d %(filename)s:%(lineno)d %(levelname)s %(message)s',
    level = logging.INFO,
    datefmt = '%H:%M:%S')


def complete_incar(incar: dict):
    incar = incar.copy()
    def set_parameter(tag, value):
        if tag not in incar:
            warnings.warn(f'Set: {tag}={value}')
        elif value != incar.get(tag):
            warnings.warn(f'Override: {tag}={incar.get(tag)} with {tag}={value}')
        incar[tag] = value

    set_parameter('ISYM', 0)
    set_parameter('IBRION', 11)
    set_parameter('POTIM', 0.0)
    set_parameter('NSW', int(1e6))
    set_parameter('INTERACTIVE', True)
    return incar


def generate_structure_wrapper(f):
    
    def _wrapper(process):
        positions = f(process)
        # if it is ase.Atoms
        if hasattr(positions, 'get_scaled_positions'):
            positions = positions.get_scaled_positions()
        elif hasattr(positions, 'frac_coords'):
            positions = positions.frac_coords
        
        if isinstance(positions, np.ndarray):
            positions = positions.tolist()

        return positions

    return _wrapper


def construct_proc_handle(gen_structure, executeable, directory=os.getcwd(), stdout=sys.stdout, stderr=sys.stderr, stdin=sys.stdin, stdin_proc=None, stdout_proc=None, stderr_proc=None, loop=None, callbacks=None):
    
    structure_generator = generate_structure_wrapper(gen_structure)

    proc_handle = VaspInteractiveProcess(
        structure_generator, executeable, directory=directory, 
        stdin=stdin, stdout=stdout, stderr=stderr,
        stdin_proc=stdin_proc, stdout_proc=stdout_proc, stderr_proc=stderr_proc,
        loop=loop)

    for cb, funcs in (callbacks or {}).items():
        for f in ensure_iterable_of_type(tuple, funcs):
            proc_handle.register_callback(cb, f)
    
    return proc_handle


def copy_or_write(fname, clasz, transform=None, directory=os.getcwd()):

    if isinstance(fname, str):
        # the we copy just the file to out new directory
        obj = clasz.from_file(fname)
    elif isinstance(fname, clasz):
        obj = fname
    else:
        # finally we try to throw it into the constructore of the corresponding type
        obj = clasz(fname)

    obj = transform(obj) if transform is not None else obj

    obj.write_file(os.path.join(directory, clasz.__name__.upper()))


async def run_vasp_calculation(gen_structure, incar, kpoints, potcar, directory=os.getcwd(), executable=None, stdout=sys.stdout, stderr=sys.stderr, stdin=sys.stdin, stdin_proc=None, stdout_proc=None, stderr_proc=None, loop=None, callbacks=None):

    if not os.path.exists(directory):
        os.makedirs(directory)

    if executable is None:
        for binary_name in 'vasp', 'vasp_std', 'vasp_gam', 'vasp_ncl':
            executable = shutil.which(binary_name)
            if executable is not None: 
                break
        else:
            raise RuntimeError('Cannot find a VASP executable')

    loop = loop or asyncio.get_event_loop()

    proc_handle = construct_proc_handle(gen_structure, executable, directory=directory, stdout=stdout, stderr=stderr, stdin=stdin, stdout_proc=stdout_proc, stderr_proc=stderr_proc, stdin_proc=stdin_proc, loop=loop, callbacks=callbacks)

    first_structure = gen_structure(proc_handle)
    # do imports
    from pymatgen.io.vasp import Poscar, Incar, Kpoints, Potcar
    copy_or_write_ = functools.partial(copy_or_write, directory=directory)
    copy_or_write_(first_structure, Poscar)
    copy_or_write_(incar, Incar, transform=lambda inc: Incar(complete_incar(inc)))
    copy_or_write_(kpoints, Kpoints)
    copy_or_write_(potcar, Potcar)

    async with proc_handle:
        await proc_handle.wait()

    return proc_handle