## ipc_engine.py
import multiprocessing as mp, time
from dataclasses import dataclass
from typing import Optional

@dataclass
class Message:
    src: int
    dst: int
    data: str
    timestamp: float

class IPCChannel:
    def send(self, src: int, data: str): ...
    def recv(self, dst: int, diag=None) -> Optional[Message]: ...
    def status(self) -> str: ...
    def type_name(self) -> str: ...


class PipeChannel(IPCChannel):
    def __init__(self):
        self.in_, self.out_ = mp.Pipe(duplex=False)
    def send(self, src, data): self.out_.send((src, data, time.time()))
    def recv(self, dst, diag=None):
        if self.in_.poll():
            src, data, ts = self.in_.recv()
            return Message(src, dst, data, ts)
        return None
    def status(self): return "Pipe: ready" if self.in_.poll() else "Pipe: empty"
    def type_name(self): return "Pipe"

class QueueChannel(IPCChannel):
    def __init__(self): self.q = mp.Queue()
    def send(self, src, data): self.q.put((src, data, time.time()))
    def recv(self, dst, diag=None):
        try: src, data, ts = self.q.get_nowait()
        except: return None
        return Message(src, dst, data, ts)
    def status(self): return f"Queue: {self.q.qsize()} msg(s)"
    def type_name(self): return "MsgQueue"

class SharedMemoryChannel(IPCChannel):
    def __init__(self):
        self.buf = mp.Array('c', b'\x00'*256)
        self.src = mp.Value('i', -1)
        self.ts  = mp.Value('d', 0.0)
        self.lock = mp.Lock()
        self.updated = mp.Event()

    def send(self, src, data):
        with self.lock:
            b = data.encode()[:255]
            self.buf[:len(b)] = b
            self.buf[len(b)] = 0
            self.src.value = src
            self.ts.value  = time.time()
            self.updated.set()

    def recv(self, dst, diag):
        if self.updated.wait(timeout=0.1):
            with self.lock:
                if self.ts.value > 0:
                    raw = self.buf[:].split(b'\x00',1)[0]
                    msg = Message(self.src.value, dst, raw.decode(), self.ts.value)
                    self.ts.value = 0.0
                    self.updated.clear()
                    if diag: diag.update_access(dst)
                    return msg

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
            length = len(self.buf[:].split(b'\x00',1)[0])
        return f"SharedMem: {length} bytes"
    def type_name(self): return "SharedMem:"

# end of ipc_engine.py