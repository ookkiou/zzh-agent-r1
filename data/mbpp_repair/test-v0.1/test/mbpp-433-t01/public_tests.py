import unittest
from solution import check_greater

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = check_greater(*[[1, 2, 3, 4, 5], 4])
        expected = 'No, entered number is less than those in the array'
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = check_greater(*[[2, 3, 4, 5, 6], 8])
        expected = 'Yes, the entered number is greater than those in the array'
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

