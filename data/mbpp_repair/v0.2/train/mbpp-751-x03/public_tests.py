import unittest
from solution import check_min_heap

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = check_min_heap(*[[1, 2, 3, 4, 5, 6], 0])
        expected = True
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = check_min_heap(*[[2, 3, 4, 5, 10, 15], 0])
        expected = True
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

