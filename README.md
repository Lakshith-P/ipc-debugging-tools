# Inter-Process Communication (IPC) Debugger

### 1. Project Overview

* **Project Goals:** To design and build a visual debugging tool that simulates and analyzes the performance and synchronization of common Inter-Process Communication (IPC) methods: Pipes, Message Queues, and Shared Memory.
* **Expected Outcomes:** A functional desktop application where a user can select an IPC method, choose a number of processes, and visually observe data transfer. The tool must successfully highlight performance bottlenecks (via latency/throughput metrics) and critical synchronization errors (like deadlocks).
* **Project Scope:** The project is scoped to three IPC methods (Pipe, Queue, Shared Memory), a Python/Qt GUI for simulation, a logging system, and specific modules for both demonstrating and automatically detecting deadlocks.

### 2. Module-Wise Breakdown

| Module | Purpose | Role |
| :--- | :--- | :--- |
| **GUI Frontend** (`gui.qml`) | This module is the "face" of the application. It provides all user controls and visual feedback. | It acts as a "thin client" that is decoupled from the simulation logic. It simply displays information and sends commands to the backend. |
| **Simulation Backend** (`main.py`) | This is the "brain" of the project. It connects the frontend (GUI) to the backend (IPC Engine). | It manages the simulation's life cycle (start, stop), spawns child processes, creates communication channels, and aggregates logs/metrics. |
| **IPC & Diagnostics Engine** (`ipc_engine.py`, `diagnostics.py`) | This module contains the "plumbing" and the "doctor." It defines the low-level communication channels. | `ipc_engine.py` provides concrete implementations for each IPC method. `diagnostics.py` acts as a specialized tool to analyze the channels for errors. |

### 3. Functionalities

| Module | Key Functionalities |
| :--- | :--- |
| **GUI Frontend** | <ul><li>**Process Visualization:** Draws a box for each active process.</li><li>**Data-Flow Animation:** Renders animated dots flying between processes.</li><li>**Control Panel:** Provides buttons to Start/Stop, Export Log, and toggle Deadlock Mode.</li><li>**Real-time Stats:** Displays `Throughput` and `Avg. Latency`.</li><li>**Log Viewer:** A scrollable `TextArea` shows a time-stamped log of all actions.</li><li>**Alert System:** A flashing red bar shows critical alerts.</li></ul> |
| **Simulation Backend** | <ul><li>**Process Management:** Uses `multiprocessing` to spawn and terminate all child processes.</li><li>**State Management:** Binds Python variables (e.g., `_running`) to QML properties (`backend.running`).</li><li>**Event/Signal Handling:** Uses PySide's `Signal`/`Slot` system to trigger GUI events (like animations).</li><li>**Log Aggregation:** Uses an `mp.Queue` to safely collect logs from all processes.</li></ul> |
| **IPC & Diagnostics Engine** | <ul><li>**`PipeChannel`:** Implements `send`/`recv` using a simple `mp.Pipe`.</li><li>**`QueueChannel`:** Implements `send`/`recv` using a process-safe `mp.Queue`.</li><li>**`SharedMemoryChannel`:** Implements `send`/`recv` using a locked `mp.Array`.</li><li>**`Diagnostics`:** Implements a graph-based algorithm to find circular "wait-for" dependencies (deadlocks).</li></ul> |

### 4. Technology Recommendations

| Technology | Recommendation | Reason |
| :--- | :--- | :--- |
| **Programming Language** | **Python (3.8+)** | Its `multiprocessing` library is perfect for this task, and its "batteries-included" nature makes it easy to work with. |
| **GUI Framework** | **PySide6 (Qt for Python)** | Provides a modern QML-based approach that cleanly separates frontend logic (`.qml`) from backend logic (`.py`). |
| **Key Libraries** | `multiprocessing`, `PySide6.QtCore`, `PySide6.QtQml` | Core for creating processes, Pipes, Queues, Locks, and for connecting the Python backend to the QML frontend. |

### 5. Execution Plan

| Step | Action |
| :--- | :--- |
| **Step 1** | **Build the IPC Engine (`ipc_engine.py`):** Define the abstract `IPCChannel` base class. Implement the `PipeChannel`, `QueueChannel`, and `SharedMemoryChannel`. Test with a simple command-line script. |
| **Step 2** | **Build the Backend (`main.py`):** Create the `Backend` class and `process_worker` function. Write the `start`/`stop` logic. Test with console logging (no GUI). |
| **Step 3** | **Build the Core GUI (`gui.qml`):** Lay out the buttons, process view area, and log. Connect the `Start` button to the `backend.start` slot. |
| **Step 4** | **Connect Backend to Frontend:** Implement the full `Signal`/`Slot` system. Feed the `TextArea` from the `log_q`. Implement the `onDataFlow` signal for animations and the `QTimer` for stats. |
| **Step 5** | **Implement the Deadlock Feature:** Build the `diagnostics.py` module for automatic detection. Build the manual "Force Deadlock" demo with the extra locks and logic in `process_worker`. Connect this to the GUI to turn the boxes red. |

## Contributing

Small improvements and bug-fixes are welcome. If you'd like to contribute:

- Fork the repo and create a feature branch for your changes.
- Add tests (see `tests/`) for any behavioral changes.
- Keep commits small and descriptive. We follow Conventional Commits.
- Open a pull request describing the change and why it's useful.

## Headless runner (CI / quick smoke tests)

The project includes a lightweight headless runner that can start a short simulation without the GUI. This is useful for CI or smoke tests. See `headless_runner.py` which programmatically starts the backend, runs a short simulation, and writes a small log file.

Example (local):

1. Run a short headless session:

	python headless_runner.py --procs 4 --seconds 5

2. Check the generated log `ipcsync_log_<timestamp>.txt` for messages.
