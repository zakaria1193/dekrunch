Below is a detailed set of instructions you can hand off to a coder‐focused AI agent. It describes exactly what the FUSE‐based Ada package viewer must do, how it should handle every scenario we’ve outlined (including preserving existing subdirectories), and how to validate correctness via a comprehensive test suite. Think of this as a “developer briefing” that covers both implementation requirements and the tests that must pass.

---

## 1. Project Overview

You are building a Python‐based FUSE filesystem (“adafs”) whose job is to take a directory containing “GNAT‐crunched” Ada sources (with hashed filenames like `foo‐1a2b3c.ads`, `foo_dot_bar‐4d5e6f.adb`, etc.) and present a **clean, human‐readable Ada package hierarchy**:

* Each top-level Ada package appears as a directory whose name is the package name (uppercased).
* Inside each package directory, you expose `.ads` and/or `.adb` files named exactly as the package (e.g. `FOO.ads`, `FOO.adb`).
* Nested (“child” and “grandchild”) Ada packages (indicated by `_dot_` in the original names) become subdirectories. For example, `foo_dot_bar‐xxxx.ads` → `/mnt/FOO/BAR/BAR.ads`.
* The mount is strictly **read-only**: any attempt to write, create, delete, or rename should return the appropriate error (EPERM or EROFS).
* Non‐Ada files (anything other than `.ads` or `.adb`) should be hidden entirely.
* File lookups are **case-insensitive**: a user should be able to do `/mnt/foo/bar/BAR.ads` or `/mnt/FOO/BAR/bar.ads` interchangeably.
* If the source directory contains existing subdirectories (e.g. `legacy/`, `old/`, `subproj/`), those folders are **preserved** at the root of the mount. Inside each such folder, the same GNAT‐crunch→package logic is applied recursively.

Your job is to implement that FUSE layer, and then verify its behavior by writing a suite of tests in Python (e.g. using pytest) that automatically mount the FS against various “fixtures” directories and check that the visible hierarchy and file contents match expectations. Below is a complete breakdown of every scenario (test case) you must support, followed by guidance on how to organize the tests and what to assert.

---

## 2. Mapping Rules and Core Behavior

1. **Filename → Package Mapping**

   * A GNAT‐crunched filename has the form `<basename>-<hash>.<ext>`, where `<ext>` is `ads` for spec or `adb` for body.
   * Strip off the trailing `-<hash>` and convert the remaining `<basename>`:

     * Replace `_dot_` with a directory separator.
     * Uppercase each identifier.
     * The final component on each path becomes the visible file name (with extension), also uppercased.
   * Examples:

     * `a‐2adb2f.ads` → package `A`, spec file → `/mnt/A/A.ads`
     * `outer_dot_inner‐b1b2b3.ads` → `/mnt/OUTER/INNER/INNER.ads`

2. **Directory Structure**

   * **Top‐level**: identify every distinct “package root” from the set of `.ads`/`.adb` files and create a directory per package.
   * **Nested packages**: if a filename contains `_dot_`, build a subdirectory chain.
   * If you detect both a `.ads` and `.adb` for the same package (same `<basename>`), expose both inside that package’s directory. If only one exists, expose only that one.

3. **Preserving Existing Subdirectories**

   * If the source directory has a real folder (e.g. `legacy/`), **do not merge its contents with the top level**. Instead:

     * Show `legacy/` as a real directory under `/mnt/`.
     * Inside `legacy/`, apply all mapping rules again, just as if it were the top level.
     * Hide any non‐Ada files inside `legacy/` in the same way.

4. **Hiding Non‐Ada Files (“Noise”)**

   * At any level (top or nested), don’t show `.ali`, `.o`, backups (`*.ads~`, `*.adb~`), `README.txt`, or any file whose extension is not `.ads` or `.adb`.

