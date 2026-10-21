import unittest
from solution import are_Rotations

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = are_Rotations(*['abc', 'cba'])
        expected = False
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = are_Rotations(*['abcd', 'cdba'])
        expected = False
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

