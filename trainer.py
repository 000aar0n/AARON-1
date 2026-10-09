"""Independent background trainer. Run: python3 trainer.py"""
import json
import os
import signal
import time
from pathlib import Path
from engine import Pair

DATA = Path("data")
DATA.mkdir(exist_ok=True)
CHECKPOINT = DATA / "checkpoint.json"
STATUS = DATA / "status.json"
CONTROL = DATA / "control.json"
RUN = True

def stop(*_):
    global RUN
    RUN = False

signal.signal(signal.SIGINT, stop)
signal.signal(signal.SIGTERM, stop)

def atomic_json(path, obj):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    os.replace(temp, path)

def read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default

def main():
    saved = read_json(CHECKPOINT, {})
    pair = Pair.from_state(saved["pair"]) if "pair" in saved else Pair()
    history = saved.get("history", [])
    generations = saved.get("generations", 0)
    streak = saved.get("streak", 0)
    last_event = "Training initialized"
    print("AARON-1 running. Ctrl+C stops safely.", flush=True)
    try:
        while RUN:
            control = read_json(CONTROL, {})
            if control.get("paused", False):
                status = read_json(STATUS, {})
                status["running"] = True
                status["paused"] = True
                status["updated_at"] = time.time()
                atomic_json(STATUS, status)
                time.sleep(0.5)
                continue
            wins = 0
            for _ in range(1000):
                wins += pair.episode()["success"]
            generations += 1
            accuracy, mapping = pair.accuracy()
            recent = wins / 1000
            pair.epsilon = max(0.04, pair.epsilon * 0.995)
            streak = streak + 1 if accuracy == 1.0 else 0
            if streak >= 12 and pair.n < 8:
                n = pair.n + 1
                pair = Pair(n=n)
                streak = 0
                last_event = f"Curriculum advanced to {n} symbols"
            else:
                last_event = f"Generation {generations} completed"
            history.append({"generation": generations, "n": pair.n,
                            "train_accuracy": round(recent, 4),
                            "greedy_accuracy": round(accuracy, 4)})
            history = history[-500:]
            checkpoint = {"pair": pair.state(), "history": history,
                          "generations": generations, "streak": streak}
            atomic_json(CHECKPOINT, checkpoint)
            current_accuracy, current_mapping = pair.accuracy()
            atomic_json(STATUS, {"running": True, "updated_at": time.time(),
                        "generation": generations, "paused": False, "total_episodes": generations * 1000,
                        "symbols": pair.n, "train_accuracy": recent,
                        "greedy_accuracy": current_accuracy, "mapping": current_mapping,
                        "history": history, "event": last_event})
            if generations % 10 == 0:
                print(last_event, "accuracy", round(current_accuracy, 2), flush=True)
            time.sleep(0.15)
    finally:
        atomic_json(CHECKPOINT, {"pair": pair.state(), "history": history,
                                "generations": generations, "streak": streak})
        status = read_json(STATUS, {})
        status["running"] = False
        status["updated_at"] = time.time()
        atomic_json(STATUS, status)
        print("Checkpoint saved. Trainer stopped.", flush=True)

if __name__ == "__main__":
    main()