5. **Read-Only Semantics**

   * All file‐system operations that attempt to modify content (create files/dirs, delete, rename, write, chmod, etc.) must return a standard read‐only error (EPERM or EROFS).
   * Reading, listing, and stat’ing existing files should succeed.

6. **Case-Insensitivity**

   * Users may supply any mixture of uppercase/lowercase when traversing directories or opening a file. Internally normalize names to uppercase when mapping to the real underlying GNAT filename(s).
   * Directory listings (e.g. `os.listdir("/mnt/")`) should return names in uppercase. Users can still type `/mnt/foo/BAR.ads` and it should work.

7. **Collision / Ambiguity Handling**

   * If two different GNAT files would map to the same virtual path (e.g. `x‐1111.ads` and `x‐2222.ads` both → `/mnt/X/X.ads`), you have three choices, but you must pick one and document it in your README:

     1. **Refuse to mount** (error: “Ambiguous spec for package X”).
     2. **Pick the newest by modification timestamp** and silently ignore the other (but log a warning).
     3. **Disambiguate by renaming** in the virtual FS (e.g. `X__1111.ads` and `X__2222.ads`).

   * Similarly, if two distinct files end up mapping to the same package body (both want `X.adb`), you must handle it consistently (preferably refuse to mount or disambiguate).

   * Document whichever approach you choose as “Collision Behavior” in the README.

---

## 3. Comprehensive Test Cases

Below are ten (plus one) explicit “fixtures → expected view” scenarios. For each case, you will create a small directory under `tests/fixtures/caseN/` containing exactly the on‐disk GNAT files (and subfolders where indicated). Then, write pytest functions that:

* Launch your FUSE process pointing at that fixture directory and a fresh mount point.
* Wait briefly (e.g. 0.5 seconds) to let it finish mounting.
* Perform the checks listed.
* Unmount and clean up.

### Test Case 1: Single Package, Spec + Body

**Fixtures (`tests/fixtures/case1/`):**

```
a-2adb2f.ads
a-2adb2f.adb
```

* Both map to package `A`.

**Expected Virtual FS:**

```
/mnt/
└── A/
    ├── A.ads   ← original a-2adb2f.ads 
    └── A.adb   ← original a-2adb2f.adb
```

**Assertions:**

1. `sorted(os.listdir(mnt)) == ["A"]`
2. `set(os.listdir(mnt+"/A")) == {"A.ads", "A.adb"}`
3. Reading `/mnt/A/A.ads` yields same bytes as `tests/fixtures/case1/a-2adb2f.ads`.
4. Reading `/mnt/A/A.adb` yields same bytes as `…/a-2adb2f.adb`.

---

### Test Case 2: Package With Only Spec (No Body)

**Fixtures (`tests/fixtures/case2/`):**

```
util-1a2b3c.ads
```

* Only a `.ads` file for package `UTIL`.

**Expected Virtual FS:**

```
/mnt/
└── UTIL/
    └── UTIL.ads
```

**Assertions:**

1. `sorted(os.listdir(mnt)) == ["UTIL"]`
2. `os.listdir(mnt+"/UTIL") == ["UTIL.ads"]`
3. Reading the spec file matches the original.
4. Attempting open `/mnt/UTIL/UTIL.adb` → `FileNotFoundError` (ENOENT).

---

### Test Case 3: Nested Child Package

**Fixtures (`tests/fixtures/case3/`):**

```
outer-aaaaaa.ads
outer-aaaaaa.adb
outer_dot_inner-bbbbb1.ads
```

* `OUTER` has spec+body.
* `OUTER.INNER` has only spec.

**Expected Virtual FS:**

```
/mnt/
└── OUTER/
    ├── OUTER.ads
    ├── OUTER.adb
    └── INNER/
        └── INNER.ads
```

**Assertions:**

1. `sorted(os.listdir(mnt)) == ["OUTER"]`
2. `set(os.listdir(mnt+"/OUTER")) == {"OUTER.ads", "OUTER.adb", "INNER"}`
3. `os.listdir(mnt+"/OUTER/INNER") == ["INNER.ads"]`
4. File contents match originals.
5. `/mnt/OUTER/INNER/INNER.adb` → ENOENT.

