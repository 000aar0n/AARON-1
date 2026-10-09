"""Streamlit monitoring UI; trainer runs independently of this process."""
import json
import time
from pathlib import Path
import pandas as pd
import streamlit as st

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

monitor()
with st.expander("How the experiment works"):
    st.write("Two tabular reinforcement-learning policies share only a discrete signal. "
             "A receives the hidden target and chooses a signal. B sees the signal and "
             "chooses a target. Both receive the same reward. The task gradually grows "
             "from four to eight targets after consecutive perfect evaluations.")
    st.write("There are no language models, no API fees, and no automatic modification of your code.")
