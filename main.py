import sys, time, random, psutil
import multiprocessing as mp
from collections import deque
from typing import Optional, List, Deque

from PySide6.QtCore import (
    QObject, Slot, Signal, Property, QRunnable, QThreadPool, QTimer
)
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterType

# Import the modules you provided
from ipc_engine import (
    IPCChannel, PipeChannel, QueueChannel, SharedMemoryChannel, Message
)
from diagnostics import Diagnostics

# --- simulator worker -- 
# This function runs in a separate process
def process_worker(
    pid: int,
    num_procs: int,
    channel: IPCChannel,
    control_q: mp.Queue,
    log_q: mp.Queue,
    diag: Optional[Diagnostics] = None,
    deadlock_mode: bool = False,
    lock_A: Optional[mp.Lock] = None, # NEW: Lock for demo
    lock_B: Optional[mp.Lock] = None  # NEW: Lock for demo
):
    """
    The target function for each simulated process.
    It sends and receives messages, simulating work.
    """
    log = lambda msg: log_q.put(f"[P{pid}] {msg}")
    log("Started.")
    
    # Deadlock mode: P2 and P3 will try to lock resources
    # in reverse order, creating a P2 -> P3 -> P2 cycle.
    if deadlock_mode:
        if pid == 2:
            log(f"DEADLOCK_MODE (P{pid}): Acquiring Lock A...")
            lock_A.acquire()
            log(f"DEADLOCK_MODE (P{pid}): Acquired Lock A. Simulating work...")
            time.sleep(1) # Give P3 time to grab Lock B
            log(f"DEADLOCK_MODE (P{pid}): Trying to acquire Lock B...")
            lock_B.acquire() # This will block forever
            
            # This code will never be reached
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
            
            # This code will never be reached
            log(f"DEADLOCK_MODE (P{pid}): Acquired Lock A.")
            lock_A.release()
            lock_B.release()

    # Normal operation
    last_send_time = time.time()
    while True:
        try:
            # Check for control messages (e.g., "STOP")
            if not control_q.empty() and control_q.get() == "STOP":
                log("Stopping.")
                break
            
            # --- Receive Logic ---
            msg = channel.recv(pid, diag)
            if msg:
                # --- MODIFIED FOR METRICS ---
                latency = time.time() - msg.timestamp
                log(f"Received '{msg.data}' from P{msg.src}, latency={latency:.4f}s")
                # Simulate work
                time.sleep(random.uniform(0.05, 0.2))

            # --- Send Logic ---
            if time.time() - last_send_time > random.uniform(0.5, 2.0):
                dst = random.randint(0, num_procs - 1)
                if dst == pid: # Don't send to self
                    dst = (pid + 1) % num_procs
                
                data = f"Hello from P{pid}"
                log(f"Sending '{data}' to P{dst}")
                channel.send(pid, data)
                last_send_time = time.time()

            time.sleep(0.01) # Small sleep to prevent busy-waiting

        except (BrokenPipeError, EOFError):
            log("Channel closed. Exiting.")
            break
        except Exception as e:
            log(f"ERROR: {e}")
            break

# --- Python-QML Bridge ---


