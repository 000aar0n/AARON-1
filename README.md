# 🤖 AARON-1 — your personal assistant

**One assistant. Four tabs. No agent network or API fees. Local conversational AI is optional.**

This version has replaced the sender/receiver, evolution, and sandbox-network experiments. Old experiment source files were removed. Files and checkpoints already saved on your computer under `data/` were **not deleted**; previously taught personal facts are migrated into the new task database.

## What can it actually do?

- **🗓️ Planner:** an interactive FullCalendar view with **Month / Week / Day / Agenda**, clickable timed events and task deadlines, descriptions, due times, event lengths, and a quick editor. No Google Calendar account/sync is required; this is the local AARON-1 calendar, styled and operated like Google Calendar.
- **🎯 Priorities:** "What should I do next?" ordered by the actual time due, a 1–4 priority level you set, your feedback, and estimated work time. Each task gives a readable reason, not an unexplained AI score.
- **💬 Conversation:** talk about your day, ask what's due, or create tasks in chat. Optional **Ollama** enables much more natural, multi-turn local conversations. The pretrained Ollama model only handles language — AARON-1 owns your tasks, context and explicit actions.
- **💬 Chat:** simple commands like `what homework is due`, `add task read chapter 3`, `check my email`, or `my favorite subject is chemistry`.
- **✅ Task controls:** add, edit, prioritize, finish and reopen tasks. New entries can have descriptions, dates, clock times and effort estimates. The **Important** action also teaches the local priority model.
- **🔗 Connect:** import school assignments from an .ics calendar export or .csv file. Optionally authorize a personal **Gmail** account using Google's own OAuth sign-in, with **read-only** Gmail access. Browse inbox subjects and snippets, search school-related email, and explicitly add a message as a task.

Without Ollama, AARON-1 **does not** have a general-purpose language model: its chat is based on explicit commands and rules. An optional locally running pretrained Ollama model enables more natural conversation but is not AARON-1 training a neural model from scratch. It continues learning priority weights from your feedback. It never sends/deletes emails, logs in to Blackbaud, completes homework, edits files, or acts without approval.

## Run on your Mac — one Terminal, one browser tab

If you've already installed AARON-1:

```bash
cd ~/AARON-1
git pull
source .venv/bin/activate
python3 -m pip install --upgrade -r requirements.txt
python3 -m streamlit run app.py
```

Refresh your existing browser tab at http://localhost:8501. The interface uses a dark, minimalist style and shows **Planner**, **Priorities**, **Chat**, and **Connections** tabs. You no longer need to start `trainer.py`, `evolution.py`, or any other background training process. Use Ctrl+C in the existing Streamlit Terminal to stop before rerunning.

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

In **Chat → Conversation settings**, you can pick from installed local [Ollama](https://ollama.com/) models. This makes AARON-1 much better at actual back-and-forth dialogue and discussing the assignments it knows about. The language model receives recent conversation and a small digest of your local task priorities, through `127.0.0.1` only. It has **no Gmail or task-mutating tools**. All actual calendar updates are processed by AARON-1's verified planner code; arbitrary LLM text cannot silently write to your calendar.

1. Install [Ollama](https://ollama.com/download) for macOS or Windows and start it.
2. In a Terminal, run `ollama pull qwen2.5:3b` to download a modest open-weight conversational model.
3. Refresh the AARON-1 browser tab and choose that model in **Chat → Conversation settings**.

Without Ollama you can still ask `what should I do next?`, `what homework is due`, `what is on my schedule tomorrow`, or say `add task chemistry homework due tomorrow at 5pm`. AARON-1's fallback conversation remains limited; it doesn't pretend otherwise.

**Tests:** `python3 -m unittest -v test_assistant.py test_planner.py`.