---

### Test Case 4: Multi-Level (Grandchild)

**Fixtures (`tests/fixtures/case4/`):**

```
pkg-111111.ads
pkg-111111.adb
pkg_dot_sub-222222.ads
pkg_dot_sub-222222.adb
pkg_dot_sub_dot_leaf-333333.ads
```

* `PKG` spec+body
* `PKG.SUB` spec+body
* `PKG.SUB.LEAF` only spec

**Expected Virtual FS:**

```
/mnt/
└── PKG/
    ├── PKG.ads
    ├── PKG.adb
    └── SUB/
        ├── SUB.ads
        ├── SUB.adb
        └── LEAF/
            └── LEAF.ads
```

**Assertions:**

1. `["PKG"]` at root.
2. `["PKG.ads","PKG.adb","SUB"]` under `/mnt/PKG`.
3. `["SUB.ads","SUB.adb","LEAF"]` under `/mnt/PKG/SUB`.
4. `["LEAF.ads"]` under `/mnt/PKG/SUB/LEAF`.
5. Each file’s content matches its fixture.

---

### Test Case 5: Collisions and Ambiguities

#### 5a) Identical Targets for Body Files

**Fixtures (`tests/fixtures/case5a/`):**

```
pkg-aaaaaaaa.ads
pkg-aaaaaaaa.adb
pkg-aaaaaaaa.adb    ← duplicate filename
```

* Two files claim to map to `PKG/PKG.adb`.

**Desired Behavior (choose one, document it):**

* Option A: **Refuse to mount** and log “Two files map to PKG/PKG.adb.”
* Option B: **Disambiguate** (e.g. keep `PKG.adb` and expose `PKG_1.adb`).
* Option C: Pick the newest timestamp and ignore the other (log a warning).

**Assertions:**

1. If refusing: process should exit with nonzero or raise an exception about collision.
2. If disambiguating: `os.listdir("/mnt/PKG")` should show two distinct names.
3. If picking newest: ensure only one version appears but a warning is emitted (tests can inspect stderr).

#### 5b) Two Specs for the Same Package

**Fixtures (`tests/fixtures/case5b/`):**

```
x-111111.ads
x-222222.ads
```

* Both map to `X/X.ads`.

**Desired Behavior:** same three options as above.

**Assertions:**

1. Check whether only one spec appears (newest or chosen) or both are disambiguated.
2. If both, names might be `X__111111.ads` and `X__222222.ads` (depending on your scheme).
3. If refusing, ensure mount fails with an “ambiguous spec” error.

---

### Test Case 6: Read-Only Enforcement

We assume the FS is strictly read-only.

**Fixtures (`tests/fixtures/case6/`):**

```
a-aaaaaa.ads
a-aaaaaa.adb
```

**Assertions:**

1. Opening `/mnt/A/NEW.ads` with `os.O_CREAT|os.O_WRONLY` → raises `PermissionError` (errno EPERM).
2. Calling `os.remove("/mnt/A/A.ads")` → raises error (errno EROFS or EPERM).
3. Attempting to rename a file or create a directory `/mnt/A/Dir/` → EPERM.

---

### Test Case 7: Deeply Nested, Long Names

**Fixtures (`tests/fixtures/case7/`):**

```
super_long_pkg_dot_sub_pkg_dot_leaf_pkg-abcdef.ads
```

* Should map to:

  * Package path: `SUPER_LONG_PKG/SUB_PKG/LEAF_PKG/LEAF_PKG.ads`

**Expected Virtual FS:**

```
/mnt/
└── SUPER_LONG_PKG/
    └── SUB_PKG/
        └── LEAF_PKG/
            └── LEAF_PKG.ads
```

**Assertions:**

