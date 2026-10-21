import unittest
from solution import odd_Num_Sum

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = odd_Num_Sum(*[2])
        expected = 82
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = odd_Num_Sum(*[3])
        expected = 707
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

