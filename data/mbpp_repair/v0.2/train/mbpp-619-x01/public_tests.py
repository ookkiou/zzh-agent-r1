import unittest
from solution import move_num

class PublicTests(unittest.TestCase):
    def test_public_01(self):
        actual = move_num(*['I1love143you55three3000thousand'])
        expected = 'Iloveyouthreethousand1143553000'
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

    def test_public_02(self):
        actual = move_num(*['Avengers124Assemble'])
        expected = 'AvengersAssemble124'
        self.assertIs(type(actual), type(expected))
        self.assertEqual(actual, expected)

