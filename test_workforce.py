#!/usr/bin/env python3
import unittest
import time
import pandas as pd
import os
import workforce


class TestWorker(unittest.TestCase):
    def cleanup(self):
        self.testfile = "test_plan.csv"
        if os.path.isfile(self.testfile):
            os.remove(self.testfile)

    def setUp(self):
        self.cleanup()

    def tearDown(self):
        self.cleanup()

    def test_schema(self):
        # Tests a simple plan to make sure multiprocessing works
        multi_test = "multiproc_test"
        test_array = pd.DataFrame([
            ["echo 1", "echo 2"],
            ["echo 2", "touch multiproc_test"],
            ["echo 2", "echo 3"]])
        test_array.to_csv(self.testfile, header=False, index=False)
        worker = workforce.worker(self.testfile)
        worker.run()
        time.sleep(1)
        assert os.path.exists(multi_test)
        if os.path.exists(multi_test):
            os.remove(multi_test)


if __name__ == '__main__':
    unittest.main()
