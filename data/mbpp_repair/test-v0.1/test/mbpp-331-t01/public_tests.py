import unittest
from solution import count_unset_bits

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = count_unset_bits(*[2])
        expected = 1
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = count_unset_bits(*[4])
        expected = 2
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

