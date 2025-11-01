"""Headless runner for quick smoke tests and CI.

Starts a short simulation without any GUI. This script spawns a few
processes that execute `worker.process_worker` and collects logs into a
timestamped file.
"""
import argparse
import multiprocessing as mp
import time
from ipc_engine import QueueChannel
from diagnostics import Diagnostics
from worker import process_worker


def run_headless(num_procs: int, seconds: int, deadlock: bool = False):
    log_q = mp.Queue()
    control_queues = [mp.Queue() for _ in range(num_procs)]
    channel = QueueChannel()
    diagnostics = Diagnostics() if isinstance(channel, QueueChannel) else None

    procs = []
    for i in range(num_procs):
        p = mp.Process(
            target=process_worker,
            args=(i, num_procs, channel, control_queues[i], log_q, diagnostics, deadlock),
            daemon=True,
        )
        procs.append(p)
        p.start()

    start = time.time()
    timeline = []
    try:
        while time.time() - start < seconds:
            # Drain logs
            while not log_q.empty():
                timeline.append(log_q.get())
            time.sleep(0.05)
    finally:
        for q in control_queues:
            q.put("STOP")
        for p in procs:
            p.join(timeout=1.0)
            if p.is_alive():
                p.terminate()

    ts = int(time.time())
    fname = f"ipcsync_log_{ts}.txt"
    with open(fname, "w", encoding="utf-8") as f:
        f.write("\n".join(timeline))

    print(f"Headless run finished; log written to {fname}")


def parse_args():
    p = argparse.ArgumentParser(description="Run a short headless IPC simulation")
    p.add_argument("--procs", type=int, default=3, help="Number of processes to spawn")
    p.add_argument("--seconds", type=int, default=5, help="How long to run the simulation")
    p.add_argument("--deadlock", action="store_true", help="Enable deadlock demo mode")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    mp.set_start_method("spawn", force=False)
    run_headless(args.procs, args.seconds, args.deadlock)
