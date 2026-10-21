import unittest
from solution import Repeat

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = Repeat(*[[10, 20, 30, 20, 20, 30, 40, 50, -20, 60, 60, -20, -20]])
        expected = [20, 30, -20, 60]
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = Repeat(*[[-1, 1, -1, 8]])
        expected = [-1]
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

