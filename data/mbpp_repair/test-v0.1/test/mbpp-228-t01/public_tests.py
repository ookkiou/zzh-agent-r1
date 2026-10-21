import unittest
from solution import all_Bits_Set_In_The_Given_Range

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = all_Bits_Set_In_The_Given_Range(*[4, 1, 2])
        expected = True
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = all_Bits_Set_In_The_Given_Range(*[17, 2, 4])
        expected = True
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

