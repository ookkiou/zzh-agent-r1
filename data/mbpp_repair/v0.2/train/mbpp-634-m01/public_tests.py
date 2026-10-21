import unittest
from solution import even_Power_Sum

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = even_Power_Sum(*[2])
        expected = 272
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = even_Power_Sum(*[3])
        expected = 1568
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

