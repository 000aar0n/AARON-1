"""Streamlit monitoring UI; trainer runs independently of this process."""
import json
import time
from pathlib import Path
import pandas as pd
import streamlit as st
from individual import respond, history, vocabulary, symbolic_peer
from avatar import render_face
from agency import GOALS, ACTIONS, ACTION_LABELS, load_agent, preview_local_folder
from personality import (get_profile, save_profile, teach_reply, learned_examples,
                         forget_example, ensure_brainrot_training, training_stats)

st.set_page_config(page_title="AARON-1 | Evolution Lab", page_icon="🧠", layout="wide")
DATA = Path("data")
DATA.mkdir(exist_ok=True)
STATUS = DATA / "status.json"
CONTROL = DATA / "control.json"

def read(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}

def write_control(paused):
    CONTROL.write_text(json.dumps({"paused": paused}), encoding="utf-8")

st.title("🧠 AARON-1")
st.caption("One persistent local agent · learned tools · memory · experiments")
st.info("Agency training runs in this dashboard without extra windows. The other experiments require their existing local trainers. Streamlit Cloud cannot see Mac-local checkpoints.")

@st.fragment(run_every="2s")
def monitor():
    data = read(STATUS)
    control = read(CONTROL)
    alive = data.get("running") and time.time() - data.get("updated_at", 0) < 12
    left, right = st.columns([3, 1])
    with left:
        st.subheader("🟢 Trainer online" if alive else "⚪ Trainer offline")
    with right:
        paused = st.toggle("Pause local training", value=control.get("paused", False),
                           disabled=not alive, key="pause")
        if alive and paused != control.get("paused", False):
            write_control(paused)
    if not data:
        st.warning("No checkpoints yet. Start `python3 trainer.py` in another terminal.")
        st.code("python3 trainer.py", language="bash")
        return
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Generations", data.get("generation", 0))
    c2.metric("Training episodes", f"{data.get('total_episodes', 0):,}")
    c3.metric("Signal vocabulary", data.get("symbols", 4))
    c4.metric("Greedy success", f"{100*data.get('greedy_accuracy', 0):.0f}%")
    st.caption(data.get("event", ""))
    hist = pd.DataFrame(data.get("history", []))
    if not hist.empty:
        st.subheader("Learning progress")
        st.line_chart(hist.set_index("generation")[["train_accuracy", "greedy_accuracy"]],
                      y_label="Success fraction (0–1)")
    st.subheader("Invented communication mapping")
    mapping = data.get("mapping", [])
    if mapping:
        st.dataframe(pd.DataFrame(mapping).rename(columns={
            "target": "Target location", "symbol": "Agent A sends",
            "decoded": "Agent B guesses", "correct": "Success"
        }), use_container_width=True, hide_index=True)
    st.caption("Agent A learns a symbol for each hidden target. Agent B learns to decode it. "
               "100% on known targets is not evidence of language understanding or generalization.")

tab4, tab3, tab1, tab2 = st.tabs(["🧠 Agency", "💬 AARON-1", "📡 Signal Learning", "🧬 Evolution"])
with tab1:
    monitor()
with tab2:
    st.subheader("Genetic Evolution Experiment")
    st.caption("Independent population of 48 cooperating sender/receiver policy pairs. Selection, crossover, and mutation evolve discrete communication scores.")
    @st.fragment(run_every="2s")
    def evolution_monitor():
        evo = read(DATA / "evolution_status.json")
        ctl = read(DATA / "evolution_control.json")
        online = evo.get("running") and time.time() - evo.get("updated_at", 0) < 12
        st.write("🟢 Evolution trainer online" if online else "⚪ Evolution trainer offline")
        if not evo:
            st.info("Start the separate evolution engine in another Terminal: `python3 evolution.py`")
            return
        paused = st.toggle("Pause evolution", value=ctl.get("paused", False),
                           disabled=not online, key="evolution_paused")
        if online and paused != ctl.get("paused", False):
            (DATA / "evolution_control.json").write_text(
                json.dumps({"paused": paused}), encoding="utf-8")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Generation", evo.get("generation", 0))
        c2.metric("Population", evo.get("population_size", 0))
        c3.metric("Best cooperation", f"{100*evo.get('best_fitness', 0):.1f}%")
        c4.metric("Mean cooperation", f"{100*evo.get('mean_fitness', 0):.1f}%")
        hist = pd.DataFrame(evo.get("history", []))
        if not hist.empty:
            st.line_chart(hist.set_index("generation")[["best_fitness", "mean_fitness"]],
                          y_label="Fitness (0–1)")
        mapping = evo.get("mapping", [])
        if mapping:
            st.subheader("Top agent pair's code")
            st.dataframe(mapping, use_container_width=True, hide_index=True)
        st.caption("Fitness is success on the same eight target states used for selection. "
                   "This is genuine genetic search on fixed policies, not open-ended evolution "
                   "or evidence of general intelligence.")
    evolution_monitor()
