import unittest
from solution import lcm

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = lcm(*[4, 6])
        expected = 12
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = lcm(*[15, 17])
        expected = 255
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

