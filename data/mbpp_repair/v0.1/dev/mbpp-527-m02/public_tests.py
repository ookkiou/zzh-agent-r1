import unittest
from solution import get_pairs_count

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = get_pairs_count(*[[1, 5, 7, -1, 5], 5, 6])
        expected = 3
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = get_pairs_count(*[[1, 5, 7, -1], 4, 6])
        expected = 2
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

