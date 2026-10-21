import unittest
from solution import check_Validity

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = check_Validity(*[1, 2, 3])
        expected = False
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = check_Validity(*[2, 3, 5])
        expected = False
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