with tab3:
    ensure_brainrot_training()
    st.subheader("Talk to AARON-1")
    st.caption("No pretrained models or language-model APIs. This is a tiny symbolic learner with durable local SQLite memory — not free-form language understanding.")
    st.info("Try: `am i cooked`, `what is rizz`, `valorant`, `67`, or `my favorite food is ramen`.")
    prior = history(1)
    render_face(prior[-1][1] if prior else "Hello! I am AARON-1. Teach me something!", key="individual")
    with st.expander("🎭 Teach AARON-1 your personality", expanded=True):
        st.caption("You're teaching it your conversational style, not turning it into you. All examples stay on this Mac in the local database.")
        stats = training_stats()
        st.write(f"🧠 **BRAINROT SCHOOL:** {stats['examples']} saved responses, "
                 f"{stats['bundled']} bundled lessons. Maximum slang is preloaded.")
        if st.button("💀 MAX BRAINROT — reapply training", key="max_brainrot"):
            added = ensure_brainrot_training(force=True)
            st.success(f"BRAINROT RESTORED 😭 {added} missing lessons added; your corrections are safe.")
            st.rerun()
        profile = get_profile()
        with st.form("personality_style"):
            c1, c2, c3 = st.columns(3)
            with c1:
                energy = st.slider("Energy", 0, 3, int(profile["energy"]), help="0 = chill, 3 = hyper")
            with c2:
                slang = st.slider("Slang", 0, 3, int(profile["slang"]), help="0 = plain English, 3 = casual")
            with c3:
                humor = st.slider("Humor", 0, 3, int(profile["humor"]), help="0 = straightforward, 3 = playful")
            phrases = st.text_input("Words you say (comma-separated)", value=profile["favorite_phrases"],
                                    max_chars=120, placeholder="bro, gang, lowk")
            if st.form_submit_button("Save my vibe"):
                save_profile(energy, slang, humor, phrases)
                st.success("Saved. Your next replies will use these preferences.")
                st.rerun()
        st.write("**Teach it how you'd reply**")
        st.caption("An example teaches a specific response to a phrase (or a very similar phrase). "
                   "It isn't general language training yet.")
        latest = history(1)
        with st.form("personality_correction", clear_on_submit=True):
            example_input = st.text_input("When someone says…",
                value=latest[-1][0] if latest else "",
                placeholder="what's good", max_chars=300)
            desired = st.text_area("AARON-1 should respond…",
                placeholder="yoooo what’s good gang 😭", max_chars=1000)
            if st.form_submit_button("Teach this reply"):
                if teach_reply(example_input, desired):
                    st.success("Saved! Try sending that phrase in chat.")
                    st.rerun()
                else:
                    st.warning("Add both an example message and your preferred reply.")
        examples = learned_examples()
        if examples:
            st.caption(f"{len(examples)} total response examples. Your new corrections take priority over bundled lessons.")
            if st.toggle("Browse and manage learned replies", value=False, key="show_training_replies"):
                st.dataframe(pd.DataFrame(examples, columns=["Message", "Learned response"]),
                             height=240, use_container_width=True, hide_index=True)
                selected = st.selectbox("Select one to forget", [p for p, _ in examples],
                                        key="forget_brainrot_reply")
                if st.button("Forget selected reply", key="forget_chosen_reply"):
                    forget_example(selected)
                    st.rerun()
    for utterance, reply in history(15):
        with st.chat_message("user"):
            st.write(utterance)
        with st.chat_message("assistant"):
            st.write(reply)
    msg = st.chat_input("Talk to your individual", key="aaron_chat")
    if msg:
        respond(msg)
        st.rerun()
    with st.expander("Vocabulary learned"):
        words = vocabulary()
        st.dataframe(pd.DataFrame(words, columns=["Expression", "Meaning"]),
                     use_container_width=True, hide_index=True)
    st.subheader("Communicate with another agent")
    state = read(DATA / "checkpoint.json").get("pair", {})
    n = int(state.get("n", 4))
    target = st.selectbox("Location known only to sender", list(range(n)))
    if st.button("Send learned symbol", key="peer_send"):
        outcome = symbolic_peer(target)
        if outcome is None:
            st.warning("Start the original trainer first to create a checkpoint.")
        else:
            st.write(f"Sender transmits symbol #{outcome['signal']}; receiver decodes location #{outcome['decoded']}.")
            st.success("Communication worked") if outcome["correct"] else st.error("They disagreed")
    st.caption("The English chat and learned symbol protocol are currently separate systems. Later we can connect them through explicit grounded teaching tasks.")

