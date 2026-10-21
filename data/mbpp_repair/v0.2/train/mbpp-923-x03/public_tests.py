import unittest
from solution import super_seq

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = super_seq(*['AGGTAB', 'GXTXAYB', 6, 7])
        expected = 9
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = super_seq(*['feek', 'eke', 4, 3])
        expected = 5
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

