import unittest
from solution import count_range_in_list

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = count_range_in_list(*[[10, 20, 30, 40, 40, 40, 70, 80, 99], 40, 100])
        expected = 6
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = count_range_in_list(*[['a', 'b', 'c', 'd', 'e', 'f'], 'a', 'e'])
        expected = 5
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

