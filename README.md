# Pipeline Hazard Detector & Resolver with Interactive Visualization

A complete, production-level system that simulates a 5-stage CPU pipeline (IF, ID, EX, MEM, WB). This simulator accepts user-input assembly code, detects RAW, WAR, and WAW hazards, and demonstrates both stalling and forwarding techniques through a modern interactive UI.

## Features

- **Dynamic Assembly Parsing**: Supports custom assembly parsing for instructions like `LOAD`, `STORE`, `ADD`, `SUB`, `MUL`, `BEQ`, `JMP`, etc.
- **Cycle-by-cycle Simulation**: Accurately simulates the instruction lifecycle through IF, ID, EX, MEM, and WB stages.
- **Hazard Detection**: Automatically detects read-after-write (RAW), write-after-read (WAR), and write-after-write (WAW) hazards.
- **Hazard Resolution Modes**:
  - **None**: No hazard handling.
  - **Stall**: Detects hazards and inserts stalls (bubbles) dynamically.
  - **Forwarding**: Resolves RAW hazards bypassing data (e.g. EX-to-EX or MEM-to-EX forwarding), visually drawing paths with arrows.
- **Control Hazards**: Simulates branch predictions (predict not taken) and flushes the pipeline when a misprediction occurs.
- **Interactive Visualization**:
  - Highlights stages causing hazards with colored borders.
  - Draws dynamic arrows (using SVG) representing forwarding paths.
  - Step-by-step execution mode to watch the pipeline cycle-by-cycle.
- **Performance Metrics**: Calculates total execution cycles, CPI (Cycles Per Instruction), total stalls, and flushes in real-time.
- **Smart Explanations**: A live feed of human-readable explanations detailing why a specific hazard occurred at a given cycle.

## How to Run

### Requirements
- Python 3.8+
- Node.js / Simple HTTP Server (Optional, but recommended for serving frontend files without CORS issues locally)

### 1. Start the Backend API
The backend is built with FastAPI. It receives code and returns structured JSON with the simulation trace.

```bash
cd backend
python -m venv venv

# On Windows
venv\Scripts\activate
# On Mac/Linux
source venv/bin/activate

pip install fastapi uvicorn pydantic

# Run the server
python main.py
```
*The server will start on `http://0.0.0.0:8000`.*

### 2. Open the Frontend
Since it's built with clean HTML/CSS/JS, you can simply serve the directory. Alternatively, double-click `index.html` (make sure CORS allows it if opening directly, though using a local server is preferred).

```bash
cd frontend
python -m http.server 3000
# Then visit http://localhost:3000 in your browser
```

## Example Inputs

### RAW Hazard
```assembly
ADD R1, R2, R3
SUB R4, R1, R5
MUL R6, R1, R7
```

### Load-Use Hazard
```assembly
LOAD R1, 10(R2)
ADD R3, R1, R4
```

### Branch Hazard
```assembly
ADD R1, R2, R3
BEQ R1, R0, LABEL
ADD R4, R5, R6
LABEL:
SUB R7, R8, R9
```

## Explanation of Hazards

- **RAW (Read After Write)**: Occurs when an instruction needs to read a register that is being written by an older, currently executing instruction. This is a true data dependency.
- **WAR (Write After Read)**: Occurs when an instruction writes to a register that an older instruction is reading from. Rare in basic 5-stage pipelines but detected for completeness.
- **WAW (Write After Write)**: Occurs when two instructions write to the same register, and the latter writes before the former.
- **Control Hazard**: Occurs when branch instructions (e.g., `BEQ`) change the PC (Program Counter). If the branch is taken, the instructions already fetched into the pipeline (IF, ID stages) are incorrect and must be **flushed**.
