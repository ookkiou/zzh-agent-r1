import unittest
from solution import is_Isomorphic

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = is_Isomorphic(*['paper', 'title'])
        expected = True
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = is_Isomorphic(*['ab', 'ba'])
        expected = True
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

