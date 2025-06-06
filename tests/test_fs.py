import os
import unittest
import subprocess
import time

ADA_FS_SCRIPT = "adafs.py"

class TestAdaFS(unittest.TestCase):

    def setUp(self):
        self.src_dir = os.path.join(os.getcwd(), "tests/fixtures/case1")
        self.mnt = os.path.join("/tmp", "mnt")
        os.makedirs(self.mnt, exist_ok=True)
        self.proc = subprocess.Popen(
            ["python3", ADA_FS_SCRIPT, self.src_dir, self.mnt],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        time.sleep(0.5)

    def tearDown(self):
        self.proc.terminate()
        self.proc.wait()

    def test_case1_single_package(self):
        self.assertEqual(sorted(os.listdir(self.mnt)), ["A"])
        a_dir = os.path.join(self.mnt, "A")
        self.assertEqual(set(os.listdir(a_dir)), {"A.ads", "A.adb"})
        with open(os.path.join(a_dir, "A.ads"), "rb") as virt, \
             open(os.path.join(self.src_dir, "a-2adb2f.ads"), "rb") as real:
            self.assertEqual(virt.read(), real.read())
        with open(os.path.join(a_dir, "A.adb"), "rb") as virt, \
             open(os.path.join(self.src_dir, "a-2adb2f.adb"), "rb") as real:
            self.assertEqual(virt.read(), real.read())

if __name__ == '__main__':
    unittest.main()