with tab4:
    st.subheader("AARON-1 · Agency Lab")
    st.caption("An actual trained Q-learning policy chooses tools, observes results, "
               "gets rewards, and keeps learning. The environments are safe simulations: "
               "no real folders, emails, apps, or accounts are touched.")
    agent = load_agent()
    metrics = agent.evaluate(trials_per_goal=100)
    m1, m2, m3 = st.columns(3)
    m1.metric("Lifetime training episodes", f"{agent.episodes:,}")
    m2.metric("Held-out practice accuracy", f"{metrics['accuracy']*100:.1f}%")
    m3.metric("Workflows completed", f"{metrics['complete_rate']*100:.1f}%")
    st.caption("Evaluation uses 200 new random practice workflows over the same two known "
               "task types. High scores here don't imply general computer control or "
               "natural-language understanding.")
    st.write("**Give AARON-1 a goal**")
    with st.form("agency_goal"):
        goal = st.selectbox("Goal", options=list(GOALS),
                            format_func=lambda g: GOALS[g]["label"])
        number_items = st.slider("Practice items", 3, 12, 6)
        submitted = st.form_submit_button("▶ Let AARON-1 execute")
    if submitted:
        outcome = agent.do_goal(goal, count=number_items)
        agent.save()
        st.session_state["last_agency_result"] = outcome
    outcome = st.session_state.get("last_agency_result")
    if outcome:
        summary = outcome["summary"]
        st.success(f"Agent executed {summary['steps']} tool calls and "
                   f"completed {summary['correct']}/{summary['items']} practice items correctly.")
        st.dataframe(pd.DataFrame(outcome["trace"]), hide_index=True,
                     use_container_width=True)
        st.caption("The trace shows each observation, chosen tool, and environment feedback. "
                   "The policy is updated from those rewards.")
    st.divider()
    st.write("**Continue training the SAME agent**")
    st.caption("Training updates its saved policy, not a population of replacement agents. "
               "This happens inside the current dashboard — no extra Terminal windows.")
    amount = st.select_slider("Additional practice episodes",
                              options=[100, 1000, 5000, 10000], value=5000)
    if st.button("🧠 Train AARON-1", key="agency_train"):
        with st.spinner("Running local reinforcement learning..."):
            before = agent.evaluate(trials_per_goal=100)
            info = agent.train(count=amount)
            after = agent.evaluate(trials_per_goal=100)
            agent.save()
        st.success(f"Trained {info['episodes_added']:,} more episodes. "
                   f"Accuracy {before['accuracy']:.1%} → {after['accuracy']:.1%}. "
                   f"Saved permanently to your local checkpoint.")
        st.rerun()
    if agent.history:
        chart_data = pd.DataFrame(agent.history).set_index("episode")
        st.line_chart(chart_data[["train_accuracy"]], y_label="Training success fraction")
    with st.expander("Read-only preview: organize files in a permitted folder"):
        st.caption("Optional file preview: AARON-1 reads filenames and extensions, "
                   "then proposes destinations. It NEVER moves or edits files.")
        preview_root = Path("data/agency_preview")
        preview_root.mkdir(parents=True, exist_ok=True)
        st.caption(f"Allowed preview root: {preview_root.resolve()}")
        st.caption("Put sample files there in Finder first. Access is restricted "
                   "to this directory unless the owner sets AARON_AGENCY_PREVIEW_ROOT.")
        folder = st.text_input("Folder to preview",
                               value=str(preview_root.resolve()),
                               key="agency_preview_folder")
        if st.button("Preview action plan (read-only)", key="agency_preview"):
            try:
                preview = preview_local_folder(folder, agent)
                if preview["items"]:
                    st.dataframe(pd.DataFrame(preview["items"]), hide_index=True,
                                 use_container_width=True)
                else:
                    st.info("No supported files found in the permitted folder.")
                if preview["truncated"]:
                    st.warning("Only the first 40 entries were inspected.")
                st.caption("Files changed: 0. Categories come from file extensions "
                           "supplied by a deterministic inspection tool.")
            except (OSError, ValueError) as exc:
                st.error(str(exc))
    with st.expander("Inspect AARON-1's learned tool choices"):
        rows = []
        for state, scores in sorted(agent.q.items()):
            if state.endswith("|done"):
                continue
            action = max(range(len(scores)), key=lambda idx: scores[idx])
            rows.append({"Observed state": state, "Chosen tool": ACTION_LABELS[ACTIONS[action]],
                         "Estimated action value": round(scores[action], 3)})
        if rows:
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        st.caption("The values are learned Q-estimates for these states, not "
                   "an explanation of unrestricted reasoning.")

with st.expander("How the experiment works"):
    st.write("Two tabular reinforcement-learning policies share only a discrete signal. "
             "A receives the hidden target and chooses a signal. B sees the signal and "
             "chooses a target. Both receive the same reward. The task gradually grows "
             "from four to eight targets after consecutive perfect evaluations.")
    st.write("There are no language models, no API fees, and no automatic modification of your code.")
