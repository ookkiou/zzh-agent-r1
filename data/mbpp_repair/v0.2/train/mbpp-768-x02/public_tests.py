import unittest
from solution import check_Odd_Parity

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = check_Odd_Parity(*[13])
        expected = True
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = check_Odd_Parity(*[21])
        expected = True
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

