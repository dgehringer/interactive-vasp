import os
import sys
import stat
import asyncio

PY37 = sys.version_info >= (3, 7)
platform = sys.platform

def is_pipe_transport_compatible(pipe):
    if platform == "win32":
        return False
    try:
        fileno = pipe.fileno()
    except OSError:
        return False
    mode = os.fstat(fileno).st_mode
    is_char = stat.S_ISCHR(mode)
    is_fifo = stat.S_ISFIFO(mode)
    is_socket = stat.S_ISSOCK(mode)
    if not (is_char or is_fifo or is_socket):
        return False
    return True


def protect_standard_streams(stream):
    if stream._transport is None:
        return
    try:
        fileno = stream._transport.get_extra_info("pipe").fileno()
    except (ValueError, OSError):
        return
    if fileno < 3:
        stream._transport._pipe = None


class StandardStreamReaderProtocol(asyncio.StreamReaderProtocol):
    def connection_made(self, transport):
        # The connection is already made
        if self._stream_reader._transport is not None:
            return
        # Make the connection
        super().connection_made(transport)

    def connection_lost(self, exc):
        # Copy the inner state
        state = self.__dict__.copy()
        # Call the parent
        super().connection_lost(exc)
        # Restore the inner state
        self.__dict__.update(state)


class StandardStreamReader(asyncio.StreamReader):

    __del__ = protect_standard_streams

    async def readuntil(self, separator=b"\n"):
        # Re-implement `readuntil` to work around self._limit.
        # The limit is still useful to prevent the internal buffer
        # from growing too large when it's not necessary, but it
        # needs to be disabled when the user code is purposely
        # reading from stdin.
        while True:
            try:
                return await super().readuntil(separator)
            except asyncio.LimitOverrunError as e:
                if self._buffer.startswith(separator, e.consumed):
                    chunk = self._buffer[: e.consumed + len(separator)]
                    del self._buffer[: e.consumed + len(separator)]
                    self._maybe_resume_transport()
                    return bytes(chunk)
                await self._wait_for_data("readuntil")


class StandardStreamWriter(asyncio.StreamWriter):

    __del__ = protect_standard_streams

    def write(self, data):
        if isinstance(data, str):
            data = data.encode()
        super().write(data)


class NonFileStreamReader:
    def __init__(self, stream, *, loop=None):
        if loop is None:
            loop = asyncio.get_event_loop()
        self.loop = loop
        self.stream = stream
        self.eof = False

    def at_eof(self):
        return self.eof

    async def readline(self):
        data = await self.loop.run_in_executor(None, self.stream.readline)
        if isinstance(data, str):
            data = data.encode()
        self.eof = not data
        return data

    async def read(self, n=-1):
        data = await self.loop.run_in_executor(None, self.stream.read, n)
        if isinstance(data, str):
            data = data.encode()
        self.eof = not data
        return data

    def __aiter__(self):
        return self

    async def __anext__(self):
        val = await self.readline()
        if val == b"":
            raise StopAsyncIteration
        return val


class NonFileStreamWriter:
    def __init__(self, stream, *, loop=None):
        if loop is None:
            loop = asyncio.get_event_loop()
        self.loop = loop
        self.stream = stream

    def write(self, data):
        if isinstance(data, bytes):
            data = data.decode()
        self.stream.write(data)

    async def drain(self):
        try:
            flush = self.stream.flush
        except AttributeError:
            pass
        else:
            await self.loop.run_in_executor(None, flush)


async def open_standard_pipe_connection(pipe_in, pipes_out, pipes_err, *, loop=None):
    if loop is None:
        loop = asyncio.get_event_loop()
    # Reader
    in_reader = StandardStreamReader(loop=loop)
    protocol = StandardStreamReaderProtocol(in_reader, loop=loop)
    await loop.connect_read_pipe(lambda: protocol, pipe_in)
    # Out writer

    async def make_out_pipe(pipe_out):
        out_write_connect = loop.connect_write_pipe(lambda: protocol, pipe_out)
        out_transport, _ = await out_write_connect
        out_writer = StandardStreamWriter(out_transport, protocol, in_reader, loop)
        return out_writer

    # Err writer
    async def make_err_pipe(pipe_err):
        err_write_connect = loop.connect_write_pipe(lambda: protocol, pipe_err)
        err_transport, _ = await err_write_connect
        err_writer = StandardStreamWriter(err_transport, protocol, in_reader, loop)
        return err_writer
    # Return

    output_writers, error_writers = [], []
    for pipe in pipes_out or ():
        writer = await make_out_pipe(pipe)
        output_writers.append(writer)

    for pipe in pipes_err or ():
        writer = await make_err_pipe(pipe)
        error_writers.append(writer)

    return in_reader, tuple(output_writers), tuple(error_writers)

def flatten_streams(*streams):
    stdin, stdout, stderr = streams
    yield stdin
    for stdout_ in (stdout or ()):
        yield stdout_
    for stderr_ in (stderr or ()):
        yield stderr_

async def create_standard_streams(stdin, stdout, stderr, *, loop=None):
    if all(map(is_pipe_transport_compatible, tuple(flatten_streams(stdin, stdout, stderr)))):
        return await open_standard_pipe_connection(stdin, stdout, stderr, loop=loop)
    return (
        NonFileStreamReader(stdin, loop=loop) if stdin is not None else stdin,
        list(NonFileStreamWriter(stdout_stream, loop=loop) for stdout_stream in stdout),
        list(NonFileStreamWriter(stderr_stream, loop=loop) for stderr_stream in stderr)
    )

async def forking_pipe(reader, writers, line_processors = None):
    line_processors = () if line_processors is None else line_processors
    while not reader.at_eof():
        msg = await reader.readline()
        # finally forward the msg to the writer
        for processor in line_processors:
            processor(msg)
        for writer in writers:
            writer.write(msg)
    for writer in writers: 
        if hasattr(writer, 'drain'):
            await writer.drain()
