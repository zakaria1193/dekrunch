# Ada Virtual Filesystem

This project exposes a read-only, human-readable Ada package hierarchy from GNAT-crunched source directories using a small Python script.

## Mapping rules

- The tree follow the same tree as the original repo

## Existing subdirectories

Any real subdirectory under the source tree is preserved verbatim at the root of the mount. Inside such directories the same mapping rules apply.

## Collision behaviour

If multiple GNAT files map to the same virtual path, the script keeps the first one it encounters and ignores the rest.
FIXME this should be fixed

## Hidden files

Files that do not end in `.ads` or `.adb` (e.g. `.ali`, `.o`, `*.ads~`, `README.txt`) are hidden from the mount.

## Test suite

The `tests/` folder contains unit tests for eleven scenarios:

1. Single package (spec and body)
2. Package with only spec
3. Child package
4. Grandchild package
5. Collision scenarios
6. Read-only enforcement
7. Very long nested names
8. Mixed-case lookups
9. Hiding noise files
10. Performance on a large hierarchy
11. Preserving an existing nested directory

Run all tests with:

```bash
python3 -m unittest discover tests -v
```

Or run an individual test, for example:

```bash
python3 -m unittest tests.test_fs.TestFs.test_case1_single_package -v
```
