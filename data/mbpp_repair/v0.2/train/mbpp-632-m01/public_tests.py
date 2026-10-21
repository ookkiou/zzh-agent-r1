import unittest
from solution import move_zero

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = move_zero(*[[1, 0, 2, 0, 3, 4]])
        expected = [1, 2, 3, 4, 0, 0]
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = move_zero(*[[2, 3, 2, 0, 0, 4, 0, 5, 0]])
        expected = [2, 3, 2, 4, 5, 0, 0, 0, 0]
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