1. `os.path.isdir("/mnt/SUPER_LONG_PKG/SUB_PKG/LEAF_PKG")` is True.
2. `os.listdir("/mnt/SUPER_LONG_PKG") == ["SUB_PKG"]`, etc.
3. Attempting to walk `/mnt/SUPER_LONG_PKG/SUB/` → ENOENT (no partial matches).
4. File content matches original.

---

### Test Case 8: Mixed-Case and Case-Insensitive Lookups

**Fixtures (`tests/fixtures/case8/`):**

```
Math_dot_Vector-123abc.ads
```

* Should map to `MATH/VECTOR/VECTOR.ads`.

**Expected Virtual FS:**

```
/mnt/
└── MATH/
    └── VECTOR/
        └── VECTOR.ads
```

**Assertions:**

1. `os.listdir("/mnt/") == ["MATH"]`.
2. `os.listdir("/mnt/math/")` (lowercase) also yields `["VECTOR"]`.
3. `os.listdir("/mnt/mAtH/VeCtOr/")` yields `["VECTOR.ads"]`.
4. Opening `/mnt/Math/Vector/vector.ads` works (mixed case).
5. Content matches original.

---

### Test Case 9: Hiding Non-Ada Files (“Noise”)

**Fixtures (`tests/fixtures/case9/`):**

```
a-aaaaaa.ads
a-aaaaaa.adb
a.ali
a.ali~
README.txt
```

* Only the `.ads` and `.adb` should appear.

**Expected Virtual FS:**

```
/mnt/
└── A/
    ├── A.ads
    └── A.adb
```

**Assertions:**

1. `sorted(os.listdir(mnt)) == ["A"]`.
2. Under `/mnt/A/`, only `["A.ads","A.adb"]`.
3. Ensure `"a.ali"`, `"a.ali~"`, `"README.txt"` do not show up anywhere.

---

### Test Case 10: Large Hierarchy (Performance)

**Fixtures (`tests/fixtures/case10/`):**

* Programmatically generate 200 packages: `pkg1-<hash>.ads/adb`, each with 3 subpackages:

  * `pkg1_dot_sub1-<hash>.ads/adb`,
  * `pkg1_dot_sub2-<hash>.ads/adb`,
  * `pkg1_dot_sub3-<hash>.ads/adb`,
    …
    up to `pkg200_dot_sub3-<hash>.ads/adb`.

**Assertions (Performance checks):**
Use a small Python script (in pytest) that:

```python
import os, time

# 1. List root
start = time.time()
root_entries = os.listdir("/mnt/")
t_root = time.time() - start

# 2. List a random subpackage
test_path = "/mnt/PKG150/SUB2/"
start = time.time()
sub_entries = os.listdir(test_path)
t_sub = time.time() - start

# 3. Stat a leaf file
leaf = "/mnt/PKG150/SUB2/SUB2.ads"
start = time.time()
_ = os.stat(leaf)
t_stat = time.time() - start

assert t_root < 1.0, f"Root listing too slow: {t_root}s"
assert t_sub < 0.1, f"Sub listing too slow: {t_sub}s"
assert t_stat < 0.05, f"Stat too slow: {t_stat}s"
```

* Ensure mounting and traversing a deep tree remains responsive.

---

### Test Case 11: Preserving an Existing Nested Codebase Folder

**Fixtures (`tests/fixtures/case11/`):**

```
a-aaaaaa.ads
a-aaaaaa.adb
legacy/                    ← real folder to preserve
│   x-111111.ads
│   x-111111.adb
│   x_dot_y-222222.ads
noise.txt
```

* Top-level Ada package `A` (spec+body).
* A subdirectory `legacy/` containing its own GNAT files:

  * `X/X.ads` + `X/X.adb` from `x-111111.*`
  * `X/Y/Y.ads` from `x_dot_y-222222.ads`.
* A “noise.txt” that should be hidden.

**Expected Virtual FS:**

