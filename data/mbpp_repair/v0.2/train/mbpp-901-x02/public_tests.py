import unittest
from solution import smallest_multiple

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = smallest_multiple(*[13])
        expected = 360360
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = smallest_multiple(*[2])
        expected = 2
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

