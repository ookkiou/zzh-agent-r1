import unittest
from solution import jacobsthal_num

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = jacobsthal_num(*[5])
        expected = 11
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = jacobsthal_num(*[2])
        expected = 1
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

