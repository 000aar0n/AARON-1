"""AARON-1: persistent, goal-conditioned reinforcement-learning agency.

No LLMs, pretrained networks, APIs, or external automation. A *single* Q-learning
policy learns which tool to call in two safe, simulated task environments. It
observes -> acts -> receives reward -> updates -> saves, across many episodes.

Honesty: categories are revealed by a simulated inspect tool. This does NOT
classify arbitrary real files or understand natural language.
"""
from __future__ import annotations

import argparse
import json
import os
import random
from pathlib import Path

IDENTITY = "AARON-1"
HERE = Path(__file__).resolve().parent
LOCAL_POLICY = HERE / "data" / "agency_policy.json"
PRETRAINED_POLICY = HERE / "models" / "agency_seed.json"

ACTIONS = ("inspect", "file_docs", "file_images", "file_code",
           "do_now", "schedule", "backlog")
GOALS = {
    "sort_inbox": {
        "label": "Organize a practice inbox",
        "categories": ("document", "image", "code"),
        "correct_actions": {
            "document": "file_docs",
            "image": "file_images",
            "code": "file_code",
        },
        "names": {
            "document": ("notes.txt", "essay.pdf", "report.docx", "draft.md"),
            "image": ("photo.png", "poster.jpg", "art.webp", "diagram.jpeg"),
            "code": ("app.py", "site.js", "script.sh", "main.cpp"),
        },
    },
    "triage_tasks": {
        "label": "Prioritize a practice to-do list",
        "categories": ("urgent", "soon", "later"),
        "correct_actions": {
            "urgent": "do_now",
            "soon": "schedule",
            "later": "backlog",
        },
        "names": {
            "urgent": ("deadline today", "meeting in one hour", "urgent assignment"),
            "soon": ("quiz next week", "write project outline", "review notes"),
            "later": ("reorganize bookmarks", "try new wallpaper", "optional tutorial"),
        },
    },
}
ACTION_LABELS = {
    "inspect": "Inspect item",
    "file_docs": "File under Documents",
    "file_images": "File under Images",
    "file_code": "File under Code",
    "do_now": "Put into Do Now",
    "schedule": "Schedule task",
    "backlog": "Move into Backlog",
}

def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None

def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)

class PracticeWorkspace:
    """Tiny sandbox; never touches the real filesystem."""
    def __init__(self, goal, rng, count=6):
        if goal not in GOALS:
            raise ValueError("Unknown sandbox goal")
        if not 1 <= count <= 20:
            raise ValueError("Practice task count must be 1..20")
        self.goal, self.rng = goal, rng
        self.spec = GOALS[goal]
        self.items = []
        for i in range(count):
            category = rng.choice(self.spec["categories"])
            name = rng.choice(self.spec["names"][category])
            self.items.append({"name": f"{i+1}: {name}", "category": category})
        self.index = 0
        self.inspected = False
        self.correct = 0
        self.incorrect = 0
        self.inspections = 0
        self.steps = 0
        self.max_steps = count * 6
        self.trace = []

    @property
    def done(self):
        return self.index >= len(self.items) or self.steps >= self.max_steps

    @property
    def state(self):
        if self.done:
            return f"{self.goal}|done"
        return f"{self.goal}|{self.items[self.index]['category'] if self.inspected else 'hidden'}"

    def observe(self):
        if self.done:
            return {"goal": self.goal, "complete": True}
        item = self.items[self.index]
        return {"goal": self.goal, "current_item": item["name"],
                "tag": item["category"] if self.inspected else "not inspected",
                "items_remaining": len(self.items) - self.index}

    def step(self, action):
        if self.done:
            raise RuntimeError("Goal already completed")
        if action not in ACTIONS:
            raise ValueError("Unknown action")
        before = self.observe()
        self.steps += 1
        current = self.items[self.index]
        if action == "inspect":
            if self.inspected:
                reward, event = -0.35, "Repeated inspection did not reveal anything new"
            else:
                self.inspected = True
                self.inspections += 1
                reward = -0.04
                event = f"Inspect revealed tag: {current['category']}"
        else:
            wanted = self.spec["correct_actions"][current["category"]]
            correct = action == wanted
            self.correct += int(correct)
            self.incorrect += int(not correct)
            reward = 2.0 if correct else -2.0
            event = ("Correct destination" if correct else
                     f"Incorrect: should have used {ACTION_LABELS[wanted]}")
            self.index += 1
            self.inspected = False
        after = self.observe()
        self.trace.append({"step": self.steps, "item": before["current_item"],
                           "observed_tag": before["tag"], "tool": ACTION_LABELS[action],
                           "feedback": event, "reward": reward})
        return reward, self.done, after

    def summary(self):
        return {"goal": self.goal, "items": len(self.items),
                "correct": self.correct, "incorrect": self.incorrect,
                "inspections": self.inspections, "steps": self.steps,
                "completed": self.index == len(self.items)}

