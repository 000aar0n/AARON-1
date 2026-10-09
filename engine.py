"""Small cooperating tabular agents. No LLMs or external APIs."""
import random

SYMBOLS = ["◆", "●", "▲", "■", "★", "☀", "☂", "♣", "♥", "☯", "♫", "☕"]

class Pair:
    def __init__(self, n=4, epsilon=0.22, alpha=0.18, seed=None):
        self.n = n
        self.epsilon = epsilon
        self.alpha = alpha
        self.rng = random.Random(seed)
        self.sender = [[0.0] * n for _ in range(n)]
        self.receiver = [[0.0] * n for _ in range(n)]
        self.steps = 0

    def pick(self, values, explore=True):
        if explore and self.rng.random() < self.epsilon:
            return self.rng.randrange(self.n)
        best = max(values)
        winners = [i for i, v in enumerate(values) if v == best]
        return self.rng.choice(winners) if explore else winners[0]

    def episode(self):
        target = self.rng.randrange(self.n)
        signal = self.pick(self.sender[target])
        guess = self.pick(self.receiver[signal])
        success = int(guess == target)
        reward = 1.0 if success else -0.3
        for table, row, action in ((self.sender, target, signal),
                                   (self.receiver, signal, guess)):
            table[row][action] += self.alpha * (reward - table[row][action])
        self.steps += 1
        return {"target": target, "signal": signal, "guess": guess,
                "success": success}

    def accuracy(self):
        # Exact, exploration-free assessment over all possible targets.
        hits = 0
        mapping = []
        for target in range(self.n):
            signal = self.pick(self.sender[target], explore=False)
            guess = self.pick(self.receiver[signal], explore=False)
            mapping.append({"target": target, "symbol": SYMBOLS[signal],
                            "decoded": guess, "correct": target == guess})
            hits += int(target == guess)
        return hits / self.n, mapping

    def state(self):
        return {"n": self.n, "epsilon": self.epsilon, "alpha": self.alpha,
                "sender": self.sender, "receiver": self.receiver,
                "steps": self.steps}

    @classmethod
    def from_state(cls, obj):
        pair = cls(obj["n"], obj["epsilon"], obj["alpha"])
        pair.sender = obj["sender"]
        pair.receiver = obj["receiver"]
        pair.steps = obj["steps"]
        return pair
