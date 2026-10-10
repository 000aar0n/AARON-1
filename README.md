# 🤖 AARON-1 — your personal assistant

**One assistant. Five tabs. Persistent memory, Google Calendar ZIP import, Winter Arc workouts, and a fine-tunable local conversational model.**

This version has replaced the sender/receiver, evolution, and sandbox-network experiments. Old experiment source files were removed. Files and checkpoints already saved on your computer under `data/` were **not deleted**; previously taught personal facts are migrated into the new task database.

## Run this version on your school Mac (no admin / Homebrew)

If you already created `.venv312` using `uv`, **do not reinstall anything**.
After stopping the old Streamlit process with `Control+C`, update to the
current `main` branch and start the Python 3.12 environment:

```bash
cd ~/AARON-1
git status --short --branch
git pull --ff-only origin main
grep -n '_render_editor(scope=' planner_ui.py
.venv312/bin/python --version
.venv312/bin/python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

**The crucial check** is that `grep` finds the Planner popup and
Priorities editors. If Git reports a merge/checkout error, the local files
are stale; don't delete or reset your work. Resolve the Git error before
launching the app. In the running UI, look for
**`AARON-1 build 2026.10.10-grounded-calendar-v9`** near the top.
Stop any old Streamlit terminals before restarting, and reload the browser.

### Delete one task or clear all tasks you entered

- **Priorities → All tasks · including completed → Delete → Yes, delete task**
  deletes any local task you choose. Deleting an imported copy never changes
  the original Blackbaud assignment or email.
- **Priorities → Clear all tasks I added** shows how many manually entered
  tasks (including completed tasks) would be removed. Check the confirmation
  box and click the delete button to clear them. It creates a full SQLite
  backup in `data/backups/` before deletion.
- **Events, imported school/calendar/email tasks, memories, training data,
  and chat history are excluded** from that bulk clear. You can remove any
  imported task individually if you want.

Alternatively, from Terminal, preview the cleanup without changing anything:

```bash
cd ~/AARON-1
.venv312/bin/python clear_my_tasks.py
```

Then run the explicitly confirmed one-time operation:

```bash
.venv312/bin/python clear_my_tasks.py --yes
```

This command runs only on your computer; GitHub and ChatGPT cannot see or
directly wipe your local task database. It prints the location of the backup.

## Google Calendar ZIP import + Winter Arc reminders (October 2026)

The **Connections → Google Calendar — private import** panel accepts either
`.ics` files or Google's original `.ics.zip` downloads **without unzipping**.
A typical export can decompress to 16 MB or more: the importer safely handles
up to **40 MB of uncompressed calendar data**, without the old 2 MB school
calendar import limit. It skips older events outside your selected date range,
preserves original start/end times (including all-day and multi-day events),
expands recurring instances, applies moved/cancelled sessions, and avoids
duplicates when importing the same archive again.

**On your Mac with the existing Python 3.12 environment:**

```bash
cd ~/AARON-1
git pull --ff-only origin main
.venv312/bin/python -m pip install -r requirements.txt
.venv312/bin/python -m streamlit run app.py
```

Look for **AARON-1 build 2026.10.10-calendar-winterarc-v4** near the top.
Then open **Connections → Google Calendar**, drag in the ZIP, and click
**Import Google Calendar**. The default range is from 30 days ago through
18 months afterward; choose a different range before importing if needed.
This is a **one-time local copy**, not continuous sync, and it does not change
your actual Google account or require Google OAuth. The personal calendar file
and imported SQLite data are excluded from GitHub. **Never commit the ZIP, ICS,
or a copied personal database to a public repository.**

The first updated launch also seeds the requested **Winter Arc** workouts from
**October 8 through December 30, 2026**: **Monday/Thursday Push + Core** and
**Tuesday/Friday Pull + Legs**. There are 48 all-day workout calendar entries,
each with the exact exercise list and rep targets from the Winter Arc tracker.
The last training date is December 29; December 30 is a recovery day. You can
edit or delete a workout and the app won't re-add it on later reruns. Planner
also shows today's workout or the next workout as a reminder when you open
the app. AARON-1 itself doesn't issue push alerts when closed; use scheduled
phone/ChatGPT notifications for that.

## Imported calendar is personal — no manual verification

AARON-1 displays **all the events in your imported Google Calendar**, as
requested. You do **not** have to mark classes as "Mine" individually. This
reverses the earlier, incorrect enrollment-verification gate without clearing,
replacing, or modifying your local SQLite calendar database. Any legacy
"unverified" flags are ignored.

The source of the earlier invented timetable was the conversational AI:
having a snippet of calendar data in a language model prompt does NOT
guarantee that it will quote only real appointments. This build fixes personal
calendar questions with **deterministic database retrieval** instead of
model-generated schedule text. Questions about classes, teachers, classroom
locations, named courses, and upcoming events are answered using ONLY
recorded event titles, dates, times, and notes, or AARON-1 says the details
aren't present. Imported items are identified as such in the chat. Entries
that aren't saved cannot be inferred or added to the answer.

Examples: `What classes am I taking?`, `What's on my calendar Friday?`,
`When's my next Chinese class?`, `Who is my Chinese teacher?`, and
`Where is my Chemistry class?`. Teacher/room answers require literal
information in the event's saved notes; otherwise AARON-1 says it's missing.

