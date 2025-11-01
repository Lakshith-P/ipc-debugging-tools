"""IPC channel implementations used by the simulator.

Small, well-documented implementations for Pipe, Queue and SharedMemory
channels. These are intentionally lightweight for use in the GUI and in
headless smoke tests.
"""

import multiprocessing as mp
import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class Message:
    src: int
    dst: int
    data: str
    timestamp: float


class IPCChannel:
    """Abstract interface for channels used by processes.

    Implementations should provide `send`, `recv`, `status` and
    `type_name` methods.
    """

    def send(self, src: int, data: str): ...

    def recv(self, dst: int, diag=None) -> Optional[Message]: ...

    def status(self) -> str: ...

    def type_name(self) -> str: ...


class PipeChannel(IPCChannel):
    def __init__(self):
        # Use a unidirectional pipe for simplicity
        self.in_, self.out_ = mp.Pipe(duplex=False)

    def send(self, src, data):
        self.out_.send((src, data, time.time()))

    def recv(self, dst, diag=None):
        if self.in_.poll():
            src, data, ts = self.in_.recv()
            return Message(src, dst, data, ts)
        return None

    def status(self):
        return "Pipe: ready" if self.in_.poll() else "Pipe: empty"

    def type_name(self):
        return "Pipe"


class QueueChannel(IPCChannel):
    def __init__(self):
        self.q = mp.Queue()

    def send(self, src, data):
        self.q.put((src, data, time.time()))

    def recv(self, dst, diag=None):
        try:
            src, data, ts = self.q.get_nowait()
        except Exception:
            return None
        return Message(src, dst, data, ts)

    def status(self):
        # qsize may be approximate across processes
        try:
            size = self.q.qsize()
        except Exception:
            size = "?"
        return f"Queue: {size} msg(s)"

    def type_name(self):
        return "MsgQueue"


class SharedMemoryChannel(IPCChannel):
    def __init__(self):
        # Small fixed-size buffer for demonstration purposes
        self.buf = mp.Array('c', b'\x00' * 256)
        self.src = mp.Value('i', -1)
        self.ts = mp.Value('d', 0.0)
        self.lock = mp.Lock()
        self.updated = mp.Event()

    def send(self, src, data):
        with self.lock:
            b = data.encode()[:255]
            self.buf[: len(b)] = b
            self.buf[len(b)] = 0
            self.src.value = src
            self.ts.value = time.time()
            self.updated.set()

    def recv(self, dst, diag):
        # Wait briefly for an update
        if self.updated.wait(timeout=0.1):
            with self.lock:
                if self.ts.value > 0:
                    raw = self.buf[:].split(b'\x00', 1)[0]
                    msg = Message(self.src.value, dst, raw.decode(), self.ts.value)
                    self.ts.value = 0.0
                    self.updated.clear()
                    if diag:
                        diag.update_access(dst)
                    return msg

        # If lock is contended, report wait info to diagnostics
        if not self.lock.acquire(block=False):
            owner = self.src.value
            if owner >= 0 and diag:
                diag.add_wait(dst, owner)
                time.sleep(0.15)
                diag.remove_wait(dst)
            return None
        else:
            self.lock.release()
            return None

    def status(self):
        with self.lock:
            length = len(self.buf[:].split(b'\x00', 1)[0])
        return f"SharedMem: {length} bytes"

    def type_name(self):
        return "SharedMem"
