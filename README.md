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

## 🎭 Personality mirror (no LLM)

Open the existing **💬 AARON-1** tab and expand **Teach AARON-1 your personality**. Tune the **Energy**, **Slang**, and **Humor** sliders; edit the optional words you use; then press **Save my vibe**. That changes AARON-1's stock replies while preserving its existing facts, chat log, and evolution results.

To correct a response, fill in **When someone says…** and **AARON-1 should respond…**, then press **Teach this reply**. The first field defaults to your most recent chat message. Next time it sees the same or a *very similar* phrase, it retrieves your taught reply. You can forget any taught example from the same panel. All of these preferences and examples are stored in the local SQLite database in `data/`. Don't teach it private information you wouldn't want in that local database, and avoid deploying the editable personal profile to a public unauthenticated Streamlit instance.

**Limitations:** This is direct teaching and rule-based tone adaptation, not neural language training, self-awareness, or a copy of a real person's personality. The style sliders mainly affect existing supported intents; unfamiliar questions still need explicit corrections. No LLM or paid API.

Run checks with `python3 -m unittest test_personality.py`.

## 💀 MAX BRAINROT lesson pack (152 examples)

As requested, AARON-1 now ships with **152 explicit cursed conversational examples** covering greetings, internet slang, NPC/aura/67/Ohio memes, Valorant, Buyntiq, school, and softer responses when someone is stressed. On first launch after `git pull`, the existing **💬 AARON-1** tab installs the lessons into the same local SQLite database and sets Energy, Slang, and Humor to 3/3. The robot and agent/evolution checkpoints are untouched.

The training is deliberately simple: phrase-response teaching plus the existing strict near-duplicate matcher. **It is not neural training or general natural-language comprehension**. No LLMs and no APIs. The repo includes examples only; the live Mac's local database is not modified until the updated app runs.

**Preservation rules:** User-taught example replies beat bundled examples. The initial install runs just once, so later edits or deletions stay changed and manually lowered sliders stay lowered. The **💀 MAX BRAINROT — reapply the training** button restores missing bundled lessons and resets the style sliders to max, but does **not** overwrite user-taught corrections. A collapsed **Browse and manage learned replies** toggle keeps 152 lessons from overwhelming the interface.

Try messages like `am i cooked`, `what is rizz`, `i have homework`, `valorant`, `the code is broken`, `mango mango mango`, or `67`.

To use the update in the **same dashboard** (no extra windows), stop Streamlit with Ctrl+C in the existing Terminal, then run:

```bash
cd ~/AARON-1
git pull
source .venv/bin/activate
python3 -m streamlit run app.py
```

Run local checks using `python3 -m unittest test_personality.py test_brainrot.py`.

## 🧠 AARON-1 Agentic Learning v0.1 — real Q-learning, no LLM

This is a **new capability of the same persistent AARON-1**, not a new evolutionary population or replacement identity. The committed initial policy is at `models/agency_seed.json`. It was trained for **50,000 reinforcement-learning episodes / 510,199 tool actions** and, in an independent run of 1,000 newly randomized practice workflows using the same action/state categories, achieved **100% completion and 100% correct actions**. These results measure the deliberately small simulated tasks only and are NOT proof of general intelligence or open-ended problem solving.

**Agent loop:** observe goal and current item → choose a learned tool → see feedback → update Q-values → persist. The trainable component is a goal-conditioned Q-table built from scratch, NOT an LLM, large neural network, or scripted decision mapping. The sandbox inspection tool supplies a category after inspecting an item; the agent learns when to inspect and which tool action to take based on that category. The policy does not understand arbitrary text or discover new categories by itself.

Known practice goals:
- **Organize a practice inbox:** inspect an item; choose Documents, Images, or Code
- **Prioritize a practice to-do list:** inspect a task; choose Do Now, Schedule, or Backlog

Open **🧠 Agency** in the existing Streamlit dashboard. Click **Let AARON-1 execute** to see the complete observation/action/reward trace, or **Train AARON-1** to update its original policy for another 100–10,000 episodes without a new Terminal. AARON-1's local policy is saved in ignored `data/agency_policy.json`; existing learning is NEVER replaced by `git pull`. You can also type **organize a practice inbox** or **prioritize practice tasks** into the AARON-1 chat to execute the simulated skills.

**Read-only tool preview:** the Agency tab can list filenames/extensions in the restricted folder `data/agency_preview/` (create/use it via Finder) and use the learned policy to *propose* folders. It never reads contents, moves, deletes, or renames files. The default permitted root cannot be escaped with sibling paths or symlinks. The person running the server can explicitly set `AARON_AGENCY_PREVIEW_ROOT` if they wish to authorize a different preview folder; do not expose a publicly accessible Streamlit dashboard to an unrestricted root.

### Continue training locally

In your one existing Streamlit Terminal, stop the foreground app with **Ctrl+C**, then:

```bash
cd ~/AARON-1
git pull
source .venv/bin/activate
python3 -m streamlit run app.py
```

Use the Agency tab to train and run goals — no separate training window needed.

Alternatively, advanced users can run **CPU-only** training directly:

```bash
python3 agency.py --episodes 100000
python3 -m unittest test_agency.py
```

The same script runs on Windows with Python 3.10+; it currently doesn't use or benefit from a GPU. A more capable neural agent could later use your gaming PC, but that would require a separate architecture, a task dataset, and proper independent evaluation. Neither this repo nor ChatGPT remotely accesses your PC.

**Safety/limits:** AARON-1 cannot yet browse arbitrary sites, change real files, operate apps, edit repositories, or perform unapproved actions on its own. The practice policy only works within the two explicitly defined goals. Any future real-world actions should be tool-scoped and require permission for destructive changes. Persistent chat memory remains separate from the learned control policy.
