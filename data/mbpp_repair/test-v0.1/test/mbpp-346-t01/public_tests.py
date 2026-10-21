import unittest
from solution import zigzag

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = zigzag(*[4, 3])
        expected = 5
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = zigzag(*[4, 2])
        expected = 4
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

