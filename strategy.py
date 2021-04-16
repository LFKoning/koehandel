"""Module implementing strategy related classes."""

import json
import random
import numpy as np


class Strategy:
    """Class for Koehandel strategy.

    Parameters
    ----------
    animals : dict
        Dict mapping animals and score points.
    modifiers : Optional[dict]
        Dict with modifier settings, used by deserialize method.
    """

    def __init__(self, config, seed=None):

        self.seed = seed or random.randint(1, 1e7)
        self._random = random.Random(self.seed)

        self._animals = config.get("animals")
        self._modifiers = {
            "animals": self._animal_modifiers(),
            "collected": self._collected_slope(),
            "opponent_collected": self._opponent_slope(),
            "completed_sets": self._completed_slope(),
            "trade_propensity": self._propensities(minimum=50),
            "counter_propensity": self._propensities(minimum=25),
        }

    def _animal_modifiers(self):
        """Generates dict of bidding propensities for all animals."""

        return {
            animal: self._random.lognormvariate(mu=0, sigma=0.5)
            for animal in self._animals
        }

    def _collected_slope(self):
        """Generates modifier for the number of animals collected by the player."""

        # Positive slope; more animals collected leads to higher bids.
        return self._random.expovariate(10)

    def _opponent_slope(self):
        """Generates modifier for number of animals collected by opponents."""

        # Negative slope; lower bids when opponents have collected more animals.
        return self._random.expovariate(-10)

    def _completed_slope(self):
        """Generates modifier for the number of completed sets."""

        # Assume positive slope; more completed sets leads to higher bids.
        return self._random.expovariate(5)

    def _propensities(self, minimum=0, maximum=100):
        """Generates a set of propensities for trading; propensities are modeled as
        percentages and can range from 0 to 100.

        Parameters
        ----------
        minimum : int
            Lower bound for the generated propensities.
        maximum : int
            Upper bound for the generated propensities.

        Returns
        -------
        list
            List of 3 propensity percentages.
        """

        propensities = [self._random.randint(minimum, maximum) for _ in range(3)]
        return sorted(propensities)

    def bid(self, animal, player_collected, opponent_collected, ncomplete):
        """Generates a bid for an animal depending on three factors:

        1. The animal.
        2. The number of animals collected by the player.
        3. The number of animals collected by an opponent.
        4. Total number of complete sets collected by the player.

        Note: This bid not constrained by the player's budget; this is taken into
        account at the Player level.

        Parameters
        ----------
        animal : str
            Name of the animal
        player_collected : int
            Number of animals the player has collected.
        opponent_collected : int
            Number of animals opponents have collected.
        ncomplete : int
            Number of completed sets by the player.
        """

        if animal not in self._animals or animal not in self._modifiers["animals"]:
            raise KeyError(f"Animal '{animal}' not defined in strategy!")

        # Apply animal type modifier
        bid = self._animals[animal] * self._modifiers["animals"][animal]

        # Collected modifiers implemented as slopes
        bid *= 1 + self._modifiers["collected"] * player_collected
        bid *= 1 + self._modifiers["opponent_collected"] * opponent_collected

        # Apply completed sets modifier
        bid *= 1 + self._modifiers["completed_sets"] * ncomplete

        return max(bid, 0)

    def trade_decision(self, collected, counter=False):
        """Decides whether to make a trade (counter) offer or not.

        Parameters
        ----------
        collected : int
            Number of animals collected by the player (1-3).
        counter : Optional[bool]
            Boolean indicating whether it concerns a counter offer or not (default).

        Returns
        -------
        boolean
            Boolean indicating whether to engage in trading or not.
        """

        modifier = "counter_propensity" if counter else "trade_propensity"
        return self._random.randint(0, 100) >= self._modifiers[modifier][collected - 1]
