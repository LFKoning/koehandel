"""Module implementing the Game class."""

import random
import logging
from itertools import cycle

import numpy as np
import pandas as pd

from deck import Deck
from player import Player
from config import Config


class Game:
    """Class for simulating a game of Koehandel.

    Parameters
    ----------
    config_file : str
        Path to the YAML configuration file.
    """

    # Player limits
    min_players = 3
    max_players = 5

    def __init__(self, config_file):

        self._log = logging.getLogger(__name__)

        self._config = Config(config_file)
        self._players = {}
        self._owners = None
        self._bonuses = self._config.get("animal_bonuses")
        self._deck = Deck(self._config.get("animals"), self._config.get("animal_cards"))

    def add_player(self, name):
        """Adds a player to the game.

        Parameters
        ----------
        name : str
            Name for the player, must be unique!
        """

        if len(self._players) >= self.max_players:
            raise ValueError(
                f"Too many players, reached maximum of {self.max_players} players."
            )

        if name in self._players:
            raise ValueError(f"Player with name '{name}' already exists.")

        player = Player(name, self._config)
        self._players[name] = player

    def run(self):
        """Runs the simulation."""

        # Make sure we have enough players
        if len(self._players) < self.min_players:
            raise ValueError(
                f"Too few players, need at least {self.min_players} players."
            )

        # Create animal ownership matrix
        self._owners = pd.DataFrame(
            0, columns=self._config.get("animals"), index=self._players
        )

        # Set up auctioneer cycling
        auctioneers = list(self._players)
        random.shuffle(auctioneers)
        auctioneers = cycle(auctioneers)

        all_complete = False
        max_turns = self._config.get("max_turns")
        turn = 1
        while not all_complete:

            # Start turn by selecting auctioneer
            auctioneer = self._players[next(auctioneers)]
            self._log.info(
                f"**** Starting turn {turn} with auctioneer {auctioneer.name} ****"
            )

            # Draw a card (if any remain) and perform turn phases
            animal = self._deck.draw()
            if animal:
                self._bonus(animal)
                self._auction(animal, auctioneer)

            self._trade(auctioneer)

            # increase turn
            turn += 1

            # Check stopping criteria
            if self._deck.remaining == 0:
                all_complete = np.all(self._owners.max(axis=0) == 4)

            # Check early stopping criteria
            if max_turns > 0 and turn > max_turns:
                break

        # Compute final scores
        scores = {
            player_name: player.final_score()
            for player_name, player in self._players.items()
        }
        self._log.info(f"Final scores: {scores}")

    def _bonus(self, animal):
        """Pays bonuses to all players upon drawing certain animals.

        Parameters
        ----------
        animal : str
            Name of the animal.
        """

        # Check card bonuses
        if animal in self._bonuses:
            bonus = self._bonuses[animal].pop(0)
            self._log.info(f"Applying bonus of {bonus} for animal {animal}.")

            for player in self._players.values():
                player.budget += bonus

    def _trade_animal(self, animal, to_player, from_player=None):
        """Convenience function for handling animal trades.

        Parameters
        ----------
        animal : str
            Name of the animal.
        to_player : player.Player
            Player object to assign the animal to.
        from_player : player.Player
            Player object to take the animal from.
        """

        to_player.add_animal(animal)
        self._owners.loc[to_player.name, animal] += 1

        if from_player:
            from_player.remove_animal(animal)
            self._owners.loc[from_player.name, animal] -= 1

    def _auction(self, animal, auctioneer):
        """Auctions an animal.

        Auctions involve the following steps:

        1. The auctioneer draws an animal card.
        2. The other players place bids on the animal.
        3. The player with the highest bid wins the auction.
        4. The auctioneer can decide to buy the animal for the highest bid.
            a) If the auctioneer buys the animal:
                - The auctioneer receives the animal.
                - The aucioneer pays the highest bid to the auction winner.
            b) If the auctioneer does not buy the animal:
                - The auction winner receives the animal.
                - The auction winner pays the auctioneer.

        Parameters
        ----------
        animal : str
            Name of the animal
        auctioneer : player.Player
            Player object who acts as auctioneer for the turn.
        """

        self._log.info(f"Auctioning animal {animal} by {auctioneer.name}.")

        # Generate player bids
        # Note: Bids are not rounded to bidding units yet to minimize ties
        total_collected = self._owners[animal].sum()
        bids = [
            (player, player.bid(animal, total_collected))
            for player in self._players.values()
            if player != auctioneer
        ]
        self._log.info(
            f"Bids: " + ", ".join([f"{player.name}: {bid:.2f}" for player, bid in bids])
        )

        # Determine winning bid
        bids.sort(key=lambda t: -t[1])
        buyer = bids[0][0]
        seller = auctioneer

        # Round to bidding units, make sure the winner can afford it
        buying_bid = self._round_bid(bids[1][1], add=1)
        buying_bid = min(buying_bid, buyer.budget)
        self._log.info(f"Player {buyer.name} wins the auction for {buying_bid}.")

        # Check whether auctioneer's bid tops it
        if auctioneer.bid(animal, total_collected) >= buying_bid:
            self._log.info(f"Auctioneer {auctioneer.name} choses to buy the {animal}.")
            seller = buyer
            buyer = auctioneer

        # Process cash flows
        buyer.budget -= buying_bid
        seller.budget += buying_bid

        # Register ownership
        self._trade_animal(animal, buyer)

        self._log.info(
            f"{buyer.name} buys the {animal} for {buying_bid}, "
            f"remaining budget equals {buyer.budget}."
        )
        self._log.info(
            f"{seller.name} sells the {animal} for {buying_bid}, "
            f"budget now equals {seller.budget}."
        )

    def _trade(self, auctioneer):
        """Resolves a trade between the auctioneer and another player.

        Trades involve the following steps:

        1. The auctioneer decides which animal to trade and with whom.
        2. The auctioneer puts in an offer.
        3. The player can choose to either:
            a) Accept the offer:
                - The auctioneer receives the animal.
                - The player receives the money offered.
            b) Make a counter-offer:
                - The auctioneer and pays the offer and receives the counter offer.
                - The player pays the counter offer and receives the offer.
                - The party with the highest bid wins the animal.

        Note that initializing a trade can also mean loosing an animal or money!

        Parameters
        ----------
        auctioneer : player.Player
            Player object who acts as auctioneer for the turn.
        """

        # Find trade candidates for the auctioneer
        self._log.info(f"Starting trading phase for {auctioneer.name}.")

        candidates = {}
        for animal in self._owners.columns:
            candidate = self._trade_candidates(
                self._owners[animal],
                auctioneer_name=auctioneer.name,
                threshold=self._config.get("trade_threshold"),
            )
            if candidate:
                candidates[animal] = candidate

        if not candidates:
            self._log.info("No suitable trading options.")
            return

        # Auctioneer decides on making an initial offer
        self._log.info(
            "Found trading options: "
            + ", ".join(
                [f"{ani} ({', '.join(opp)})" for ani, (opp, _) in candidates.items()]
            )
        )
        animal, offer = auctioneer.start_trade(candidates)

        if not animal:
            self._log.info(f"{auctioneer.name} does not want to trade.")
            return

        # Pick an opponent; random if multiple are eligible.
        opponent = random.choice(candidates[animal][0])
        self._log.info(
            f"{auctioneer.name} wants to trade a {animal} with {opponent} for {offer:.2f}."
        )

        # Opponent decides on counter offer
        opponent = self._players[opponent]
        counter_offer = opponent.trade_counter(animal, candidates[animal][1])

        self._log.info(
            f"{opponent.name} counters with an offer of {counter_offer:.2f}."
        )

        # Handle animal ownership
        if offer >= counter_offer:
            self._log.info(
                f"{auctioneer.name} wins the trade for a {animal} from {opponent.name}."
            )
            self._trade_animal(animal, auctioneer, opponent)
        else:
            self._log.info(
                f"{auctioneer.name} loses the trade for a {animal} to {opponent.name}."
            )
            self._trade_animal(animal, opponent, auctioneer)

        # Round offers and handle cash flows
        counter_offer = self._round_bid(counter_offer)
        offer = self._round_bid(offer)

        auctioneer.budget = auctioneer.budget - offer + counter_offer
        self._log.info(
            f"{auctioneer.name} pays {offer} and gains {counter_offer}, "
            f"budget is now {auctioneer.budget}."
        )

        opponent.budget = opponent.budget - counter_offer + offer
        self._log.info(
            f"{opponent.name} pays {counter_offer} and gains {offer}, "
            f"budget is now {opponent.budget}."
        )

    @staticmethod
    def _trade_candidates(animal_column, auctioneer_name, threshold=2):
        """Selects trading candidates and associated opponents.

        Parameters
        ----------
        animal_columns : pandas.Series
            Column from self._owners to apply candidate selection to.
        auctioneer_name : str
            Name of the auctioneer.
        threshold : int
            Threshold for starting trades.
        """

        total = animal_column.sum()
        collected = animal_column[auctioneer_name]
        if threshold <= collected < 4:
            animal_column = animal_column.drop(auctioneer_name)
            opponents = list(animal_column[animal_column > 0].index)

            if opponents:
                return opponents, total

        return None

    def _round_bid(self, bid, add=0):
        """Rounds bid to game's minimal bidding unit.

        Parameters
        ----------
        bid : float
            The bid as made by a players bid method.
        add : Optional[int]
            The number of bidding units to add.

        Returns
        -------
        int
            The bid rounded to the game's minimal bidding unit.
        """

        bid_unit = self._config.get("bid_unit")
        return int(round(bid / bid_unit) * bid_unit + add * bid_unit)
