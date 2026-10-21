import unittest
from solution import number_ctr

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = number_ctr(*['program2bedone'])
        expected = 1
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = number_ctr(*['3wonders'])
        expected = 1
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

