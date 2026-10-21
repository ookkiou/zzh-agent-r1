import unittest
from solution import capitalize_first_last_letters

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = capitalize_first_last_letters(*['python'])
        expected = 'PythoN'
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = capitalize_first_last_letters(*['bigdata'])
        expected = 'BigdatA'
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

