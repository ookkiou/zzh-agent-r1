import unittest
from solution import sort_by_dnf

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = sort_by_dnf(*[[1, 2, 0, 1, 0, 1, 2, 1, 1], 9])
        expected = [0, 0, 1, 1, 1, 1, 1, 2, 2]
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = sort_by_dnf(*[[1, 0, 0, 1, 2, 1, 2, 2, 1, 0], 10])
        expected = [0, 0, 0, 1, 1, 1, 1, 2, 2, 2]
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