This is NOT a live connection to Google; it reads only the local data last
imported to AARON-1. If something is absent, import the current calendar
again via Connections. Never upload a personal ICS export or database to
this public GitHub repository.

The **Readable Week** calendar view continues to display fully wrapping
event cards. A scrollable 390px **Every title, fully readable** list is
available below it; the optional Hour Grid preserves a classic time view.

## Local calendar questions and scrollable AI chat

AARON-1 can now **read your local calendar and class schedule** in Chat.
Without any AI model, it answers direct questions from actual saved events:

- `What's on my calendar next week?` — classes, homework, and other events,
  including weekly repeating occurrences
- `When is my next Chemistry class?` — upcoming class dates and local times
- `What's my schedule?` — your next seven days

When using the pretrained or fine-tuned local model for **non-calendar**
conversation, its prompt receives a bounded 14-day read-only snapshot.
**Personal schedule questions bypass the model entirely**, because a
generative model can invent even when calendar context is included. The verified
existing add-task chat command is unchanged. School calendar content remains
on your Mac and is not committed to the public repository.

Chat messages now appear in a **550px-tall scrollable history window** above
the input. You can scroll older conversations while keeping the message
composer on screen. The application stores the complete chat history in its
local SQLite database; the interface displays the most recent 60 messages at
once to stay responsive.

The calendar also provides strong **hover, keyboard-focus and persistent
clicked-event highlighting**, including a gold outline that remains after
closing the event's popup so it's obvious which class you last selected.

## Full-width calendar and pop-up editor

The **Planner** calendar now uses the full available width instead of sharing
the screen with an always-visible event editor. It uses an auto-height **Readable Week** layout, with clearer multi-line
event titles and non-overlapping cards. The optional Hour Grid still displays
timed appointments.
Blue means **Classes** in the legend (your school calendar imported from
Google), green is Winter Arc, and other colors indicate events and homework.

Click a calendar class/event/assignment to open its details in a **large
popup**, including the full title, notes, and linked assignments. Click an
empty calendar date or drag across a time range to open a new-event popup.
The **+ New task** and **+ New event** buttons above the calendar do the same.
Saving or canceling closes the popup without shrinking the calendar. The
Priorities page retains its own editor, with distinct Streamlit widget keys.

Use **Month / Week / Day / Agenda** to switch views; the Month view shows more
event rows before its built-in **+ more** popup. Google imports are still
read-only and local, and this update does not delete or reset tasks.

## Calendar color coding, weekly events, and attached assignments

In **Planner**, click an existing calendar item or **+ Event** / **+ New task**.
Each editor has a **Calendar color** dropdown; choose Blue, Purple, Teal,
Green, Orange, Pink, Red or Slate, or leave **Auto**. Auto colors distinguish
imported Google Calendar appointments, Winter Arc workouts, ordinary events,
and task priority. Linked assignments inherit their event color automatically
unless you choose a custom color.

