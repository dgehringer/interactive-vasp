
import re
import os
import sys
import enum
import functools
from .utils import ensure_iterable_of_type
from .interactive import InteractiveProcess
from .regex import chain, group, lpad, lrpad, regex_whitespace_maybe, regex_whitespace_sure, regex_float, regex_integer

# build regexes

def lpadws(regex):
    return lpad(regex, regex_whitespace_sure)

def lpadws(regex):
    return lpad(regex, regex_whitespace_sure)

def padnum(type, name=None, optional=False):
    parser = {float: regex_float, int: regex_integer}
    return ("?" if optional else "") + lpadws(group(parser[type], name=name))

def lrpadfloat(name):
 return lrpad(group(regex_float, name=name), regex_whitespace_sure)

scf_table_columns = ['N', 'E', 'dE', 'd\seps', 'ncg', 'rms', 'rms\(c\)']
scf_table_values = [
    (int, 'step'),
    (float, 'E'),
    (float, 'dE'),
    (float, 'deps'),
    (int, 'ncg'),
    (float, 'rms'),
    (float, 'rmsc', True)
]

regex_main_loop_active = re.compile(chain(r'^', regex_whitespace_maybe, 'entering\s+main\s+loop'))

regex_scf_table_header = re.compile(chain('^', *map(lpadws, scf_table_columns)))

regex_scf_table_row = re.compile(chain('^\s*', group('\w+', name='algo'), ':', *map(lambda args: padnum(*args), scf_table_values)))

regex_ionic_step_complete = re.compile(chain(padnum(int, 'step'), regex_whitespace_sure, 'F=', lrpadfloat('F'), 'E0=', lrpadfloat('E0'), 'd\sE\s*=\s*', group(regex_float, name='dE')))

regex_forces_begin = re.compile(r'^FORCES:')

regex_ion_forces = re.compile(chain(*(padnum(float) for _ in range(3))))

regex_feed_positions_begin = re.compile('POSITIONS:\sreading\sfrom\sstdin')

regex_feed_positions_end = re.compile('POSITIONS:\sread\sfrom\sstdin')

scf_table_converters = dict(
    algo=lambda x: x,
    E=float,
    dE=float,
    deps=float,
    rms=float,
    rmsc=lambda x: x if x is None else float(x),
    step=int,
    ncg=int
)

ionic_step_summary_converters = dict(
    step=int,
    F=float,
    E0=float,
    dE=float
)

ensure_tuple = functools.partial(ensure_iterable_of_type, tuple)

def add_line_processor(processor, procs=None):
    return (processor,) if procs is None else ensure_tuple(procs) + (processor,)


