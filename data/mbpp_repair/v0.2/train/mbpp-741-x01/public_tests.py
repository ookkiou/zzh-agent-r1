import unittest
from solution import all_Characters_Same

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = all_Characters_Same(*['python'])
        expected = False
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = all_Characters_Same(*['aaa'])
        expected = True
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