class AARONAgent:
    """One persistent Q-table, shared across goal-conditioned tasks."""
    def __init__(self, state=None):
        state = state or {}
        if state.get("identity", IDENTITY) != IDENTITY:
            raise ValueError("Checkpoint belongs to a different agent")
        self.identity = IDENTITY
        self.q = {key: [float(v) for v in values]
                  for key, values in state.get("q", {}).items()
                  if isinstance(values, list) and len(values) == len(ACTIONS)}
        self.episodes = int(state.get("episodes", 0))
        self.steps = int(state.get("steps", 0))
        self.history = list(state.get("history", []))[-100:]
        self.alpha = 0.18
        self.gamma = 0.88

    def scores(self, state):
        if state not in self.q:
            self.q[state] = [0.0] * len(ACTIONS)
        return self.q[state]

    def choose(self, state, rng, epsilon=0.0):
        if rng.random() < epsilon:
            return rng.randrange(len(ACTIONS))
        row = self.scores(state)
        return max(range(len(ACTIONS)), key=lambda i: row[i])

    def update(self, prior, action, reward, nxt, terminal):
        row = self.scores(prior)
        future = 0 if terminal else max(self.scores(nxt))
        target = reward + self.gamma * future
        row[action] += self.alpha * (target - row[action])
        self.steps += 1

    def episode(self, goal, rng, *, epsilon=0.0, learn=False, count=6):
        env = PracticeWorkspace(goal, rng, count)
        while not env.done:
            state = env.state
            action_i = self.choose(state, rng, epsilon=epsilon)
            reward, finished, _ = env.step(ACTIONS[action_i])
            if learn:
                self.update(state, action_i, reward, env.state, finished)
        if learn:
            self.episodes += 1
        return env

    def train(self, count=5000, seed=621, sample_every=500):
        if not 1 <= count <= 200000:
            raise ValueError("Train between 1 and 200,000 episodes per call")
        rng = random.Random(seed + self.episodes)
        wins = 0
        total = 0
        for idx in range(count):
            goal = rng.choice(tuple(GOALS))
            # More exploration early; retain slight exploration over lifetime.
            epsilon = max(0.045, 0.40 * (1.0 - idx / max(1000, count)))
            env = self.episode(goal, rng, epsilon=epsilon,
                               learn=True, count=rng.randint(3, 8))
            wins += env.correct
            total += len(env.items)
            if (idx + 1) % sample_every == 0 or idx + 1 == count:
                self.history.append({"episode": self.episodes,
                                     "train_accuracy": round(wins / total, 4)})
                self.history = self.history[-100:]
        return {"episodes_added": count, "training_accuracy": round(wins / total, 4),
                "total_episodes": self.episodes}

    def evaluate(self, trials_per_goal=100, seed=7001):
        rng = random.Random(seed)
        details = {}
        total_correct = total_items = completed = 0
        for goal in GOALS:
            right = tasks = complete = inspected = 0
            for _ in range(trials_per_goal):
                env = self.episode(goal, rng, count=rng.randint(3, 8))
                result = env.summary()
                right += result["correct"]
                tasks += result["items"]
                complete += int(result["completed"])
                inspected += result["inspections"]
            details[goal] = {"accuracy": round(right / tasks, 4),
                             "completion_rate": round(complete / trials_per_goal, 4),
                             "inspections": inspected}
            total_correct += right
            total_items += tasks
            completed += complete
        return {"accuracy": round(total_correct / total_items, 4),
                "complete_rate": round(completed / (len(GOALS) * trials_per_goal), 4),
                "by_goal": details}

    def do_goal(self, goal, count=6, seed=None):
        rng = random.Random(seed)
        env = self.episode(goal, rng, epsilon=0.0, learn=True, count=count)
        return {"summary": env.summary(), "trace": env.trace}

    def state_dict(self):
        return {"version": 1, "identity": self.identity, "episodes": self.episodes,
                "steps": self.steps, "q": self.q, "history": self.history}

    def save(self, path=LOCAL_POLICY):
        atomic_json(path, self.state_dict())


