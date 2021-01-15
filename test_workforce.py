#!/usr/bin/env python3
import csv
import os
import time
import unittest
from src import workforce


class TestWorker(unittest.TestCase):
    def cleanup(self):
        self.planfile = "test_plan.csv"
        if os.path.isfile(self.planfile): os.remove(self.planfile)
        self.testfile = "multiproc_test"
        if os.path.isfile(self.testfile): os.remove(self.testfile)

    def setUp(self):
        self.cleanup()

    def tearDown(self):
        self.cleanup()

    def test_schema(self):
        # Tests a simple plan to make sure multiprocessing works
        test_array = [
            ["echo 1", "echo 2"],
            ["echo 2", "touch multiproc_test"],
            ["echo 2", "echo 3"]]
        with open(self.testfile, "w") as ff:
            writer = csv.writer(ff)
            writer.writerows(test_array)
        worker = workforce.worker(self.testfile)
        worker.run()
        time.sleep(1)
        assert os.path.exists(self.testfile)


if __name__ == '__main__':
    unittest.main()
