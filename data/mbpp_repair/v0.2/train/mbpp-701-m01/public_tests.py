import unittest
from solution import equilibrium_index

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = equilibrium_index(*[[1, 2, 3, 4, 1, 2, 3]])
        expected = 3
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = equilibrium_index(*[[-7, 1, 5, 2, -4, 3, 0]])
        expected = 3
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

