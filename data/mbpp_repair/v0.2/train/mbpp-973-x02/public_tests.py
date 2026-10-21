import unittest
from solution import left_rotate

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = left_rotate(*['python', 2])
        expected = 'thonpy'
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = left_rotate(*['bigdata', 3])
        expected = 'databig'
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

