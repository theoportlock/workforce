import unittest
import time
import pandas as pd
import os
import workforce

class TestWorker(unittest.TestCase):
    def test_schema(self):
        # Tests a simple plan to make sure multiprocessing works
        test_plan = "test_plan.csv"
        multi_test = "multiproc_test"

        if os.path.exists(test_plan):
            os.remove(test_plan)
        if os.path.exists(multi_test):
            os.remove(multi_test)

        test_array = pd.DataFrame([["echo 1", "echo 2"],
            ["echo 2", "touch multiproc_test"],
            ["echo 2", "echo 3"]])
        test_array.to_csv(test_plan, header=False, index=False)
        worker = workforce.worker(test_plan)
        worker.run()
        time.sleep(1)
        assert os.path.exists(multi_test)

        if os.path.exists(test_plan):
            os.remove(test_plan)
        if os.path.exists(multi_test):
            os.remove(multi_test)
