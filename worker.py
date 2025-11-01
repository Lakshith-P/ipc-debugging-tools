import time, random
import multiprocessing as mp
from typing import Optional

from ipc_engine import IPCChannel
from diagnostics import Diagnostics

def process_worker(
    pid: int,
    num_procs: int,
    channel: IPCChannel,
    control_q: mp.Queue,
    log_q: mp.Queue,
    diag: Optional[Diagnostics] = None,
    deadlock_mode: bool = False,
    lock_A: Optional[mp.Lock] = None, 
    lock_B: Optional[mp.Lock] = None
):
    """
    The target function for each simulated process.
    It sends and receives messages, simulating work.
    """
    log = lambda msg: log_q.put(f"[P{pid}] {msg}")
    log("Started.")

    if deadlock_mode:
        if pid == 2:
            log(f"DEADLOCK_MODE (P{pid}): Acquiring Lock A...")
            lock_A.acquire()
            log(f"DEADLOCK_MODE (P{pid}): Acquired Lock A. Simulating work...")
            time.sleep(1) # Give P3 time to grab Lock B
            log(f"DEADLOCK_MODE (P{pid}): Trying to acquire Lock B...")
            lock_B.acquire() # This will block forever
            log(f"DEADLOCK_MODE (P{pid}): Acquired Lock B.")
            lock_B.release()
            lock_A.release()

        elif pid == 3:
            log(f"DEADLOCK_MODE (P{pid}): Acquiring Lock B...")
            lock_B.acquire()
            log(f"DEADLOCK_MODE (P{pid}): Acquired Lock B. Simulating work...")
            time.sleep(1) # Give P2 time to grab Lock A
            log(f"DEADLOCK_MODE (P{pid}): Trying to acquire Lock A...")
            lock_A.acquire() # This will block forever
            log(f"DEADLOCK_MODE (P{pid}): Acquired Lock A.")
            lock_A.release()
            lock_B.release()

    # Normal operation
    last_send_time = time.time()
    while True:
        try:
            if not control_q.empty() and control_q.get() == "STOP":
                log("Stopping.")
                break

            msg = channel.recv(pid, diag)
            if msg:
                latency = time.time() - msg.timestamp
                log(f"Received '{msg.data}' from P{msg.src}, latency={latency:.4f}s")
                time.sleep(random.uniform(0.05, 0.2))

            if time.time() - last_send_time > random.uniform(0.5, 2.0):
                dst = random.randint(0, num_procs - 1)
                if dst == pid:
                    dst = (pid + 1) % num_procs

                data = f"Hello from P{pid}"
                log(f"Sending '{data}' to P{dst}")
                channel.send(pid, data)
                last_send_time = time.time()

            time.sleep(0.01)

        except (BrokenPipeError, EOFError):
            log("Channel closed. Exiting.")
            break
        except Exception as e:
            log(f"ERROR: {e}")
            break