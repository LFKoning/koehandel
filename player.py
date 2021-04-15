"""Module implementing the player class."""

import pandas as pd

from strategy import Strategy


class Player:
    """Class for the Koehandel player.

    Parameters
    ----------
    name : str
        Name for the player, must be unique!
    config : config.Config
        Object containing the YAML configuration.
    """

    def __init__(self, name, config):

        self.name = name
        self._config = config
        self.budget = config.get("start_budget")

        animals = config.get("animals")
        self._hand = pd.DataFrame(
            {"count": [0] * len(animals), "value": animals.values()}, index=animals,
        )

        self._strategy = Strategy(animals)

    def add_animal(self, animal):
        """Adds an animal to the player's hand.

        Parameters
        ----------
        animal : str
            Name of the animal.
        """

        self._hand.loc[animal, "count"] += 1

    def remove_animal(self, animal):
        """Removes an animal from the players hand.

        Parameters
        ----------
        animal : str
            Name of the animal.
        """

        if self._hand.loc[animal, "count"] > 0:
            self._hand.loc[animal, "count"] -= 1
        else:
            raise ValueError(f"Player {self.name}: Don't have a {animal} in my hand.")

    def bid(self, animal, total_collected, budget_cap=True):
        """Makes a bid during an auction phase of the game. The bid depends on the
        player's strategy and contextual variables such as number of animals collected,
        number of sets completed, et cetera.

        Parameters
        ----------
        animal : str
            Name of the animal to bid on.
        total_collected : int
            Number of animals collected by opponents.
        budget_cap : Optional[bool]
            Constrain the bid by the players available budget.

        Returns
        -------
        float
            The player's bid for the animal.
        """

        # Create unconstrained bid
        self_collected = self.count(animal)
        opponent_collected = total_collected - self_collected
        bid = self._strategy.bid(
            animal, self_collected, opponent_collected, self.complete_sets()
        )

        # Cap to budget if requested
        if budget_cap:
            return min(bid, self.budget)
        return bid

    def start_trade(self, candidates):
        """Creates an offer when trading with another player.

        Parameters
        ----------
        candidates : dict
            Dict of trading candidates in format:
            {animal: [<available opponents>], <total number collected>}

        Returns
        -------
        Tuple(str, float)
            Tuple of animal name and offer; the animal name is None if the player
            does not want to trade.
        """

        trade_animal = None
        trade_bid = 0
        for animal, (_, total_collected) in candidates.items():

            # Decide whether to start trading
            collected = self.count(animal)
            if self._strategy.trade_decision(collected):
                # Generate an offer
                bid = self.bid(animal, total_collected, False)

                # Only trade when the budget covers at least 80% of the bid.
                # TODO: Prevents silly offers, make this part of the strategy?
                if bid == 0 or self.budget / bid < 0.8:
                    continue

                # Note: Selecting the most wanted animal (aka the highest bid).
                if bid > trade_bid:
                    trade_animal = animal
                    trade_bid = min(bid, self.budget)

        return trade_animal, trade_bid

    def trade_counter(self, animal, total_collected):
        """Creates a counter offer when trading with another player.

        Parameters
        ----------
        animal : str
            Name of the animal.
        total_collected : int
            Number of animals collected by all players.

        Returns
        -------
        float
            Counter offer to a trade request.
        """

        collected = self.count(animal)
        counter_bid = 0
        if self._strategy.trade_decision(collected, counter=True):
            counter_bid = self.bid(animal, total_collected)

        return counter_bid

    def final_score(self):
        """Compute final score as point total using these steps:

        1. Select complete sets only.
        2. Sum points for each complete set.
        3. Multiply by the number of sets completed.
        4. Optional: add remaining player budget.

        TODO: Make sets above threshold complete, so they count as 4 cards.

        Returns
        -------
        int
            Final score.
        """

        threshold = self._config.get("score_threshold", 4)
        points_total = (
            self._hand.loc[self._hand["count"] >= threshold].product(axis=1).sum()
        )
        points_total = points_total * self.complete_sets(threshold=threshold)

        if self._config.get("score_budget"):
            points_total += self.budget

        return points_total

    def count(self, animal):
        """Counts number of animals collected by the player.

        Parameters
        ----------
        animal : str
            Name of the animal

        Returns
        -------
        int
            Number of animals collected by the player.
        """

        return self._hand.loc[animal, "count"]

    def complete_sets(self, threshold=4):
        """Returns the number of completed sets. The threshold determines
        what counts as completed.

        Parameters
        ----------
        threshold : Optional[int]
            Minimal number of animals that count as completed set.

        Returns
        -------
        int
            Number of sets the player has completed.
        """

        return (self._hand["count"] >= threshold).sum()

    def __eq__(self, other):
        """Compare by name only; name should be unique."""

        return self.name.lower() == other.name.lower()

    def __hash__(self):
        """Make hashable by name to enforce unique names."""

        return hash(self.name.lower())