def load_agent():
    """Local trained identity takes priority; pretraining is copied only once."""
    saved = read_json(LOCAL_POLICY)
    if saved is None:
        saved = read_json(PRETRAINED_POLICY)
    return AARONAgent(saved)



READONLY_SUFFIXES = {
    "document": {".pdf", ".txt", ".md", ".docx", ".doc", ".rtf", ".pptx", ".xlsx"},
    "image": {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"},
    "code": {".py", ".js", ".ts", ".sh", ".cpp", ".c", ".java", ".css", ".html", ".json", ".yaml"},
}
FOLDERS = {"file_docs": "Documents", "file_images": "Images", "file_code": "Code"}


def preview_local_folder(folder, agent, limit=40):
    """Read filenames/extensions only and use the learned policy for a proposed plan.

    Never reads file contents; never creates, moves or deletes files. The user
    explicitly supplies the local folder path. No recursive traversal/symlinks.
    """
    if not isinstance(agent, AARONAgent):
        raise TypeError("Expected AARON-1 agent")
    path = Path(folder).expanduser()
    if not path.is_dir():
        raise ValueError("Choose an existing folder on the machine running Streamlit")
    if not 1 <= limit <= 100:
        raise ValueError("Limit must be between 1 and 100")
    results = []
    files = sorted(path.iterdir(), key=lambda item: item.name.lower())
    truncated = len(files) > limit
    for item in files[:limit]:
        if item.is_symlink() or not item.is_file():
            continue
        category = next((tag for tag, suffixes in READONLY_SUFFIXES.items()
                         if item.suffix.lower() in suffixes), None)
        if not category:
            results.append({"name": item.name, "inspect": "extension not supported",
                            "decision": "Leave untouched", "confidence": "n/a"})
            continue
        # Learned tool selection (not a hardcoded move): inspect first, then decide.
        inspect_action = ACTIONS[agent.choose("sort_inbox|hidden", random.Random(17))]
        if inspect_action != "inspect":
            results.append({"name": item.name, "inspect": "not inspected",
                            "decision": "No proposal: policy needs training",
                            "confidence": "low"})
            continue
        action = ACTIONS[agent.choose("sort_inbox|" + category, random.Random(17))]
        destination = FOLDERS.get(action)
        results.append({"name": item.name,
                        "inspect": f"extension suggests {category}",
                        "decision": f"Would organize into {destination}" if destination else
                                    "No supported destination",
                        "confidence": "known category" if destination else "low"})
    return {"folder": str(path), "items": results,
            "truncated": truncated, "files_changed": 0}


def main():
    parser = argparse.ArgumentParser(description="Train one AARON-1 agent on safe sandbox goals.")
    parser.add_argument("--episodes", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=621)
    parser.add_argument("--output", type=Path, default=LOCAL_POLICY)
    parser.add_argument("--fresh", action="store_true", help="New policy (only for seed creation)")
    args = parser.parse_args()
    agent = AARONAgent() if args.fresh else load_agent()
    before = agent.evaluate()
    print(f"Training {IDENTITY}: before accuracy={before['accuracy']:.1%} "
          f"completed={before['complete_rate']:.1%}", flush=True)
    result = agent.train(args.episodes, seed=args.seed)
    after = agent.evaluate()
    agent.save(args.output)
    print(f"After {result['total_episodes']} episodes: "
          f"accuracy={after['accuracy']:.1%}, complete={after['complete_rate']:.1%}. "
          f"Policy written to {args.output}", flush=True)

if __name__ == "__main__":
    main()
