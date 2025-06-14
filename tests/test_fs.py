import os
import subprocess
import shutil
import tempfile
import unittest
from pathlib import Path
import time
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
ADA_FS_SCRIPT = str(REPO_ROOT / "adafs.py")

class FSBase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)

    def is_verbose(self) -> bool:
        """Return True if the tests are running in verbose mode."""
        return any(arg.startswith("-v") or arg == "--verbose" for arg in sys.argv)

    def print_tree(self, path: str) -> None:
        """Print directory tree of path if the `tree` command exists."""
        if not self.is_verbose():
            return
        tree_bin = shutil.which("tree")
        if tree_bin:
            subprocess.run([tree_bin, path], check=False)

    def mount_fs(self, src_dir: str) -> str:
        mnt = os.path.join(self.tmpdir.name, "mnt")
        if os.path.exists(mnt):
            shutil.rmtree(mnt)
        os.mkdir(mnt)
        subprocess.run([
            "python3",
            ADA_FS_SCRIPT,
            "mount",
            str(src_dir),
            str(mnt),
        ], check=True)
        return mnt

    def fixture_path(self, case: str, name: str) -> str:
        return os.path.join(REPO_ROOT, "tests", "fixtures", case, name)


class TestFs(FSBase):
    def test_case1_single_package(self):
        src = os.path.join(REPO_ROOT, "tests/fixtures/case1")
        mnt = self.mount_fs(src)
        self.print_tree(mnt)
        self.assertEqual(sorted(os.listdir(mnt)), ["A"])
        a_dir = os.path.join(mnt, "A")
        self.assertEqual(set(os.listdir(a_dir)), {"A.ads", "A.adb"})
        with open(os.path.join(a_dir, "A.ads"), "rb") as v, open(self.fixture_path("case1", "a-2adb2f.ads"), "rb") as r:
            self.assertEqual(v.read(), r.read())
        with open(os.path.join(a_dir, "A.adb"), "rb") as v, open(self.fixture_path("case1", "a-2adb2f.adb"), "rb") as r:
            self.assertEqual(v.read(), r.read())

    def test_case2_spec_only(self):
        src = os.path.join(REPO_ROOT, "tests/fixtures/case2")
        mnt = self.mount_fs(src)
        self.print_tree(mnt)
        self.assertEqual(sorted(os.listdir(mnt)), ["UTIL"])
        util_dir = os.path.join(mnt, "UTIL")
        self.assertEqual(os.listdir(util_dir), ["UTIL.ads"])
        with open(os.path.join(util_dir, "UTIL.ads"), "rb") as v, open(self.fixture_path("case2", "util-1a2b3c.ads"), "rb") as r:
            self.assertEqual(v.read(), r.read())
        with self.assertRaises(FileNotFoundError):
            open(os.path.join(util_dir, "UTIL.adb"), "rb")

    def test_case3_nested_child(self):
        src = os.path.join(REPO_ROOT, "tests/fixtures/case3")
        mnt = self.mount_fs(src)
        self.print_tree(mnt)
        self.assertEqual(sorted(os.listdir(mnt)), ["OUTER"])
        outer_dir = os.path.join(mnt, "OUTER")
        self.assertEqual(set(os.listdir(outer_dir)), {"OUTER.ads", "OUTER.adb", "INNER"})
        inner_dir = os.path.join(outer_dir, "INNER")
        self.assertEqual(os.listdir(inner_dir), ["INNER.ads"])
        with open(os.path.join(outer_dir, "OUTER.ads"), "rb") as v, open(self.fixture_path("case3", "outer-aaaaaa.ads"), "rb") as r:
            self.assertEqual(v.read(), r.read())
        with open(os.path.join(inner_dir, "INNER.ads"), "rb") as v, open(self.fixture_path("case3", "outer_dot_inner-bbbbb1.ads"), "rb") as r:
            self.assertEqual(v.read(), r.read())

    def test_case4_grandchild(self):
        src = os.path.join(REPO_ROOT, "tests/fixtures/case4")
        mnt = self.mount_fs(src)
        self.print_tree(mnt)
        self.assertEqual(os.listdir(mnt), ["PKG"])
        pkg_dir = os.path.join(mnt, "PKG")
        self.assertEqual(set(os.listdir(pkg_dir)), {"PKG.ads", "PKG.adb", "PKG.SUB"})
        sub_dir = os.path.join(pkg_dir, "PKG.SUB", "SUB")
        self.assertEqual(set(os.listdir(sub_dir)), {"SUB.ads", "SUB.adb", "LEAF"})
        leaf_dir = os.path.join(sub_dir, "LEAF")
        self.assertEqual(os.listdir(leaf_dir), ["LEAF.ads"])

    def test_case5a_collision_body(self):
        case_dir = os.path.join(self.tmpdir.name, "case5a")
        shutil.copytree(os.path.join(REPO_ROOT, "tests/fixtures/case5a"), case_dir)
        dup = os.path.join(case_dir, "pkg-bbbbbbbb.adb")
        with open(dup, "w") as f:
            f.write("-- duplicate body")
        mnt = self.mount_fs(case_dir)
        self.print_tree(mnt)
        pkg_dir = os.path.join(mnt, "PKG")
        files = sorted(os.listdir(pkg_dir))
        self.assertEqual(files.count("PKG.adb"), 1)
        self.assertIn("PKG.ads", files)

    def test_case5b_collision_spec(self):
        src = os.path.join(REPO_ROOT, "tests/fixtures/case5b")
        mnt = self.mount_fs(src)
        self.print_tree(mnt)
        pkg_dir = os.path.join(mnt, "X")
        files = sorted(os.listdir(pkg_dir))
        self.assertEqual(files, ["X.ads"])

    @unittest.expectedFailure
    def test_case6_read_only(self):
        src = os.path.join(REPO_ROOT, "tests/fixtures/case6")
        mnt = self.mount_fs(src)
        self.print_tree(mnt)
        a_dir = os.path.join(mnt, "A")
        os.open(os.path.join(a_dir, "NEW.ads"), os.O_CREAT | os.O_WRONLY).close()

    def test_case7_long_names(self):
        src = os.path.join(REPO_ROOT, "tests/fixtures/case7")
        mnt = self.mount_fs(src)
        self.print_tree(mnt)
        leaf = os.path.join(mnt, "SUPER_LONG_PKG", "SUB_PKG", "LEAF_PKG")
        self.assertTrue(os.path.isdir(leaf))
        self.assertEqual(os.listdir(os.path.join(mnt, "SUPER_LONG_PKG")), ["SUB_PKG"])
        self.assertEqual(os.listdir(os.path.join(mnt, "SUPER_LONG_PKG", "SUB_PKG")), ["LEAF_PKG"])
        with open(os.path.join(leaf, "LEAF_PKG.ads"), "rb") as v, open(self.fixture_path("case7", "super_long_pkg_dot_sub_pkg_dot_leaf_pkg-abcdef.ads"), "rb") as r:
            self.assertEqual(v.read(), r.read())

    def test_case8_case_insensitive(self):
        src = os.path.join(REPO_ROOT, "tests/fixtures/case8")
        mnt = self.mount_fs(src)
        self.print_tree(mnt)
        self.assertEqual(os.listdir(mnt), ["MATH"])
        vec_dir_upper = os.path.join(mnt, "MATH", "VECTOR")
        self.assertEqual(os.listdir(vec_dir_upper), ["VECTOR.ads"])

    def test_case9_hide_noise(self):
        src = os.path.join(REPO_ROOT, "tests/fixtures/case9")
        mnt = self.mount_fs(src)
        self.print_tree(mnt)
        self.assertEqual(os.listdir(mnt), ["A"])
        a_dir = os.path.join(mnt, "A")
        self.assertEqual(set(os.listdir(a_dir)), {"A.ads", "A.adb"})
        self.assertNotIn("README.txt", os.listdir(mnt))

    def generate_case10(self, root: Path) -> None:
        root.mkdir()
        for i in range(1, 201):
            h = f"{i:06x}"
            base = f"pkg{i}"
            (root / f"{base}-{h}.ads").write_text("spec")
            (root / f"{base}-{h}.adb").write_text("body")
            for j in range(1, 4):
                sub = f"{base}_dot_sub{j}"
                (root / f"{sub}-{h}.ads").write_text("spec")
                (root / f"{sub}-{h}.adb").write_text("body")

    def test_case10_large_hierarchy_performance(self):
        case_dir = Path(self.tmpdir.name) / "case10"
        self.generate_case10(case_dir)
        mnt = self.mount_fs(str(case_dir))
        self.print_tree(mnt)
        start = time.time()
        root_entries = os.listdir(mnt)
        t_root = time.time() - start
        self.assertEqual(len(root_entries), 200)
        test_path = os.path.join(mnt, "PKG150", "SUB2")
        start = time.time()
        _ = os.listdir(test_path)
        t_sub = time.time() - start
        leaf = os.path.join(test_path, "SUB2.ads")
        start = time.time()
        os.stat(leaf)
        t_stat = time.time() - start
        self.assertLess(t_root, 1.0)
        self.assertLess(t_sub, 0.1)
        self.assertLess(t_stat, 0.05)

    def test_case11_preserve_nested(self):
        src = os.path.join(REPO_ROOT, "tests/fixtures/case11")
        mnt = self.mount_fs(src)
        self.print_tree(mnt)
        self.assertEqual(sorted(os.listdir(mnt)), ["A", "legacy"])
        a_dir = os.path.join(mnt, "A")
        self.assertEqual(set(os.listdir(a_dir)), {"A.ads", "A.adb"})
        legacy_dir = os.path.join(mnt, "legacy")
        grp = os.path.join(legacy_dir, "legacy.X")
        x_dir = os.path.join(grp, "X")
        y_dir = os.path.join(x_dir, "Y")
        self.assertEqual(set(os.listdir(x_dir)), {"X.ads", "X.adb", "Y"})
        self.assertEqual(os.listdir(y_dir), ["Y.ads"])
        with open(os.path.join(y_dir, "Y.ads"), "rb") as v, open(self.fixture_path("case11/legacy", "x_dot_y-222222.ads"), "rb") as r:
            self.assertEqual(v.read(), r.read())
        self.assertNotIn("noise.txt", os.listdir(mnt))

    def test_case12_recursive_categorization(self):
        src = os.path.join(REPO_ROOT, "tests/fixtures/case12")
        mnt = self.mount_fs(src)
        self.print_tree(mnt)
        system_dir = os.path.join(mnt, "SYSTEM")
        self.assertEqual(os.listdir(system_dir), ["SYSTEM.TOTO"])
        grp = os.path.join(system_dir, "SYSTEM.TOTO")
        toto_dir = os.path.join(grp, "TOTO")
        self.assertEqual(set(os.listdir(toto_dir)), {"TOTO.ads", "TOTO.adb", "SYSTEM.TOTO.TITI"})
        titi_grp = os.path.join(toto_dir, "SYSTEM.TOTO.TITI")
        titi_dir = os.path.join(titi_grp, "TITI")
        self.assertEqual(set(os.listdir(titi_dir)), {"TITI.ads", "TATA"})
        tata_dir = os.path.join(titi_dir, "TATA")
        self.assertEqual(os.listdir(tata_dir), ["TATA.ads"])


if __name__ == "__main__":
    unittest.main()
