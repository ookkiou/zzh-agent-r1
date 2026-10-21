import unittest
from solution import nCr_mod_p

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = nCr_mod_p(*[10, 2, 13])
        expected = 6
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = nCr_mod_p(*[11, 3, 14])
        expected = 11
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

