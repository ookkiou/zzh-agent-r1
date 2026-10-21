import unittest
from solution import is_undulating

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = is_undulating(*['1212121'])
        expected = True
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = is_undulating(*['1991'])
        expected = False
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

