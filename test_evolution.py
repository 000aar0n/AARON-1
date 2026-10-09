import random
import unittest
from evolution import N, POPULATION, new_genome, fitness, generation, mapping

class EvolutionTests(unittest.TestCase):
    def test_fitness_bounds(self):
        g = new_genome(random.Random(1))
        self.assertGreaterEqual(fitness(g), 0)
        self.assertLessEqual(fitness(g), 1)

    def test_elitism_never_loses_best(self):
        rng = random.Random(7)
        pop = [new_genome(rng) for _ in range(POPULATION)]
        best = max(map(fitness, pop))
        for _ in range(20):
            pop, _, _, _ = generation(pop, rng)
            self.assertGreaterEqual(max(map(fitness, pop)), best)
            best = max(map(fitness, pop))

    def test_mapping_size(self):
        self.assertEqual(len(mapping(new_genome(random.Random(2)))), N)

if __name__ == "__main__":
    unittest.main()
