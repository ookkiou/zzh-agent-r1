import unittest
from solution import increment_numerics

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = increment_numerics(*[['MSM', '234', 'is', '98', '123', 'best', '4'], 6])
        expected = ['MSM', '240', 'is', '104', '129', 'best', '10']
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = increment_numerics(*[['Dart', '356', 'is', '88', '169', 'Super', '6'], 12])
        expected = ['Dart', '368', 'is', '100', '181', 'Super', '18']
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

