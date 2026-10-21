import unittest
from solution import sum_Of_Primes

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = sum_Of_Primes(*[10])
        expected = 17
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = sum_Of_Primes(*[20])
        expected = 77
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

