import unittest
from solution import all_unique

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = all_unique(*[[1, 2, 3]])
        expected = True
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = all_unique(*[[1, 2, 1, 2]])
        expected = False
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

