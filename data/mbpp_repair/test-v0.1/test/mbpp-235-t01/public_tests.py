import unittest
from solution import even_bit_set_number

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = even_bit_set_number(*[10])
        expected = 10
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = even_bit_set_number(*[20])
        expected = 30
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