To make a repeating class, choose **Event**, check **Repeat every week**, set
the first date/time, choose **Repeat weekly until**, and save. AARON-1 creates
virtual weekly occurrences from one saved event record (no duplicate database
rows). Click any occurrence to edit **the entire series**, including its end
date and color; deleting the parent removes the series. This simple weekly
option repeats on the weekday of the first occurrence, through the inclusive
end date (up to three years). It does not support individual occurrence
exceptions; imported Google recurring events retain their separately expanded
calendar instances and are not modified at Google.

To attach homework to class, open the **Task** editor and pick
**Attach assignment to an event**. Or click a class event and choose
**Add assignment to this event**; attached tasks appear directly in that
event's editor, but retain independent deadlines, completion status and
priority. An assignment attached to a repeating event is linked to the whole
series. Deleting the class event does *not* delete the homework: it removes
the relationship and keeps the task.

Calendar titles are bolder and use multi-line wrapping in Week, Day, Month and
Agenda views. These features are all local; they don't edit Google Calendar.

## No Ollama needed: talk to pretrained AARON-1

You **do not need Ollama**. AARON-1 can now run the Qwen2.5 0.5B-Instruct language model directly with PyTorch/Transformers, even **before you have any fine-tuning examples**. This model already understands basic language; it won't initially have a personality tailored to you. Fine-tune it later from the **Train AARON-1** tab.

```bash
cd ~/AARON-1
git pull
source .venv/bin/activate
python3 -m pip install --upgrade -r requirements.txt
python3 -m pip install -r requirements-training.txt
python3 -m streamlit run app.py
```

Go to **Chat → Conversation settings** and choose **AARON-1 (pretrained · no Ollama)**. The **first actual chat** downloads the pretrained Qwen weights from Hugging Face and caches them on your computer (internet required for the first download); later chats run locally, without the Ollama server or API keys. When you've approved enough training examples and finished a LoRA run, activate your adapter and select **AARON-1 (fine-tuned)**.

The model is modest (0.5 billion parameters), so don't expect ChatGPT-level reasoning. On an M4 Mac with 16 GB RAM it's a sensible starting point, although real-world speed and compatibility still require a local test. AARON-1 keeps calendar data and private memory in its SQLite database, and neither mode automatically sends your data to model providers for inference.

## What can it actually do?

- **🗓️ Planner:** an interactive FullCalendar view with **Month / Week / Day / Agenda**, clickable timed events and task deadlines, descriptions, due times, event lengths, and a quick editor. No Google Calendar account/sync is required; this is the local AARON-1 calendar, styled and operated like Google Calendar.
- **🎯 Priorities:** "What should I do next?" ordered by the actual time due, a 1–4 priority level you set, your feedback, and estimated work time. Each task gives a readable reason, not an unexplained AI score.
- **💬 Conversation:** talk about your day, ask what's due, or create tasks in chat. Use Ollama OR your own fine-tuned LoRA adapter for natural multi-turn replies. AARON-1 still owns its tasks, memory and approved tool actions.\n- **🧠 Train AARON-1:** explicitly approve example replies, fine-tune a small pretrained Qwen2.5 model's LoRA weights, compare held-out losses, and activate the trained adapter in Chat.
- **💬 Chat:** simple commands like `what homework is due`, `add task read chapter 3`, `check my email`, or `my favorite subject is chemistry`.
- **✅ Task controls:** add, edit, prioritize, finish and reopen tasks. New entries can have descriptions, dates, clock times and effort estimates. The **Important** action also teaches the local priority model.
- **🔗 Connect:** import school assignments from an .ics calendar export or .csv file. Optionally authorize a personal **Gmail** account using Google's own OAuth sign-in, with **read-only** Gmail access. Browse inbox subjects and snippets, search school-related email, and explicitly add a message as a task.

AARON-1 offers **direct pretrained Qwen chat without Ollama**, optional Ollama, or rule-based chat. It can also load a locally fine-tuned adapter after a deliberate training run. The language model cannot mutate tasks except through verified application commands, and Gmail remains read-only. Personal task-priority feedback is saved locally.

## Run on your Mac — one Terminal, one browser tab

If you've already installed AARON-1:

