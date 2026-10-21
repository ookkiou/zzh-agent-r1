import unittest
from solution import get_total_number_of_sequences

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = get_total_number_of_sequences(*[10, 4])
        expected = 4
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = get_total_number_of_sequences(*[5, 2])
        expected = 6
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

