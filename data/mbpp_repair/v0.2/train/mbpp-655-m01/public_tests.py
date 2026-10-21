import unittest
from solution import fifth_Power_Sum

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = fifth_Power_Sum(*[2])
        expected = 33
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = fifth_Power_Sum(*[4])
        expected = 1300
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

