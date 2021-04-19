"""Module for running many Koehandel simulations."""

import math
import random
from collections import deque

from joblib import Parallel, delayed

from config import Config
from strategy import Strategy
from player import Player
from game import Game
from deck import Deck


class Simulator:
    """Class to run many Koehandel games with different strategies."""

    def __init__(self, config_file, njobs=-1):

        self._njobs = njobs
        self._config = Config(config_file)

        self._play_each = self._config.get("play_each_strategy")
        self._nplayers = self._config.get("players_per_game")

        self._pool = self._generate_strategies()

    def _generate_strategies(self):
        """Generates a pool of strategies to play."""

        size = self._config.get("number_strategies")
        return [Strategy(self._config) for _ in range(size)]

    def _generate_names(self):
        """Generates (uninspired) player names if none were provided."""

        return [f"Player {n + 1}" for n in range(self._nplayers)]

    def play_game(self, strategies):
        """Runs a single game."""

        deck = Deck(self._config)
        game = Game(self._config, deck)

        names = self._generate_names()
        for name, strategy in zip(names, strategies):
            player = Player(self._config, name, strategy)
            game.add_player(player)

        return game.run()

    def run(self):
        """Runs the entire simulation."""

        strategy_cycle = StrategyCycle(self._pool, self._play_each, self._nplayers)

        results = Parallel(n_jobs=self._njobs)(
            delayed(self.play_game)(strategies)
            for strategies in strategy_cycle
        )

        return results


class StrategyCycle:
    """Class to cycle through a pool of strategies.

    Parameters
    ----------
    pool : List[strategy.Strategy]
        List of player strategies to cycle through.
    play_each : int
        Number of times to play each strategy.
    nplayers : int
        Number of players in each game.
    """

    def __init__(self, pool, play_each, nplayers):

        self._pool = pool

        if nplayers > len(pool):
            raise ValueError("Pool must be larger than number of players per game.")

        self._nplayers = nplayers
        self._ngames = math.ceil(len(pool) / nplayers * play_each)


    def __iter__(self):

        self._games = 0
        self._stack = deque(random.sample(self._pool, len(self._pool)))

        return self

    def __next__(self):
        """Returns a set of strategies equal to the number of players per game."""

        if self._games < self._ngames:

            selected = []

            while len(selected) < self._nplayers:

                # Replenish stack if needed
                if len(self._stack) < self._nplayers:
                    self._stack.extend(random.sample(self._pool, len(self._pool)))

                if self._stack[0] not in selected:
                    selected.append(self._stack.popleft())
                else:
                    self._stack.rotate()


            self._games += 1
            return selected

        else:
            raise StopIteration