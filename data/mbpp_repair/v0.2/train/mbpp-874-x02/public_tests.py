import unittest
from solution import check_Concat

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = check_Concat(*['abcabcabc', 'abc'])
        expected = True
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = check_Concat(*['abcab', 'abc'])
        expected = False
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

