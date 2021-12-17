import os
import sys
import shlex
import asyncio
import functools
from .utils import ensure_iterable_of_type
from .aio import forking_pipe, create_standard_streams 

class InteractiveProcess(object):

    def __init__(self, command, directory=os.getcwd(), stdout=sys.stdout, stderr=sys.stderr, stdin=sys.stdin, stdin_proc=None, stdout_proc=None, stderr_proc=None, loop=None):
        ensure_tuple = functools.partial(ensure_iterable_of_type, tuple)
        self._command = command
        self._directory = directory
        self._pipes = None
        self._handle = None
        self._wrapped_streams = None
        self._streams = (stdin, ensure_tuple(stdout), ensure_tuple(stderr))
        self._processors = (stdin_proc, ensure_tuple(stdout_proc), ensure_tuple(stderr_proc))
        self._loop = asyncio.get_event_loop() if loop is None else loop 

    async def create_process_handle(self):
        PIPE = asyncio.subprocess.PIPE
        handle = await asyncio.create_subprocess_exec(*shlex.split(self._command), stdin=PIPE, stdout=PIPE, stderr=PIPE, cwd=self._directory)
        return handle

    def create_pipes(self, proc_handle, stdin, stdout, stderr):
        proc_stdin, proc_stdout, proc_stderr = self._processors
        return dict(
            stdout=asyncio.create_task(forking_pipe(proc_handle.stdout, stdout, line_processors=proc_stdout)),
            stderr=asyncio.create_task(forking_pipe(proc_handle.stderr, stderr, line_processors=proc_stderr)),
            stdin=asyncio.create_task(forking_pipe(stdin, (proc_handle.stdin,), line_processors=proc_stdin))
        )

    def close_pipes(self, pipes):
        for forkers in pipes.values():
            forkers.cancel()

    async def __aenter__(self):
        self._wrapped_streams = await create_standard_streams(*self._streams)
        self._handle = await self.create_process_handle()
        self._pipes = self.create_pipes(self._handle, *self._wrapped_streams)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        
        if self._handle.returncode is None:
            self._handle.terminate()
        await self._handle.wait()
        self.close_pipes(self._pipes)
        self._handle, self._pipes = None, None

    async def wait(self):
        if self._handle:
            await self._handle.wait()