```
/mnt/
├── A/
│   ├── A.ads
│   └── A.adb
└── legacy/
    ├── X/
    │   ├── X.ads
    │   └── X.adb
    └── Y/
        └── Y.ads
```

* Note: `legacy/` is a real directory preserved as a top-level entry.
* Inside `legacy/`, the same mapping (child package, nested) is applied.
* `noise.txt` is never visible at `/mnt/` or `/mnt/legacy/`.

**Assertions:**

1. `sorted(os.listdir(mnt)) == ["A", "legacy"]`.
2. Under `/mnt/A/`, exactly `["A.ads","A.adb"]`, and file contents match.
3. `/mnt/legacy` exists as a directory.
4. Under `/mnt/legacy/X/`, exactly `["X.ads","X.adb"]`. Content checks.
5. Under `/mnt/legacy/Y/`, exactly `["Y.ads"]`. No `Y.adb`. Content matches.
6. `noise.txt` does not appear at the root or inside `legacy/`.
7. Case-insensitive lookup inside `legacy/` also works (e.g. `/mnt/legacy/x/x.ads`).

---

## 4. Test Suite Organization (pytest Example)

1. **Directory layout**

   ```
   your‐repo/
   ├── adafs.py                  ← your FUSE entrypoint script  
   ├── README.md                 ← documentation you’ll write later  
   ├── tests/  
   │   ├── fixtures/  
   │   │   ├── case1/…  
   │   │   ├── case2/…  
   │   │   ├── …  
   │   │   └── case11/…  
   │   └── test_fs.py  
   └── setup.py (optional)  
   ```

2. **Mount & Unmount Fixtures**

   * Create a pytest fixture `mount_fs(src_dir, tmp_path)` that:

     1. Creates a mount point (`tmp_path/"mnt"`).
     2. Launches `adafs.py src_dir mount_point` as a subprocess.
     3. Sleeps 0.5 seconds for the FUSE layer to become ready.
     4. Yields the string path of the mounted directory.
     5. After the test function, terminates and waits on the subprocess to unmount.

   * Example:

     ```python
     import pytest, subprocess, time, os

     @pytest.fixture
     def mount_fs(tmp_path, request):
         # src_dir is provided via parametrization or by a helper
         src_dir = request.param
         mnt = tmp_path / "mnt"
         mnt.mkdir()
         proc = subprocess.Popen(
             ["python3", "adafs.py", str(src_dir), str(mnt)],
             stdout=subprocess.PIPE,
             stderr=subprocess.PIPE,
         )
         time.sleep(0.5)
         yield str(mnt), proc
         proc.terminate()
         proc.wait()
     ```

3. **Parametrizing Each Test Case**

   * In `test_fs.py`, write one function per “case,” or parametrize a single function with a list of `(case_number, assertions)` tuples.
   * Example for Case 1:

     ```python
     import os, pytest

     @pytest.mark.parametrize("case", ["case1"])
     def test_case1(mount_fs, tmp_path):
         # mount_fs will be parametrized with request.param = tmp_path/"fixtures"/case1
         mnt, proc = mount_fs
         # 1. Check top‐level directory names:
         assert sorted(os.listdir(mnt)) == ["A"]
         # 2. Check contents of /mnt/A/
         a_dir = os.path.join(mnt, "A")
         assert set(os.listdir(a_dir)) == {"A.ads", "A.adb"}
         # 3. Content check
         with open(os.path.join(a_dir, "A.ads"), "rb") as virt, \
              open(os.path.join(str(tmp_path/"fixtures"/"case1"), "a-2adb2f.ads"), "rb") as real:
             assert virt.read() == real.read()
         # 4. Clean up is automatic via fixture teardown
     ```
   * For Case 11, do something similar but check both `A` and `legacy`.

4. **Collision Tests (Case 5a & 5b)**

   * If you decide to refuse mounting on collision, your test should catch an exception or check that the subprocess exit code is nonzero and stderr contains the expected error message.
   * If you choose to disambiguate or pick a timestamp, write tests that inspect the mounted directory’s contents accordingly and validate consistency.

