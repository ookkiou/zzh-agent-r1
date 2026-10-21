import unittest
from solution import count_Unset_Bits

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = count_Unset_Bits(*[2])
        expected = 1
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = count_Unset_Bits(*[5])
        expected = 4
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