```bash
cd ~/AARON-1
git pull
source .venv/bin/activate
python3 -m pip install --upgrade -r requirements.txt
python3 -m streamlit run app.py
```

Refresh your existing browser tab at http://localhost:8501. The interface uses a dark, minimalist style and shows **Planner**, **Priorities**, **Chat**, **Train AARON-1**, and **Connections** tabs. You no longer need to start `trainer.py`, `evolution.py`, or any other background training process. Use Ctrl+C in the existing Streamlit Terminal to stop before rerunning.

First-time install:

```bash
git clone https://github.com/000aar0n/AARON-1.git
cd AARON-1
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 -m streamlit run app.py
```

## Gmail connection (optional; personal Gmail works)

Google's API requires **your own Google Cloud OAuth client** for a privately run app. This is a one-time setup; there is no way to secretly give an app your Gmail access.

1. In [Google Cloud Console](https://console.cloud.google.com/), make a project and enable the [Gmail API](https://console.cloud.google.com/apis/library/gmail.googleapis.com).
2. Configure **Google Auth Platform → Branding/Audience/Data access**. For personal testing, choose **External** and add the Gmail account you will use as a **test user** if Google prompts you. Request Gmail read-only scope (`https://www.googleapis.com/auth/gmail.readonly`) in the consent configuration as needed.
3. Under **Clients**, create an OAuth 2.0 client of type **Web application**. Add **`http://localhost:8501`** to its **authorized redirect URIs**.
4. Download the client JSON. Open AARON-1's **🔗 Connect** tab, upload that file and click **Save Google connection setup**.
5. Click **Start Gmail authorization** → **Continue to Google authorization**. Review the read-only permission and approve it. Google returns to your existing dashboard; no email is sent.

**Do not share a Gmail password**, and do not commit OAuth client JSON or refresh tokens to GitHub. They stay in the gitignored local `data/` folder, and tokens are saved with owner-only file permissions. The **Disconnect Gmail** button removes the local token (Google's account permissions can also be revoked in your Google Account).

Google classifies `gmail.readonly` as a **restricted OAuth scope**. Public deployment can require verification and an additional security assessment. The flow in this repo is intended only for your own **localhost** machine with a testing OAuth project. Google can show an unverified-app warning or revoke short-lived test authorization; reauthorization may be necessary. See Google's [official API Python quickstart](https://developers.google.com/workspace/gmail/api/quickstart/python), [scope documentation](https://developers.google.com/workspace/gmail/api/auth/scopes), and [web OAuth guide](https://developers.google.com/identity/protocols/oauth2/web-server).

**Privacy:** AARON-1 fetches email headers and short snippets only after you click to search or explicitly request inbox information in chat. It does not store full message bodies. You can explicitly add an email subject/snippet to the local task database.

## School assignments / Blackbaud

AARON-1 **does not** have direct Blackbaud login or continuous synchronization. If your school exposes an iCal/ICS feed or a CSV export of assignment events, save that **file** and upload it under **🔗 Connect → School assignments**. Blackbaud's iCal feeds depend on school administrators enabling calendar export. Imported events are deduplicated by event ID, where available. Personal Gmail can also be searched for assignment-related notices, but it won't magically contain your school's Blackbaud data.

The import creates local tasks only. It doesn't change assignments, grades, or submissions in Blackbaud.

## How AARON-1 learns

The priority model is a tiny logistic learner trained from scratch on **60,000 generated practice examples** representing deadlines and urgency. Its synthetic holdout accuracy was **88.84% over 8,000 generated examples**. This isn't real-student predictive performance. The bundled starting weights are in `models/priority_seed.json`. Every **Important** / **Not urgent** press updates *your* local weights and persists them in `data/priority_weights.json`.

The app also remembers facts you explicitly tell it (`my X is Y`) in local SQLite. If your old `data/aaron_individual.sqlite3` database exists, the new app reads its explicit user facts once without deleting it.

No GPU is needed for this version. A future more sophisticated agent could train on your gaming PC, but this one works on the Mac's CPU.

## Tests

```bash
python3 -m unittest -v test_assistant.py
```

GitHub Actions checks syntax and runs these tests on pushes. OAuth live authorization has to be tested on your Mac, with your permission.

## UI design

The dashboard uses an integrated dark visual system in `ui_theme.py` and `.streamlit/config.toml`: charcoal backgrounds, restrained violet and mint accents, and a full interactive FullCalendar calendar with month/week/day/agenda modes. The style change does not reset any local tasks or authentication state. The calendar and the assignment list use the same SQLite task database.

## Planner details

Everything is stored in the existing `data/aaron_personal.sqlite3`. The first upgraded run adds optional columns to the task table: `due_time`, `item_type`, `duration_min`, `estimated_min`, and `priority_level`; **it never drops old tasks**. Existing imported assignments default to all-day tasks with Normal priority. Previous descriptions already in `notes` are preserved.

Use **Planner** to create **Task** (due date, due time, importance, estimate) or **Event** (start time, duration). Click an existing entry to edit its title, description, date, time, priority, or length. All-day tasks are supported. Deletion requires confirming it in the editor. Completing an assignment does NOT change Blackbaud or Gmail.

The **Priorities** page and **Your next moves** below the calendar rank unfinished tasks. Urgent/due-soon deadlines take precedence over low-priority distant work; AARON-1's previously trained priority scorer contributes a smaller personalization signal. This is a **heuristic/planning policy with online feedback**, not a learned prediction of how you'll perform or an autonomous homework-completion agent.

**Timezones:** all saved date/time values are currently treated as the local clock time of the machine running Streamlit. This is intended for a local Mac/PC installation and does not automatically synchronize time zones across devices. No external Google Calendar sync is implemented.

## Conversational AARON-1 (optional, local only)

In **Chat → Conversation settings**, you can choose the native pretrained Qwen model (no Ollama), a trained adapter, or an optional local [Ollama](https://ollama.com/) model. This makes AARON-1 much better at actual back-and-forth dialogue and discussing the assignments it knows about. The language model receives recent conversation and a small digest of your local task priorities, through `127.0.0.1` only. It has **no Gmail or task-mutating tools**. All actual calendar updates are processed by AARON-1's verified planner code; arbitrary LLM text cannot silently write to your calendar.

1. Install [Ollama](https://ollama.com/download) for macOS or Windows and start it.
2. In a Terminal, run `ollama pull qwen2.5:3b` to download a modest open-weight conversational model.
3. Refresh the AARON-1 browser tab and choose that model in **Chat → Conversation settings**.

Without Ollama you can still ask `what should I do next?`, `what homework is due`, `what is on my schedule tomorrow`, or say `add task chemistry homework due tomorrow at 5pm`. AARON-1's fallback conversation remains limited; it doesn't pretend otherwise.

**Tests:** `python3 -m unittest -v test_assistant.py test_planner.py test_training.py test_planner_widgets.py test_task_cleanup.py`.

## 🧠 Train AARON-1 — actual model fine-tuning

AARON-1 can now use a **partially trained but still trainable model**. The starting point is [Qwen2.5-0.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct) (or an optional 1.5B version). This is an existing open-weight language model; **you are not training billions of parameters from scratch**. The optional **PyTorch + PEFT LoRA** implementation trains adapter weights using gradient descent from examples you approve.

### Setup on the Mac currently running AARON-1

Start your existing Streamlit app as before. To enable real training and trained-adapter inference, stop Streamlit first (`Control+C`) and run:

```bash
cd ~/AARON-1
git pull
source .venv/bin/activate
python3 -m pip install --upgrade -r requirements.txt
python3 -m pip install -r requirements-training.txt
python3 -m streamlit run app.py --server.address 127.0.0.1
```

The training dependencies are optional and significantly larger than the basic application dependencies. The 0.5B starter model downloads from Hugging Face the first time it is trained or loaded. On an M-series Mac, PyTorch's MPS may work; otherwise it can train on CPU more slowly. AARON-1 does not silently access an external API to run inference.

### How to train it in the dashboard

1. Open **Train AARON-1**. Write pairs such as **When I say:** `I have a chemistry quiz tomorrow` → **Preferred answer:** `Let's knock out the hardest concepts first. What topics are on it?` and click **Save approved example**. You can also choose an existing chat message, edit the response, and explicitly approve that pair.
2. Approve at least **8 distinct prompt/response examples**. **30–100+ varied examples** are much more useful and less prone to memorization.
3. Choose **Qwen2.5 0.5B**, set training passes (default 3), then click **Train AARON-1 on this computer**. This starts a local worker and updates a LoRA adapter; it never edits your original downloaded base weights. On later runs, select **Continue training my current AARON-1 adapter** to start from the previous learned weights rather than a fresh adapter (the base model must match). You can also uncheck it to reset and retrain from the pretrained base.
4. Refresh training status to see the local run log, training loss and **held-out validation loss before and after**. Compare on actual prompts too: a lower loss on just a few validation examples does not establish that the model is generally better.
5. Click **Use this fine-tuned AARON-1**, then open **Chat → Conversation settings** and select **AARON-1 (fine-tuned)**. Chat loads the adapter with the exact corresponding base model.

Training examples, frozen job snapshots, weights, job logs and token files are all saved under **`data/`**, already excluded from Git. **No Gmail, Blackbaud, or chat contents are automatically added to the training dataset.** Export approved examples from the Train tab if you deliberately want to move them to another computer. Correcting an already approved prompt replaces its older target for subsequent training; it does not undo its effect on previously trained adapters.

Important distinction: **Your calendar facts and task list are still stored separately in SQLite**. Fine-tuning teaches conversational *behavior and style*, not up-to-the-minute school assignments. AARON-1 injects approved local memory and upcoming tasks into conversational context each time. Calendar/email operations are explicit verified application actions, not model hallucinations.

### Train on your gaming PC (AMD Radeon RX 9060 XT)

The **GPU machine must host the training worker** (it isn't accessed remotely from ChatGPT or the Mac). To carry the approved dataset over, use **Train → Export training examples**, copy that private JSONL file to your PC, then use **Train → Import** there.

AMD's 2026 [PyTorch on Windows 7.2.1 compatibility announcement](https://www.amd.com/en/resources/support-articles/release-notes/RN-AMDGPU-WINDOWS-PYTORCH-7-2-1.html) explicitly lists the RX 9060 XT. But you need a compatible **Windows 11 / Python 3.12 / driver / ROCm PyTorch** combination; simply running `pip install torch` doesn't guarantee GPU training. Use AMD's [PyTorch installation instructions](https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/install/installrad/windows/install-pytorch.html) for the correct wheels first, then install `requirements-training.txt` in that same environment.

Alternatively a supported Linux ROCm configuration may be used. Python 3.14 or old AMD drivers may not have compatible wheels. Test `python -c "import torch; print(torch.cuda.is_available(), torch.version.hip)"` on the PC before starting a substantial run. AARON-1 uses CUDA-compatible PyTorch calls for AMD ROCm too.

To run the dashboard on a separately configured PC, clone the repository, activate the correct virtual environment, install basic and training requirements, and start `python -m streamlit run app.py --server.address 127.0.0.1`. The first run imports approved examples using your manually transferred JSONL. No existing Mac database is magically synced to the PC.

### Engineering and privacy details

- The training pipeline uses LoRA on Qwen attention projections, with the **system/user prefix masked out of the loss**. Only assistant target tokens receive gradient updates.
- Each run makes a fixed split with **20% of its approved pairs (minimum 2)** held out for evaluation. With incremental runs, previously seen samples may move between train and evaluation splits; use new questions for a more trustworthy independent comparison.
- The frozen dataset, adapter checkpoints and `active_finetune.json` remain local; you can switch to a base model any time.
- The local model can discuss your schedule. It **does not get unrestricted file, Gmail, or internet access**, nor can it automatically modify your calendar by writing arbitrary generated text.
- Fine-tuning is an explicitly initiated, compute-intensive action. It is *not* continuous self-modification, and quality is not guaranteed. Keep a backup of important private data and avoid running an unprotected Streamlit instance over the public internet.

**Offline tests:** `python3 -m unittest -v test_assistant.py test_planner.py test_training.py`. These test the fine-tuning control flow, data isolation, prompt masking, and adapter selection **without downloading or actually training a large neural model**. You must execute at least one real training run locally before claiming GPU compatibility and real-world quality.
