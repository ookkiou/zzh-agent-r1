import unittest
from solution import find_Element

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = find_Element(*[[1, 2, 3, 4, 5], [[0, 2], [0, 3]], 2, 1])
        expected = 3
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = find_Element(*[[1, 2, 3, 4], [[0, 1], [0, 2]], 1, 2])
        expected = 3
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

