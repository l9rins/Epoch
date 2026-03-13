# 🚀 The Epoch Engine

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![React](https://img.shields.io/badge/React-Vite-61dafb?logo=react)
![Architecture](https://img.shields.io/badge/Architecture-Event--Driven-ff69b4)
![Status](https://img.shields.io/badge/status-active-brightgreen)

**The Epoch Engine** is a full-stack predictive intelligence system for NBA basketball. It combines real-time data ingestion, causal machine learning, computer vision, and deep memory-level simulation — leveraging the internal physics and player logic of NBA 2K14 — to generate win probabilities, player props, and betting signals.

---

## 🧠 Core Architecture

Epoch is divided into five decoupled, asynchronous domains:

| Domain | Path | Purpose |
|---|---|---|
| **The Pipeline** | `/src/pipeline` | Automated data ingestion from NBA API with Basketball Reference fallbacks |
| **The Intelligence** | `/src/intelligence`, `/src/ml` | Causal DAGs, fatigue models, momentum tracking, Kelly Criterion sizing |
| **The Simulator** | `/src/simulation`, `/src/binary` | Headless 2K14 runner with memory reading and binary `.ROS` roster injection |
| **The Eye** | `/src/vision` | OpenCV/YOLO microservices for court spacing and player tracking |
| **The Terminal** | `/src/frontend` | React/Vite dashboard with live WebSocket feeds and knowledge graph UI |

---

## 📂 Directory Structure

```
epoch/
├── src/
│   ├── api/             # FastAPI backend, WebSockets, Stripe integration
│   ├── binary/          # Hex/binary parsers for .ROS roster files
│   ├── frontend/        # React/Vite UI (live dashboard, command palette)
│   ├── graph/           # GNN models and knowledge graph schema
│   ├── intelligence/    # Causal models, fatigue, momentum, injury detection
│   ├── ml/              # Ensembles, spread calculators, total forecasters
│   ├── pipeline/        # Ingestion, NBA API, health monitors, latency tracking
│   ├── simulation/      # Headless 2K runner, memory reader, roster injection
│   └── vision/          # OpenCV/YOLO court and spacing analyzers
├── data/                # Cache, predictions, and synthetic training data
├── docs/                # Master spec documents and tech stack references
├── scripts/             # Testing, verification, and data generation utilities
└── tests/               # E2E and unit test suite
```

---

## ⚡ Quickstart

### Prerequisites

- Python 3.10+
- Node.js 18+
- Redis (for WebSocket pub/sub and caching)
- NBA 2K14 (Windows installation required for headless simulation mode — the engine reads and writes directly to the game's memory and `.ROS` roster files via WinAPI/ctypes)

### Backend Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/epoch.git
cd epoch

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env — set your NBA API key, Redis URL, and 2K14 install path

# Launch the FastAPI server
python -m src.api.main
```

### Frontend Setup

```bash
cd src/frontend

# Install dependencies
npm install

# Start the Vite development server
npm run dev
```

The dashboard will be available at `http://localhost:5173`.

---

## 🎯 Features & Roadmap

✅ Automated roster pipeline with live NBA API integration  
✅ Binary `.ROS` file reader/writer for 2K14 roster injection  
✅ Causal ML predictions — real-time spread and total forecasting  
✅ WebSocket dashboard with sub-second latency live game feeds  
✅ Kelly Criterion bet sizing calculator  
🔲 Parallel headless simulation runner (Monte Carlo across multiple 2K14 instances)  
🔲 Fully autonomous betting journal with integrated performance tracking  
🔲 Graph Neural Network upgrade for player interaction modeling  

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Backend API | Python, FastAPI, WebSockets |
| ML / Inference | PyTorch, Scikit-learn, Causal DAGs |
| Graph Models | Graph Neural Networks (GNNs) |
| Simulation | ctypes, WinAPI, custom binary hex parsing |
| Computer Vision | OpenCV, YOLO |
| Frontend | React, Vite, TailwindCSS, Recharts |
| Infrastructure | Redis, asyncio |

---

## 🤖 AI Context Prompt (Antigravity Init)

If you're using an AI coding assistant (Cursor, Claude, ChatGPT, etc.), paste the following as your system prompt or `.cursorrules` file to bring it fully up to speed on this codebase:

```
# MISSION DIRECTIVE: THE EPOCH ENGINE — ANTIGRAVITY INITIALIZATION

You are a principal-level full-stack engineer and data scientist embedded in
"The Epoch Engine" — an event-driven NBA predictive intelligence system.

## System Intent
This is not a CRUD app. It is a live-data prediction engine that:
1. Ingests real-time NBA data via automated pipeline
2. Runs it through causal ML models and fatigue/momentum tracking
3. Injects that state into an NBA 2K14 simulation via binary .ROS file
   modification and direct memory reading using WinAPI/ctypes
4. Returns win probabilities, spread forecasts, and Kelly-sized bet signals

## Core Stack
- Backend: Python, FastAPI, WebSockets, asyncio
- ML: PyTorch, Scikit-learn, Causal DAGs, GNNs
- Simulation: ctypes/WinAPI memory extraction, custom binary hex parsing
- Frontend: React, Vite, TailwindCSS, Recharts

## Structural Domains
- /src/api         — WebSocket nervous system and Stripe monetization endpoints
- /src/binary      — Hex offset parsers for .ROS roster files (handle with care)
- /src/simulation  — Headless 2K14 runner and memory_reader.py state extractor
- /src/intelligence — Causal models, fatigue, momentum, injury detection
- /src/ml          — Spread/total ensembles, Kelly Criterion sizing
- /src/pipeline    — Real-time NBA API ingestion with latency tracking + fallbacks

## Rules
1. All /src/api and /src/pipeline code must be non-blocking — asyncio only.
2. Binary modifications to ros_writer.py / ros_reader.py must handle hex offsets
   precisely. Corruption here breaks the simulation engine entirely.
3. The React frontend uses a terminal-style high-contrast aesthetic.
   Maintain this — command palettes, live gauges, alert feeds.
4. Assume production. Add logging to health_monitor.py. Build fallbacks
   (NBA API → Basketball Reference) wherever data sources can fail.

Acknowledge with: "Antigravity protocols engaged. Epoch Engine synchronized."
```

---

## 📜 License

Distributed under the MIT License. See [LICENSE](LICENSE) for details.
