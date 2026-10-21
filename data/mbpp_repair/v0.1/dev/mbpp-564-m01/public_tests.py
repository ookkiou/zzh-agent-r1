import unittest
from solution import count_Pairs

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = count_Pairs(*[[1, 2, 1], 3])
        expected = 2
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = count_Pairs(*[[1, 1, 1, 1], 4])
        expected = 0
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

