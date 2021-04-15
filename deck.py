"""Module implementing the Deck class."""

import json
import random


class Deck:
    """Class for managing the Koehandel deck.

    Parameters
    ----------
    animals : dict
        Dict mapping animals and score points.
    cards_each : Optional[int]
        Number of cards for each animal type, defaults to 4.
    """

    def __init__(self, config):

        animals = config.get("animals")
        cards_each = config.get("cards_each", 4)

        self._pointer = 0
        self._cards = [animal for _ in range(cards_each) for animal in animals]
        random.shuffle(self._cards)

    @property
    def remaining(self):
        """Returns remaining number of cards.

        Returns
        -------
        int
            Number of cards remaining in the deck.
        """

        return len(self._cards)

    def draw(self):
        """Draws a card from the deck.

        Returns
        -------
        str
            Name of an animal.
        """

        if self._pointer < len(self._cards):
            draw = self._cards[self._pointer]
            self._pointer += 1
            return draw
        return None

    def serialize(self):
        """Serializes the deck into a JSON string.

        Returns
        -------
        str
            Cards as JSON string.
        """

        return json.dumps(self._cards)

    def deserialize(self, json_str):
        """Loads deck from a JSON string.

        Parameters
        ----------
        json_str : str
            JSON string representation of the cards
        """

        self._cards = json.loads(json_str)
