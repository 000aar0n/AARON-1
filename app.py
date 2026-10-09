"""Streamlit monitoring UI; trainer runs independently of this process."""
import json
import time
from pathlib import Path
import pandas as pd
import streamlit as st
from individual import respond, history, vocabulary, symbolic_peer
from avatar import render_face

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
st.caption("Cooperative agent evolution laboratory · Local-first")
st.info("The trainer is separate from Streamlit. Start it in Terminal with `python3 trainer.py`. This dashboard can also run on Streamlit Cloud in read-only demo mode, but cloud training is not continuous or synced to your Mac.")

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

tab1, tab2, tab3 = st.tabs(["📡 Signal Learning", "🧬 Evolution", "💬 AARON-1"])
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
    st.subheader("Talk to AARON-1")
    st.caption("No pretrained models or language-model APIs. This is a tiny symbolic learner with durable local SQLite memory — not free-form language understanding.")
    st.info("Try: `my favorite food is ramen`, `what is my favorite food`, or `teach: sup = greeting`.")
    prior = history(1)
    render_face(prior[-1][1] if prior else "Hello! I am AARON-1. Teach me something!", key="individual")
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

with st.expander("How the experiment works"):
    st.write("Two tabular reinforcement-learning policies share only a discrete signal. "
             "A receives the hidden target and chooses a signal. B sees the signal and "
             "chooses a target. Both receive the same reward. The task gradually grows "
             "from four to eight targets after consecutive perfect evaluations.")
    st.write("There are no language models, no API fees, and no automatic modification of your code.")
