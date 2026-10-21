import unittest
from solution import count_Fac

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = count_Fac(*[24])
        expected = 3
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = count_Fac(*[12])
        expected = 2
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