5. **Performance Test (Case 10)**

   * Programmatically generate the large hierarchy under `tests/fixtures/case10/` (you can write a small Python script that creates 200 × 3 × 2 = 1,200 files with random “hash” suffixes).
   * In the pytest function, mount, then run the timing code shown above with asserts on time thresholds.
   * Make sure to guard these performance tests so they don’t run if someone lacks resources (e.g. mark them with `@pytest.mark.slow`).

---

## 5. README.md Guidance

Your README should include:

1. **Project Purpose**

   > “This FUSE‐based filesystem presents a human‐readable Ada package hierarchy from GNAT‐crunched source directories.”

2. **Installation & Dependencies**

   * Requires Python3, `fusepy` (or similar), and FUSE installed on the system.
   * Example:

     ```
     pip install fusepy
     ```

3. **Usage**

   ```
   python3 adafs.py <source_directory> <mount_point>
   ```

   * Once mounted, you can `cd <mount_point>` and see the virtual Ada packages.

4. **Mapping Logic**

   * Outline how `_<name>_<hash>.<ext>` is transformed into a path of uppercased, dot→slash directories, with `.ads`/`.adb` file names.
   * Describe case-insensitive lookup: users can type names in any case.

5. **Existing Subdirectories**

   > “If `<source_directory>` contains any real subdirectory, we preserve it verbatim at the root of the mount. Inside that subdirectory, the same GNAT‐crunched → package‐hierarchy mapping is applied recursively, and non‐Ada files remain hidden.”

6. **Read-Only Behavior**

   > “This filesystem is strictly read-only. All write, create, delete, and rename operations return an error (EPERM/EROFS).”

7. **Collision / Ambiguity Policy**

   * Explain how you handle cases where two GNAT files map to the same virtual path.
   * E.g.:

     > “If two `.ads` for the same package exist, we refuse to mount and print ‘Ambiguous spec for package X.’”
     > OR
     > “We take the file with the newer timestamp and ignore the older.”
   * Provide examples so users know what to expect.

8. **Hidden Files**

   > “Any file that does not end in `.ads` or `.adb` is hidden. Examples: `.ali`, `.o`, `*.ads~`, `README.txt`—none of these appear in the mount.”

9. **Case Insensitivity**

   > “Directory names and file names in the mount are presented in uppercase. However, lookups are case‐insensitive: you can type `foo/bar.ads` or `FOO/BAR.ADS` or `Foo/Bar.Ads` interchangeably.”

10. **Test Suite Overview**

    * Summarize that `tests/` contains 11 fixture cases covering all edge conditions:

      1. Single package (spec+body)
      2. Package with only spec
      3. Child package
      4. Grandchild package
      5. Collision scenarios
      6. Read-only enforcement
      7. Very long nested names
      8. Mixed-case lookups
      9. Hiding noise files
      10. Performance on a large hierarchy
      11. Preserving an existing nested codebase directory (e.g. `legacy/`).
    * Provide instructions on how to run tests:

      ```
      python3 -m unittest discover tests -v
      ```
      To run a single test case:

      ```
      python3 -m unittest tests.test_fs.TestFs.test_case1_single_package -v
      ```

---

## 6. Implementation Checklist

When coding `adafs.py` (or whatever module you choose), ensure you:

1. **Scan Source Directory (Recursively)**

   * At startup, walk the directory tree.
   * For each entry:

     * If it’s a directory: register it as a “preserved” folder (will be exposed at mount root). Recurse inside to find `.ads` & `.adb`.
     * If it’s a file ending with `.ads` or `.adb`: parse the GNAT‐crunched `<basename>`.
   * Build an in‐memory mapping from each virtual path (e.g. `("A","A.ads")`, `("OUTER","INNER","INNER.ads")`) to the real on‐disk filename.

