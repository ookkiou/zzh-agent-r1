import unittest
from solution import maximum_segments

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = maximum_segments(*[7, 5, 2, 5])
        expected = 2
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = maximum_segments(*[17, 2, 1, 3])
        expected = 17
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

