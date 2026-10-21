import unittest
from solution import cube_Sum

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = cube_Sum(*[2])
        expected = 28
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = cube_Sum(*[3])
        expected = 153
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

