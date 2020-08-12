import unittest
import time
import pandas as pd
import os
import workforce

class TestWorker(unittest.TestCase):
    def cleanup(self):
        for testing_file in self.testing_files.values():
            if os.path.isfile(testing_file):
                os.remove(testing_file) 

    def setUp(self):
        self.testing_files = {
            "test": "test_plan.csv",
            "result": "multiproc_test"}
        self.cleanup()

    def tearDown(self):
        self.cleanup()

    def test_schema(self):
        # Tests a simple plan to make sure multiprocessing works
        test_array = pd.DataFrame(
                    [["echo 1", "echo 2"],
                    ["echo 2", "touch multiproc_test"],
                    ["echo 2", "echo 3"]])
        test_array.to_csv(self.testing_files["test"], header=False, index=False)
        worker = workforce.worker(self.testing_files["test"])
        worker.run()
        time.sleep(1)
        assert os.path.exists(self.testing_files["result"])

if __name__ == '__main__':
    unittest.main()

