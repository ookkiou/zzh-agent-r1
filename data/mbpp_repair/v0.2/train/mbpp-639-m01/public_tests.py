import unittest
from solution import sample_nam

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = sample_nam(*[['sally', 'Dylan', 'rebecca', 'Diana', 'Joanne', 'keith']])
        expected = 16
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = sample_nam(*[['php', 'res', 'Python', 'abcd', 'Java', 'aaa']])
        expected = 10
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

