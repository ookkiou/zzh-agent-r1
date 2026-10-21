import unittest
from solution import dealnnoy_num

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = dealnnoy_num(*[3, 4])
        expected = 129
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = dealnnoy_num(*[3, 3])
        expected = 63
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

