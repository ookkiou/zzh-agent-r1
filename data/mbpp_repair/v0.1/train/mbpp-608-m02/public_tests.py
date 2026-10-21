import unittest
from solution import bell_Number

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = bell_Number(*[2])
        expected = 2
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = bell_Number(*[3])
        expected = 5
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

