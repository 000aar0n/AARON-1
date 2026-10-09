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

## 🧬 Evolution v0.2 (separate experiment)

First pull the latest code:

```bash
cd ~/AARON-1
git pull
```

Open a **third Terminal** in the same folder (your original `trainer.py` and `streamlit run app.py` can stay running):

```bash
cd ~/AARON-1
source .venv/bin/activate
python3 evolution.py
```

Open the **Evolution** tab of your existing Streamlit dashboard. You'll see the best and mean cooperation fitness for a population of 48 pairs, and you can pause the evolution worker. Stop the worker with Ctrl+C. Progress is saved separately in `data/evolution_checkpoint.json` and resumes automatically.

To test the new engine:

```bash
python3 -m unittest test_evolution.py
```

**Scientific limitations:** Selection, mutation, crossover, and elitism are real genetic-algorithm mechanisms. The genomes encode lookup-score policies, not self-modifying neural networks; the eight tasks used to measure fitness are the same tasks used in selection. Thus improved fitness does not establish generalization, emergent grammar, or useful real-world intelligence. Those are future research steps. Keep both workers on your Mac; Streamlit Community Cloud will not connect to these local processes automatically.

## 💬 AARON-1 individual (no LLM)

The **AARON-1** Streamlit tab provides an offline teachable chat system using only Python and SQLite. It remembers simple facts and user-taught word meanings across restarts. No Ollama, ChatGPT, APIs, pretrained language models, or GPU are required.

To update on your Mac, run `cd ~/AARON-1 && git pull` and refresh the existing Streamlit page. The new tab includes examples and a separate trained-symbol channel for the sender and receiver agents.

Example messages:
- `my favorite food is ramen`
- `what is my favorite food`
- `teach: sup = greeting`
- `sup`

This version **does not** train neural language comprehension. Teaching a word stores a mapping; it does not magically give an AI natural-language understanding. Free-form conversation will be limited until we build grounded language-learning tasks that update a trainable model. Chat logs and taught information remain local in `data/aaron_individual.sqlite3`.

## 🎭 Cartoon avatar and voice

The **💬 AARON-1** tab now displays a cartoon character. Eyes blink, its head gently moves, and its mouth animates while the browser's built-in speech synthesis reads the latest AI response. Press **Speak reply** to trigger it; use **Stop** to cancel. Speech playback requires browser support and user interaction. It doesn't add an LLM, pretrained conversational intelligence, or voice-to-voice interaction, and the mouth uses an approximate animation rather than phoneme-accurate lip sync.

To get the latest interface:

```bash
cd ~/AARON-1
git pull
```

Refresh Streamlit and open **💬 AARON-1**. Your existing saved conversations and training checkpoints remain in the ignored `data/` directory.

## 🤖 Robot avatar (latest)

The AARON-1 chat tab now renders an animated robot instead of a human cartoon. **Test mouth** always runs a visual-only mouth animation, even if speech isn't supported. **Speak reply** tries your browser's built-in text-to-speech and starts mouth animation immediately; speech may be unavailable in a browser's embedded iframe, so sound is not guaranteed. No LLM or external speech API is used.

To update the **existing** local dashboard, stop the Streamlit foreground process with Ctrl+C in its existing Terminal, then run:

```bash
cd ~/AARON-1
git pull
source .venv/bin/activate
python3 -m streamlit run app.py
```

Refresh your existing browser tab; no new windows are required. Local training checkpoints and memories are preserved.