2. **Handle Hidden Files**

   * If a file does not match `*.ads` or `*.adb`, skip it entirely.
   * If you encounter a backup suffix (e.g. `foo.ads~`), treat it the same as hidden.

3. **Collision Detection**

   * While building that mapping, detect if two different real files map to the same virtual path.
   * Apply your chosen policy (reject, pick newest, or disambiguate). If you reject, raise an exception before mounting so the test can catch a nonzero exit.

4. **Fuse Operations**

   * `getattr(path)`: return a directory or file stat based on your in‐memory mapping.
   * `readdir(path, ...)`: list immediate children at that virtual path (directories first, then files). Always return uppercase names.
   * `open(path, flags)`: if attempting to write (flags & O\_WRONLY or flags & O\_CREAT), return EPERM. Otherwise, check if the path exists in mapping; if not, ENOENT.
   * `read(path, size, offset)`: open the mapped real file, read bytes (so the contents in `/mnt/…` match exactly).
   * `mkdir`, `rmdir`, `unlink`, `rename`, etc.: return EROFS or EPERM unconditionally.
   * Normalize incoming lookups by uppercasing each component, so `math/Vector/VECTOR.ads` is treated the same as `MATH/VECTOR/VECTOR.ads`.

5. **Case-Insensitive Directory/Name Matching**

   * Maintain your in‐memory map with uppercase keys.
   * Whenever FUSE asks about a component (e.g. in `readdir` or `getattr`), uppercase the incoming name before matching.

6. **Mount / Unmount**

   * Use `fusepy` (or any Python FUSE binding) to implement a simple, single‐threaded FUSE loop.
   * Ensure you call `fuse.FUSE(your_fs_object, mount_point, foreground=True, ro=True)` so that it’s read‐only.
   * On shutdown (SIGINT), cleanly unmount.

7. **Testing Hooks**

   * Make sure your script is friendly to automated tests:

     * If there’s a collision you refuse to mount, exit with a nonzero code and write an error message to stderr.
     * If mounting succeeds, keep running in the foreground so pytest can test the mount.
     * Use a small delay (`time.sleep(0.5)`) inside tests to allow the mount to become ready.
     * Tests will call `proc.terminate()` and `proc.wait()` to unmount.

---

## 7. Sample pytest Skeleton

Below is a minimal example of how your `tests/test_fs.py` might look. Duplicate this pattern for all 11 cases.

