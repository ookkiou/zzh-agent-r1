import unittest
from solution import divisor

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = divisor(*[15])
        expected = 4
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = divisor(*[12])
        expected = 6
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

