import unittest
from solution import neg_nos

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = neg_nos(*[[-1, 4, 5, -6]])
        expected = -1
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = neg_nos(*[[-1, -2, 3, 4]])
        expected = -1
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

