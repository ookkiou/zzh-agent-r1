import unittest
from solution import Check_Solution

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = Check_Solution(*[2, 5, 2])
        expected = '2 solutions'
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = Check_Solution(*[1, 1, 1])
        expected = 'No solutions'
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