class Backend(QObject):
    """
    This class is exposed to QML. It handles user commands
    and emits signals to update the UI.
    """
    # --- Signals for QML ---
    # Signal(args) - 'dataFlow(int src, int dst)'
    dataFlow = Signal(int, int) 
    # Signal() - 'timelineChanged()' (used to notify QML to re-read the property)
    timelineChanged = Signal() 
    # Signal() - 'runningChanged()'
    runningChanged = Signal()
    # Signal() - 'statusChanged()'
    statusChanged = Signal()
    # Signal() - 'alertChanged()'
    alertChanged = Signal()
    # Signal() - 'metricsChanged()' (for throughput/latency)
    metricsChanged = Signal()
    # Signal() - 'deadlockActiveChanged()'
    deadlockActiveChanged = Signal()
    # Signal() - 'channelTypeChanged()'
    channelTypeChanged = Signal()
    # --- NEW SIGNAL ---
    frozenProcessesChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._status = "Idle"
        self._timeline = "Welcome to IPCSync Debugger!\n"
        self._alert = ""
        self._throughput = "Throughput: 0.0 msg/s"
        self._latency = "Avg. Latency: 0.00 ms"
        self._deadlock_active = False
        self._channel_type = "Pipe"
        
        self.processes: List[mp.Process] = []
        self.control_queues: List[mp.Queue] = []
        self.log_queue: mp.Queue = mp.Queue()
        self.channel: Optional[IPCChannel] = None
        self.diagnostics: Optional[Diagnostics] = None
        
        self.message_count = 0
        self.total_latency = 0.0
        self.start_time = 0.0
        
        # --- NEW PROPERTY ---
        self._frozen_processes: List[int] = []
        
        # Timer to pull logs from the log_queue
        self.log_timer = QTimer(self)
        self.log_timer.timeout.connect(self.update_logs)
        self.log_timer.start(100) # Check for logs every 100ms
        
        # Timer for updating stats/alerts
        self.stats_timer = QTimer(self)
        self.stats_timer.timeout.connect(self.update_stats)
        self.stats_timer.start(500) # Update stats every 500ms

    # --- QML Properties ---
    @Property(bool, notify=runningChanged)
    def running(self):
        return self._running

    @Property(str, notify=statusChanged)
    def status(self):
        return self._status

    @Property(str, notify=timelineChanged)
    def timeline(self):
        return self._timeline

    @Property(str, notify=alertChanged)
    def alert(self):
        return self._alert

    @Property(str, notify=metricsChanged)
    def throughput(self):
        return self._throughput

    @Property(str, notify=metricsChanged)
    def latency(self):
        return self._latency

    @Property(bool, notify=deadlockActiveChanged)
    def deadlockActive(self):
        return self._deadlock_active

    @Property(str, notify=channelTypeChanged)
    def channelType(self):
        return self._channel_type
        
    # --- NEW PROPERTY ---
    @Property("QVariantList", notify=frozenProcessesChanged)
    def frozenProcesses(self):
        return self._frozen_processes

    # --- QML Slots ---

    @Slot(int, int)
    def start(self, num_procs: int, ipc_index: int):
        if self._running:
            self.stop()
            return
        
        self.log_queue = mp.Queue()
        self.control_queues = [mp.Queue() for _ in range(num_procs)]
        self.processes = []
        
        ipc_map = {0: PipeChannel, 1: QueueChannel, 2: SharedMemoryChannel}
        self.channel = ipc_map.get(ipc_index, PipeChannel)()
        self.diagnostics = Diagnostics() if isinstance(self.channel, SharedMemoryChannel) else None
        
        self._channel_type = self.channel.type_name()
        self.channelTypeChanged.emit()

        self._timeline = f"--- Starting simulation with {num_procs} processes using {self._channel_type} ---\n"
        self.timelineChanged.emit()

        # --- Create locks for deadlock demo ---
        lock_A = None
        lock_B = None
        is_deadlock_demo = (
            self._deadlock_active and
            isinstance(self.channel, SharedMemoryChannel) and
            num_procs > 3 # Need P2 and P3 for the demo
        )
        
        if is_deadlock_demo:
            lock_A = mp.Lock()
            lock_B = mp.Lock()
            self._timeline += "--- DEADLOCK DEMO MODE ENABLED ---\n"
            self.update_status("Running in Deadlock Demo Mode...")
        # --- End of new lock code ---

        for i in range(num_procs):
            p = mp.Process(
                target=process_worker,
                args=(
                    i, num_procs, self.channel, self.control_queues[i],
                    self.log_queue, self.diagnostics,
                    is_deadlock_demo, # Pass the final flag
                    lock_A,           # Pass Lock A
                    lock_B            # Pass Lock B
                ),
                daemon=True
            )
            self.processes.append(p)
            p.start()

        self._running = True
        self.runningChanged.emit()
        self.update_status("Running...")
        self.start_time = time.time()
        self.message_count = 0
        self.total_latency = 0.0
        
        # --- RESET FROZEN LIST ---
        self._frozen_processes = []
        self.frozenProcessesChanged.emit()

    @Slot()
    def stop(self):
        if not self._running:
            return

        self.update_status("Stopping...")
        for q in self.control_queues:
            q.put("STOP")

        for p in self.processes:
            p.join(timeout=1.0) # Wait 1s
            if p.is_alive():
                p.terminate() # Force kill if stuck
        
        self.processes = []
        self.control_queues = []
        
        self._running = False
        self.runningChanged.emit()
        self.update_status("Idle")
        
        # --- RESET FROZEN LIST ---
        self._frozen_processes = []
        self.frozenProcessesChanged.emit()
        
        # Clear deadlock state
        if self._deadlock_active:
            self._deadlock_active = False
            self.deadlockActiveChanged.emit()
        
        # Final log pull
        self.update_logs()
        self._timeline += "--- Simulation Stopped ---\n"
        self.timelineChanged.emit()

    @Slot()
    def exportLog(self):
        try:
            filename = f"ipcsync_log_{int(time.time())}.txt"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(self._timeline)
            self.update_status(f"Log exported to {filename}")
        except Exception as e:
            self.update_status(f"Error exporting log: {e}")

    @Slot()
    def toggleDeadlock(self):
        # Can only toggle when not running
        if not self._running:
            self._deadlock_active = not self._deadlock_active
            self.deadlockActiveChanged.emit()
            status = "Deadlock mode ON" if self._deadlock_active else "Deadlock mode OFF"
            self.update_status(status)
        else:
            self.update_status("Cannot change deadlock mode while running.")

    # --- Internal Methods ---

    def update_status(self, msg: str):
        self._status = msg
        self.statusChanged.emit()
    
    def update_logs(self):
        """Pull messages from the log queue and update the timeline."""
        new_logs = False
        while not self.log_queue.empty():
            try:
                msg = self.log_queue.get_nowait()
                self._timeline += f"{msg}\n"
                new_logs = True
                
                # --- Parse log for visualizations ---
                try:
                    # Get PID from log line
                    src_pid = int(msg.split("]")[0].strip("[P"))
                except:
                    src_pid = -1

                if src_pid != -1:
                    # Check for data flow
                    if "Sending" in msg and "to P" in msg:
                        parts = msg.split(" ")
                        try:
                            dst_pid = int(parts[-1].strip("P"))
                            self.dataFlow.emit(src_pid, dst_pid)
                        except:
                            pass # Failed to parse
                    
                    # --- NEW LOGIC FOR METRICS ---
                    if "Received" in msg and "latency=" in msg:
                        try:
                            lat_str = msg.split("latency=")[1].split("s")[0]
                            self.total_latency += float(lat_str)
                            self.message_count += 1
                        except Exception as e:
                            # You could log this to the console for debugging
                            # print(f"Error parsing latency: {e}, on msg: {msg}")
                            pass 

                    # --- NEW LOGIC TO DETECT FREEZE ---
                    # Check for the log message that indicates a process is about to freeze
                    if "DEADLOCK_MODE" in msg and "Trying to acquire Lock" in msg:
                        if src_pid not in self._frozen_processes:
                            self._frozen_processes.append(src_pid)
                            self.frozenProcessesChanged.emit() # Tell QML to update
                    # --- END NEW LOGIC ---
                
            except:
                break # Queue is empty
        
        if new_logs:
            self.timelineChanged.emit()

    def update_stats(self):
        """Update performance metrics and check for diagnostic alerts."""
        if self._running:
            # Update IPC status
            if self.channel:
                self.update_status(self.channel.status())
            
            # Update performance metrics
            elapsed = time.time() - self.start_time
            if elapsed > 0:
                tput = self.message_count / elapsed
                self._throughput = f"Throughput: {tput:.1f} msg/s"
                
                if self.message_count > 0:
                    lat = (self.total_latency / self.message_count) * 1000
                    self._latency = f"Avg. Latency: {lat:.2f} ms"
                else:
                    self._latency = "Avg. Latency: 0.00 ms"
                self.metricsChanged.emit()

        # Update alerts from diagnostics
        new_alert = ""
        if self.diagnostics:
            self.diagnostics.check_deadlock() # Re-check
            new_alert = self.diagnostics.alert
            if not new_alert:
                new_alert = self.diagnostics.get_bottlenecks()
        
        if new_alert != self._alert:
            self._alert = new_alert
            self.alertChanged.emit()


# --- Main Application Runner ---

def main():
    app = QGuiApplication(sys.argv)
    
    engine = QQmlApplicationEngine()
    
    # Create the Backend instance
    backend = Backend()
    
    # Expose the Backend instance to QML under the name "backend"
    engine.rootContext().setContextProperty("backend", backend)
    
    # Load the QML file (using the correct "gui.qml" name)
    engine.load("gui.qml")
    
    if not engine.rootObjects():
        sys.exit(-1)
        
    # Set app to stop backend when quitting
    app.aboutToQuit.connect(backend.stop)
    
    sys.exit(app.exec())

if __name__ == "__main__":
    mp.freeze_support() # For Windows compatibility
    main()

