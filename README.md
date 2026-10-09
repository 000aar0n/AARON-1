# AARON-1 🧠

**An experimental multi-agent cooperation laboratory.** Two small reinforcement-learning agents discover a signaling protocol to solve hidden-location puzzles. A curriculum expands the symbol space when the current task is mastered.

## Run locally on macOS

Use Python 3.10+.

```bash
git clone https://github.com/000aar0n/AARON-1.git
cd AARON-1
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Start the **trainer** in Terminal window 1:

```bash
python3 trainer.py
```

Start the **Streamlit dashboard** in Terminal window 2:

```bash
source .venv/bin/activate
streamlit run app.py
```

Visit http://localhost:8501.

The trainer remains running if you close or refresh your browser, but **stops when the Mac sleeps**. Stop with Ctrl+C. Checkpoints are saved automatically under `data/`. The Streamlit pause switch controls the local trainer.

## Streamlit Community Cloud

Use `app.py` as the entrypoint. The app will display a no-checkpoint message: **the cloud dashboard cannot see the local trainer's files**. To publish live training results later, add a shared remote data store and authentication. The cloud app by itself is not a 24/7 training service.

## What is and is not learned?

This version trains **tabular policies**, not large language models. Agent A sees a hidden target and chooses one of N arbitrary signals. Agent B observes only the signal and guesses a target. Shared reward reinforces useful codes. Both policies start without a mapping. Exact greedy accuracy across known target states is displayed; training accuracy reflects exploration.

Each curriculum expansion initializes a fresh policy, while retaining the overall training history. This is increasing task complexity, **not** genetic evolution, self-rewriting, or proof of generalization to unseen concepts. Future experiments can add genuine policy evolution, compositional signals, and held-out tasks.

## Files

- `engine.py` — independent sender/receiver reinforcement-learning policies
- `trainer.py` — continuous separate process, saves atomic checkpoints
- `app.py` — read-only metrics and pause/resume dashboard
- `requirements.txt` — web UI dependencies