class VaspInteractiveProcess(InteractiveProcess):

    class Callback(enum.Enum):

        MainLoopStarted = 'main_loop_started'
        IonicStepStarted = 'ionic_step_started'
        IonicStepFinished = 'ionic_step_finished'
        ScfStepCompleted = 'scf_step_callback'
        NextStructure = 'next_structure'
        IonForceRead = 'ion_force_read'
        FeedPositionsStarted = 'feed_positions_started'
        FeedPositionsFinished = 'feed_positions_finished'
        Exit = 'exit'


    def __init__(self, next_structure, command, directory=os.getcwd(), stdout=sys.stdout, stderr=sys.stderr, stdin=sys.stdin, stdin_proc=None, stdout_proc=None, stderr_proc=None, loop=None):
        super().__init__(command, directory=directory, stdout=stdout, stderr=stderr, stdin=stdin, stdin_proc=stdin_proc, stdout_proc=add_line_processor(self._main_processor, stdout_proc), stderr_proc=stderr_proc, loop=loop)
        self._scf_step = None
        self._ionic_step = None
        self._next_action = (regex_main_loop_active, self._main_loop_started)
        self._current_ionic_step = None
        self._ionic_steps = []
        self._callbacks = {cb: [] for cb in VaspInteractiveProcess.Callback}
        self._compute_next_positions = next_structure
        self._abort = False
        self._positions = None
        self._ion_index = None
    
    def register_callback(self, cb, f):
        cb = cb if isinstance(cb, VaspInteractiveProcess.Callback) else VaspInteractiveProcess.Callback(cb)
        self._callbacks[cb].append(f) 

    def _fire_callback(self, cb, *args, **kwargs):
        for cb_ in self._callbacks[cb]:
            cb_(*args, **kwargs)

    def _main_loop_started(self, *_):
        self._scf_step = 0
        self._ionic_step = 0
        self._next_action = (regex_scf_table_header, self._ionic_step_started)
        self._fire_callback(VaspInteractiveProcess.Callback.MainLoopStarted)

    def _ionic_step_started(self, *_):
        self._current_ionic_step = dict(scf=[])
        self._scf_step = 0
        self._ionic_step += 1
        self._next_action = (regex_scf_table_row, self._scf_step_completed)
        self._fire_callback(VaspInteractiveProcess.Callback.IonicStepStarted, self._ionic_step)

    def _scf_step_completed(self, m):
        self._scf_step += 1
        assert self._current_ionic_step is not None
        data = m.groupdict()
        if data['rms'] is None:
            data['rms'] = data['rmsc']
            data['rmsc'] = None

        data = {k: scf_table_converters.get(k)(v) for k, v in data.items()}
        self._current_ionic_step['scf'].append(data)
        self._next_action = ((regex_scf_table_row, regex_forces_begin), (self._scf_step_completed, self._read_forces))
        self._fire_callback(VaspInteractiveProcess.Callback.ScfStepCompleted, self._ionic_step, self._scf_step, data=data)

    def _read_forces(self, *_):
        self._ion_index = 0
        self._current_ionic_step['forces'] = []
        self._next_action = (regex_ion_forces, self._read_ion_force)

    def _read_ion_force(self, m):
        forces = list(map(float, m.groups()))
        self._current_ionic_step['forces'].append(forces)
        self._next_action = ((regex_ion_forces, regex_ionic_step_complete), (self._read_ion_force, self._ionic_step_finished))
        self._fire_callback(VaspInteractiveProcess.Callback.IonForceRead, forces, index=self._ion_index, ionic_step=self._ionic_step)

    def _ionic_step_finished(self, m):
        data = {k: ionic_step_summary_converters.get(k)(v) for k, v in m.groupdict().items()}
        self._ion_index = None
        self._current_ionic_step['summary'] = data
        self._ionic_steps.append(self._current_ionic_step)
        self._next_action = (regex_feed_positions_begin, self._start_feed_positions)
        self._fire_callback(VaspInteractiveProcess.Callback.IonicStepFinished, self._ionic_step, data=self._current_ionic_step, scf_steps=self._scf_step)
        self._current_ionic_step = None

    def _start_feed_positions(self, *_):
        try:
            self._positions = self._compute_next_positions(self)
            abort = False
        except (StopIteration,) as e:
            abort = True
        # we set the expected actions before we feed the positions
        if abort:
            self.abort()
        self._next_action = (regex_feed_positions_end, self._end_feed_positions)
        self._fire_callback(VaspInteractiveProcess.Callback.FeedPositionsStarted)
        self._feed_positions(self._positions)

    def _end_feed_positions(self, *_):
        self._fire_callback(VaspInteractiveProcess.Callback.FeedPositionsFinished)
        self._next_action = (regex_scf_table_header, self._ionic_step_started)

    def _feed_positions(self, positions):
        for coords in positions:
            line = ' '.join(map(lambda x: f'{x:18.16f}', coords))
            self._feed_line(line) 

    def _feed_line(self, command, end=os.linesep):
        self._handle.stdin.write(f'{command}{end}'.encode())

    def abort(self):
        self._fire_callback(VaspInteractiveProcess.Callback.Exit)
        stopcar_path = os.path.join(self._directory, 'STOPCAR')
        if not os.path.exists(stopcar_path):
            with open(stopcar_path, 'w') as h:
                h.write('LSTOP = .TRUE.\n')
        self._abort = True
    
    def cancel_abort(self):
        stopcar_path = os.path.join(self._directory, 'STOPCAR')
        if os.path.exists(stopcar_path):
            os.remove(stopcar_path)
        self._abort = False

    def _main_processor(self, line):
        line = line.decode().rstrip()
        triggers, actions = map(ensure_tuple, self._next_action)
        for trigger, action in zip(triggers, actions):
            m = trigger.match(line)
            if m:
                action(m)
                break
    
    @property
    def ionic_step(self):
        return self._ionic_step

    @property
    def scf_step(self):
        self._scf_step

    @property
    def ionic_steps(self):
        return self._ionic_steps

    @property
    def positions(self):
        return self._positions

    @property
    def last_ionic_step(self):
        return next(reversed(self._ionic_steps), None)