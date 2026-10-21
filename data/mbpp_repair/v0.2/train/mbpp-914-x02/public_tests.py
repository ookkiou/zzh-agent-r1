import unittest
from solution import is_Two_Alter

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = is_Two_Alter(*['abab'])
        expected = True
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = is_Two_Alter(*['aaaa'])
        expected = False
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

