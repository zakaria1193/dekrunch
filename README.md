# Ada Virtual Filesystem

This project exposes a read-only, human-readable Ada package hierarchy from GNAT-crunched source directories using a small Python script.

## Installation

You will need Python 3 and `fusepy` with FUSE available on your system:


## Usage

```bash
python3 adafs.py <source_directory> <mount_point>
```

The mount point will contain uppercased package directories. Packages that
contain nested packages are automatically moved under directories named after
their fully qualified prefix, creating a cleaner hierarchy without requiring any
additional commands.

## Mapping rules

- Filenames follow `<basename>-<hash>.<ext>` where `<ext>` is `.ads` or `.adb`.
- `_dot_` within `<basename>` becomes a subdirectory separator.
- All components are uppercased; the last component forms the Ada source filename (e.g. `A.ads`).
- Lookups are case-insensitive so `foo/bar.ads` is the same as `FOO/BAR.ads`.

## Existing subdirectories

Any real subdirectory under the source tree is preserved verbatim at the root of the mount. Inside such directories the same mapping rules apply.

## Read-only behaviour

The filesystem is strictly read-only. Create, delete or rename operations return `EPERM` or `EROFS`.

## Collision behaviour

If multiple GNAT files map to the same virtual path, the script keeps the first one it encounters and ignores the rest.

## Hidden files

Files that do not end in `.ads` or `.adb` (e.g. `.ali`, `.o`, `*.ads~`, `README.txt`) are hidden from the mount.

## Case insensitivity

Although directory and file names appear in uppercase, lookups accept any casing.

## 

suite

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
