import unittest
from solution import check_monthnumber_number

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = check_monthnumber_number(*[6])
        expected = True
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = check_monthnumber_number(*[2])
        expected = False
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

