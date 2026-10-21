import unittest
from solution import sum_Of_Subarray_Prod

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = sum_Of_Subarray_Prod(*[[1, 2, 3], 3])
        expected = 20
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = sum_Of_Subarray_Prod(*[[1, 2], 2])
        expected = 5
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

