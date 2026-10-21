import unittest
from solution import len_log

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = len_log(*[['python', 'PHP', 'bigdata']])
        expected = 7
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = len_log(*[['a', 'ab', 'abc']])
        expected = 3
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

