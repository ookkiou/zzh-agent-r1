import unittest
from solution import Seq_Linear

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = Seq_Linear(*[[0, 2, 4, 6, 8, 10]])
        expected = 'Linear Sequence'
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = Seq_Linear(*[[1, 2, 3]])
        expected = 'Linear Sequence'
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

