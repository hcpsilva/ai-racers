import numpy as np
import multiprocessing as mp
import pickle
import os.path
from datetime import datetime
from controller import controller

def cross_individual(population, mask):
    dad1_idx = np.random.randint(0, len(population))
    dad2_idx = np.random.randint(0, len(population))
    dad1 = population[dad1_idx]
    dad2 = population[dad2_idx]
    son = []

    for i, gene in enumerate(mask):
        if gene == 0:
            son.append(dad1[i])
        else:
            son.append(dad2[i])

    return np.array(son)

class Controller(controller.Controller):
    def __init__(self, track, evaluate=True, bot_type=None):
        super().__init__(track, evaluate=evaluate, bot_type=bot_type)
        self.algorithm = "Genetic Algorithm"
        self.alias = "ga"

    def local_search(self, initial_weights, *argv):

        return self.genetic_algorithm(initial_weights, *argv)

    def save_result(self, weights, score):
        f = open(self.alias + "-" + "best_w", "w+")
        f.write(datetime.now().strftime("%d/%m/%Y %H:%M:%S") + "\r\n")
        f.write(super().featureNames)
        f.write("Score: ", score)
        f.write(weights)
        f.close()

    def genetic_algorithm(self,
                          weights,
                          population_size=100,
                          mutation_rate=0.2,
                          elitism=0.15,
                          roulette=0.1):  # sori the line was huge

        population_size = int(population_size)
        elitism = float(elitism)
        mutation_rate = float(mutation_rate)
        roulette = float(roulette)

        max_same_best = 10
        perturbation_range = 0.5  # [-0.5,0.5]

        if (os.path.exists('ga_previous_pop.pkl')):
            with open('ga_previous_pop.pkl', 'rb') as pop_file:
                population = pickle.load(pop_file)
            with open('ga_previous_info.pkl', 'rb') as info_file:
                generation, same_best, greater_score_found = pickle.load(info_file)

            fitness = self.compute_fitness(population)
            best_idx = np.argmax(fitness)
            best_individual_prev = population[best_idx]
        else:
            population = self.generate_population_par(weights, population_size)
            generation = 1
            same_best = 0

            fitness = self.compute_fitness(population)
            best_idx = np.argmax(fitness)
            best_individual_prev = population[best_idx]
            greater_score_found = np.amax(fitness)

        if (fitness[best_idx] > greater_score_found):
            greater_score_found = fitness[np.argmax(fitness)]
            np.savetxt("best_genetic.txt", best_individual_prev)

        print("\n\nGeneration:", generation)
        print("Best population score:", fitness[best_idx])
        print("Greater score found among generations:", greater_score_found)
        print("\n\n")

        population = self.select_population(population, fitness, elitism, roulette)
        population = self.cross_population(population, population_size, mutation_rate, perturbation_range)
        fitness = self.compute_fitness(population)

        generation += 1

        best_idx = np.argmax(fitness)
        best_individual = population[best_idx]

        if np.array_equal(best_individual, best_individual_prev):
            same_best += 1
            if same_best >= max_same_best:
                print("Same individual found", same_best,
                      "times. Learning algorithm stopped.")
                return population[np.argmax(fitness)]

        else:
            same_best = 0

        with open('ga_previous_pop.pkl', 'wb') as pop_file:
            pickle.dump(population, pop_file)
        with open('ga_previous_info.pkl', 'wb') as info_file:
            pickle.dump([generation, same_best, greater_score_found], info_file)

        print("Max generations reached. Learning algorithm stopped.")
        return population[np.argmax(fitness)], max(fitness)

    # Input parameters: list size of the current weights; number of individuals to be generated
    # Output returned: new set of weights, int score
    def generate_population(self, weights, population_size):

        population = [weights]

        for i in range(population_size-1):
            population.append(
                np.random.uniform(low=-1.0, high=1.0, size=len(weights))
            )

        return population

    def generate_population_par(self, weights, population_size):

        population = [None] * population_size

        pool = mp.Pool(mp.cpu_count())

        population = [pool.apply(
            np.random.uniform, kwds={'low': -1.0, 'high': 1.0, 'size': len(weights)})
                      for _ in range(population_size)]

        population[0] = weights

        return population

    # Input parameters: list of individual solutions
    # Output returned: list of fitness score for each individual
    def compute_fitness(self, population):
        fitness = []

        for individual in population:
            fitness.append(self.run_episode(individual))

        return fitness


    # Input parameters: list of individual solutions; fitness; fraction to keep by elitism; fraction to keep by roulette
    # Output returned: selected individuals
    def select_population(self, population, fitness, elitism, roulette):

        fitness = np.array(fitness)
        population = np.array(population)

        elite = []
        if (elitism != 0):

            num_from_elite = round(elitism * len(population))
            elite_idx = np.argpartition(fitness, -num_from_elite)[-num_from_elite:] # Get the index of the N greatest scores
            elite = population[elite_idx]

            # Delete the already selected individuals by the elitism method
            population = np.delete(population, elite_idx, axis=0)
            fitness = np.delete(fitness, elite_idx, axis=0)

        drawn_from_roulette = []
        if (roulette != 0):
            # Select the next fraction by the roulette method
            num_from_roulette = round(roulette * len(population))

            # avoiding too negative sum result
            fitness_zero_shifted = fitness + abs(np.amin(fitness))
            s = np.sum(fitness_zero_shifted) + 1

            for _ in range(num_from_roulette):
                r = np.random.randint(0, s)
                t = 0
                for i, score in enumerate(fitness_zero_shifted):
                    t = t + score
                    if (t >= r):
                        drawn_from_roulette.append(population[i])   # get rouletted individual
                        population = np.delete(population, i, axis=0)   # can't be chosen more than once
                        fitness = np.delete(fitness, i, axis=0)   # can't be chosen more than once
                        fitness_zero_shifted = np.delete(fitness_zero_shifted, i, axis=0)
                        break

            drawn_from_roulette = np.array(drawn_from_roulette)

        selected_population = np.append(elite, drawn_from_roulette, axis=0)
        return selected_population

    # Crossover method used: uniform crossover with random crossover mask
    # Input parameters: list of individual solutions; list of maximum individuals
    # Output returned: new population
    def cross_population(self, population, population_size, mutation_rate, perturbation_range):
        num_missing_individuals = population_size - len(population)
        missing_population = [None] * num_missing_individuals

        mask = np.random.randint(0, 2, size=population.shape[1])
        # mask example for a problem with 5 weights [0,1,1,0,1]
        # Note that, here, each weight is the gene of the chromossome (instead of bits)

        pool = mp.Pool(mp.cpu_count())

        missing_population = [
            pool.apply(cross_individual, (np.array(population), mask,))
            for _ in range(num_missing_individuals)]


        missing_population = np.array(missing_population)
        missing_population = self.mutate_population(missing_population, mutation_rate, perturbation_range)
        new_population = np.append(population, missing_population, axis=0)
        return new_population

    # Input parameters: list of individual solutions;
    # Output returned: new population
    def mutate_population(self, population, mutation_rate, perturbation_range=0.1):

        mutation_percentage = mutation_rate*100
        # population = self.mutate_per_individual(population, mutation_percentage, perturbation_range)
        population = self.mutate_per_gene(population, mutation_percentage, perturbation_range)

        return population

    def mutate_per_individual(self, population, mutation_percentage, perturbation_range=0.1):
        for individual in population:
            rand = np.random.randint(0, 101)

            if self.must_mutate(rand, mutation_percentage):
                # Mutate a random number of times, a random number of genes
                for _ in range(np.random.randint(0, len(individual))):
                    mutation_gene = np.random.randint(0, len(individual))
                    perturbation = np.random.uniform(low=-perturbation_range, high=perturbation_range)
                    individual[mutation_gene] += perturbation

        return population

    def mutate_per_gene(self, population, mutation_percentage, perturbation_range=0.1):

        for individual in population:
            for gene in range(len(individual)):
                rand = np.random.randint(0, 101)

                if self.must_mutate(rand, mutation_percentage):
                    perturbation = np.random.uniform(low=-perturbation_range, high=perturbation_range)
                    individual[gene] += perturbation

        return population

    def must_mutate(self, rand, mutation):
        return rand <= mutation
