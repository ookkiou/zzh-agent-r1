import unittest
from solution import move_first

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = move_first(*[[1, 2, 3, 4]])
        expected = [4, 1, 2, 3]
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = move_first(*[[0, 1, 2, 3]])
        expected = [3, 0, 1, 2]
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