```python
import os
import pytest
import subprocess
import time

# Path to your adafs script
ADA_FS_SCRIPT = "adafs.py"

# Helper to mount and yield the mount point + process
@pytest.fixture
def mount_fs(tmp_path, request):
    src_dir = request.param  # e.g. tmp_path/"fixtures"/"case1"
    mnt = tmp_path / "mnt"
    mnt.mkdir()
    # Launch adafs.py in the foreground, read-only
    proc = subprocess.Popen(
        ["python3", ADA_FS_SCRIPT, str(src_dir), str(mnt)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(0.5)  # wait for mount
    yield str(mnt), proc
    # Teardown: terminate process (which unmounts)
    proc.terminate()
    proc.wait()

# ------------------------
# Case 1: Single Package
# ------------------------
@pytest.mark.parametrize("mount_fs", [os.path.join(os.getcwd(), "tests/fixtures/case1")], indirect=True)
def test_case1_single_package(mount_fs):
    mnt, proc = mount_fs

    # 1. Root should list ["A"]
    assert sorted(os.listdir(mnt)) == ["A"]

    # 2. /mnt/A/ contains A.ads, A.adb
    a_dir = os.path.join(mnt, "A")
    assert set(os.listdir(a_dir)) == {"A.ads", "A.adb"}

    # 3. File contents match
    with open(os.path.join(a_dir, "A.ads"), "rb") as virt, \
         open(os.path.join(os.getcwd(), "tests/fixtures/case1/a-2adb2f.ads"), "rb") as real:
        assert virt.read() == real.read()

    # 4. /mnt/A/A.adb matches as well
    with open(os.path.join(a_dir, "A.adb"), "rb") as virt, \
         open(os.path.join(os.getcwd(), "tests/fixtures/case1/a-2adb2f.adb"), "rb") as real:
        assert virt.read() == real.read()

# ------------------------
# Case 11: Preserving Nested Folder
# ------------------------
@pytest.mark.parametrize("mount_fs", [os.path.join(os.getcwd(), "tests/fixtures/case11")], indirect=True)
def test_case11_preserve_nested(mount_fs):
    mnt, proc = mount_fs

    # 1. Root entries: ["A", "legacy"]
    root_entries = sorted(os.listdir(mnt))
    assert root_entries == ["A", "legacy"]

    # 2. /mnt/A/ has A.ads, A.adb
    a_dir = os.path.join(mnt, "A")
    assert set(os.listdir(a_dir)) == {"A.ads", "A.adb"}
    with open(os.path.join(a_dir, "A.ads"), "rb") as v, \
         open(os.path.join(os.getcwd(), "tests/fixtures/case11/a-aaaaaa.ads"), "rb") as r:
        assert v.read() == r.read()

    # 3. /mnt/legacy is a directory
    legacy_dir = os.path.join(mnt, "legacy")
    assert os.path.isdir(legacy_dir)

    # 4. /mnt/legacy/X/ has X.ads, X.adb
    x_dir = os.path.join(legacy_dir, "X")
    assert set(os.listdir(x_dir)) == {"X.ads", "X.adb"}
    with open(os.path.join(x_dir, "X.ads"), "rb") as v, \
         open(os.path.join(os.getcwd(), "tests/fixtures/case11/legacy/x-111111.ads"), "rb") as r:
        assert v.read() == r.read()

    # 5. /mnt/legacy/Y/ has only Y.ads
    y_dir = os.path.join(legacy_dir, "Y")
    assert os.listdir(y_dir) == ["Y.ads"]
    with open(os.path.join(y_dir, "Y.ads"), "rb") as v, \
         open(os.path.join(os.getcwd(), "tests/fixtures/case11/legacy/x_dot_y-222222.ads"), "rb") as r:
        assert v.read() == r.read()
    with pytest.raises(FileNotFoundError):
        open(os.path.join(y_dir, "Y.adb"), "rb")

    # 6. noise.txt is hidden
    assert "noise.txt" not in os.listdir(mnt)
```

* Repeat similar blocks for Cases 2–10, using parametrization to pass in `tests/fixtures/caseN`.

---

## 8. Final Deliverables

1. **`adafs.py`** (or any name you choose)

   * Implements the FUSE layer exactly as described.
   * Contains clear error messages for collision cases.
   * Honors read-only semantics.

2. **`tests/fixtures/`**

   * `case1/` through `case11/`, each containing the exact on-disk GNAT-crunched files (and nested subfolders for case 11).
   * (For case 10, a small generator script is acceptable, but check in the generated files.)

3. **`tests/test_fs.py`** (unittest suite)

   * Covers all scenarios with assertions as detailed.
   * Ensures performance metrics for case 10.

4. **`README.md`**

   * Explains: installation, usage, mapping rules, read-only behavior, collisions/dedup policy, hidden files, preserving subdirectories, case insensitivity.
   * Brief summary of the 11 test cases and how to run them (`python3 -m unittest discover tests -v`).

---

### Success Criteria

* **All 11 test cases pass** without failing assertions or false positives.
* The FUSE process never modifies the original files or directories.
* Attempts to write into `/mnt/…` properly return permission errors.
* Case-insensitive lookups always succeed.
* Your README is clear enough for any new developer (or AI agent) to understand the mapping logic and how to run tests.

With these instructions, a coder AI agent has everything needed to build, test, and document the FUSE‐based Ada package viewer. Good luck!

