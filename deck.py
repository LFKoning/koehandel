"""Module implementing the Deck class."""

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

    def __init__(self, animals, cards_each=4):

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

        if self._cards:
            return self._cards.pop()
        return None
