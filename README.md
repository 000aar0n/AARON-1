# 🤖 AARON-1 — your personal assistant

**One assistant. Three tabs. No agent network, no LLM, no API fees.**

This version has replaced the sender/receiver, evolution, and sandbox-network experiments. Old experiment source files were removed. Files and checkpoints already saved on your computer under `data/` were **not deleted**; previously taught personal facts are migrated into the new task database.

## What can it actually do?

- **💬 Chat:** simple commands like `what homework is due`, `add task read chapter 3`, `check my email`, or `my favorite subject is chemistry`.
- **✅ Tasks:** manually add, prioritize, complete, and reopen assignments. The **Important** / **Not urgent** buttons train a small personal priority model.
- **🔗 Connect:** import school assignments from an .ics calendar export or .csv file. Optionally authorize a personal **Gmail** account using Google's own OAuth sign-in, with **read-only** Gmail access. Browse inbox subjects and snippets, search school-related email, and explicitly add a message as a task.

AARON-1 **does not** have a general-purpose language model. It learns task-priority weights from your feedback, not arbitrary English or human-like reasoning. It never sends/deletes emails, logs in to Blackbaud, completes homework, edits files, or acts without approval.

## Run on your Mac — one Terminal, one browser tab

If you've already installed AARON-1:

```bash
cd ~/AARON-1
git pull
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 -m streamlit run app.py
```

Refresh your existing browser tab at http://localhost:8501. You no longer need to start `trainer.py`, `evolution.py`, or any other background training process. Use Ctrl+C in the existing Streamlit Terminal to stop before rerunning.

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
