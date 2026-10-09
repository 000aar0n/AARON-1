"""Evolutionary search for cooperating sender/receiver policies.

Each genome encodes two score matrices, rather than neural-network weights.
Fitness measures exact cooperation over every possible hidden target.
This is a toy genetic algorithm, not open-ended intelligence.
"""
import json
import os
import random
import signal
import time
from pathlib import Path

DATA = Path("data")
DATA.mkdir(exist_ok=True)
CHECKPOINT = DATA / "evolution_checkpoint.json"
STATUS = DATA / "evolution_status.json"
CONTROL = DATA / "evolution_control.json"
N = 8
POPULATION = 48
ELITES = 6
MUTATION_RATE = 0.12
running = True

def stop(*_):
    global running
    running = False

signal.signal(signal.SIGINT, stop)
signal.signal(signal.SIGTERM, stop)

def save(path, data):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    os.replace(tmp, path)

def load(path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default

def new_genome(rng):
    return [rng.uniform(-1, 1) for _ in range(2 * N * N)]

def decode(genome, state):
    start = state * N
    return max(range(N), key=lambda x: genome[start + x])

def receive(genome, symbol):
    start = N * N + symbol * N
    return max(range(N), key=lambda x: genome[start + x])

def fitness(genome):
    return sum(receive(genome, decode(genome, target)) == target
               for target in range(N)) / N

def mutate(parent, rng):
    child = parent[:]
    for i in range(len(child)):
        if rng.random() < MUTATION_RATE:
            child[i] += rng.gauss(0, 0.6)
    return child

def cross(a, b, rng):
    return [x if rng.random() < 0.5 else y for x, y in zip(a, b)]

def generation(population, rng):
    ranked = sorted(population, key=fitness, reverse=True)
    best = fitness(ranked[0])
    mean = sum(fitness(g) for g in population) / len(population)
    children = [g[:] for g in ranked[:ELITES]]
    while len(children) < POPULATION:
        # Tournament selection gives stronger genomes a better chance to reproduce.
        a = max(rng.sample(population, 3), key=fitness)
        b = max(rng.sample(population, 3), key=fitness)
        children.append(mutate(cross(a, b, rng), rng))
    return children, best, mean, ranked[0]

def mapping(genome):
    return [{"target": i, "signal": decode(genome, i),
             "receiver_guess": receive(genome, decode(genome, i))}
            for i in range(N)]

def main():
    rng = random.Random()
    saved = load(CHECKPOINT, {})
    population = saved.get("population")
    if not population or len(population) != POPULATION:
        population = [new_genome(rng) for _ in range(POPULATION)]
    count = saved.get("generation", 0)
    history = saved.get("history", [])
    print("Evolution trainer started. Ctrl+C to save and stop.", flush=True)
    try:
        while running:
            paused = bool(load(CONTROL, {}).get("paused", False))
            if not paused:
                population, best, mean, champion = generation(population, rng)
                count += 1
                history.append({"generation": count, "best_fitness": best,
                                "mean_fitness": mean})
                history = history[-500:]
                if count % 10 == 0:
                    print(f"Generation {count}: best={best:.0%} avg={mean:.0%}", flush=True)
            else:
                champion = max(population, key=fitness)
                best = fitness(champion)
                mean = sum(map(fitness, population)) / len(population)
            state = {"generation": count, "population": population,
                     "history": history}
            save(CHECKPOINT, state)
            save(STATUS, {"running": True, "paused": paused,
                          "updated_at": time.time(), "generation": count,
                          "population_size": POPULATION, "targets": N,
                          "best_fitness": best, "mean_fitness": mean,
                          "mapping": mapping(champion), "history": history})
            time.sleep(0.3)
    finally:
        save(CHECKPOINT, {"generation": count, "population": population,
                          "history": history})
        status = load(STATUS, {})
        status.update({"running": False, "updated_at": time.time()})
        save(STATUS, status)
        print("Evolution checkpoint saved.", flush=True)

if __name__ == "__main__":
    main()
