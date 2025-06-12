#!/bin/env python

import os
import sys
import argparse
import shutil
import logging
import re
from typing import Optional

logging.basicConfig(level=logging.DEBUG)



def _find_package_in_string(source_code: str) -> Optional[str]:
    """Helper function to find a package name within a source string."""
    # Regex to find the package declaration and capture the full name.
    package_regex = r"^\s*(?:private\s+)?package(?:\s+body)?\s+([a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)*)"
    match = re.search(package_regex, source_code, re.MULTILINE | re.IGNORECASE)
    return match.group(1) if match else None

def _find_procs_or_funcs_in_string(source_code: str) -> Optional[str]:
    """
    Helper function to find all top-level procedures or functions in a source string.

    This function scans the code line by line, tracking nesting levels to
    differentiate between top-level and nested entities. If multiple top-level
    entities are found, their names are concatenated with ' AND '.
    """
    top_level_entities = []
    nesting_level = 0

    # Regex to find any procedure or function declaration.
    decl_re = re.compile(r"^\s*(procedure|function)\s+([a-zA-Z_]\w*)", re.IGNORECASE)
    # Regex to find keywords that reliably start a new block/scope.
    # We look for a declaration followed by 'is' on the same line.
    block_start_re = re.compile(r"^\s*(package|procedure|function|task|protected)\b.*\bis\b", re.IGNORECASE)
    # Regex to find the 'end' keyword that closes a block.
    block_end_re = re.compile(r"^\s*end\b", re.IGNORECASE)

    for line in source_code.splitlines():
        # Remove comments to avoid accidentally matching keywords inside them.
        clean_line = line.split('--')[0]

        # First, check for a new declaration at the CURRENT nesting level.
        # This must be done before updating the level.
        match = decl_re.match(clean_line)
        if match and nesting_level == 0:
            # If we're at the top level (not nested), this is a top-level entity.
            entity_name = match.group(2)
            top_level_entities.append(entity_name)
        
        # Second, update the nesting level for the next line.
        # A line with 'procedure ... is', 'package ... is', etc., increases nesting.
        if block_start_re.search(clean_line):
            nesting_level += 1
        # A line starting with 'end' decreases nesting.
        elif block_end_re.search(clean_line):
            if nesting_level > 0:
                nesting_level -= 1

    if not top_level_entities:
        return None
        
    if len(top_level_entities) == 1:
        return top_level_entities[0]
    else:
        # FIXME this should raise exception (not expected)
        return top_level_entities[0] # only keep first one for now

def get_ada_entity_name(file_path: str) -> Optional[str]:
    """
    Extracts the primary entity name(s) from an Ada source file.

    This function first searches for a package declaration. If none is found, 
    it then searches for top-level procedure or function declarations.

    Args:
        file_path: The path to the Ada source file.

    Returns:
        The full package name, the procedure/function name(s), or None
        if no primary entity is found or the file cannot be read.
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            source_code = f.read()
    except FileNotFoundError:
        print(f"Error: File not found at '{file_path}'")
        return None
    except Exception as e:
        print(f"Error reading file '{file_path}': {e}")
        return None

    # First, attempt to find a package name.
    package_name = _find_package_in_string(source_code)
    if package_name:
        return package_name

    # If no package, attempt to find procedure(s) or function(s).
    return _find_procs_or_funcs_in_string(source_code)



def get_ada_full_package_name(file_path: str) -> str | None:
    """
    Extracts the full package name from an Ada source file.

    This function reads an Ada source file (.ads or .adb), uses a regular
    expression to find the package declaration, and returns the full,
    dot-separated package name. For example, for "A.B.C", it returns "A.B.C".

    Args:
        file_path: The path to the Ada source file.

    Returns:
        The full package name as a string, or None if no package
        declaration is found or the file cannot be read.
    """
    # Regex to find the package declaration and capture the full name.
    #
    # Breakdown:
    # ^                  - Matches the start of a new line (due to re.MULTILINE).
    # \s* - Matches any leading whitespace.
    # package            - Matches the keyword 'package' (case-insensitive).
    # (?:\s+body)?       - An optional non-capturing group for 'body'.
    # \s+                - Matches the space(s) after 'package' or 'body'.
    # ( ... )            - The capturing group for the full package name:
    #   [a-zA-Z_]\w* - Matches the first identifier (e.g., "Ada").
    #   (?:\.[a-zA-Z_]\w*)* - A non-capturing group that matches zero or more
    #                         occurrences of a dot followed by an identifier
    #                         (e.g., ".Strings", ".Unbounded").
    #
    package_regex = r"^\s*package(?:\s+body)?\s+([a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)*)"

    try:
        # Open and read the file. Using 'errors=ignore' for robustness.
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            source_code = f.read()
    except FileNotFoundError:
        # Handle cases where the file does not exist.
        print(f"Error: File not found at '{file_path}'")
        return None
    except Exception as e:
        # Handle other potential I/O errors.
        print(f"Error reading file '{file_path}': {e}")
        return None

    # Search the source code using the regex.
    # re.MULTILINE (or re.M) allows '^' to match the start of each line.
    # re.IGNORECASE (or re.I) makes matching case-insensitive.
    match = re.search(package_regex, source_code, re.MULTILINE | re.IGNORECASE)

    if match:
        # The first captured group (group(1)) is our full package name.
        return match.group(1)

    # Return None if no match was found.
    return None

def map_to_virtual(src_root, path):
    """Return the virtual path for a single GNAT-crunched file."""
    rel = os.path.relpath(path, src_root)
    dirs, fname = os.path.split(rel)
    base, ext = os.path.splitext(fname)

    logging.debug("-----")
    logging.debug("src_root %s - path %s", src_root, path)
    logging.debug("rel %s - dirs %s - fname %s", path, dirs, fname)
    package = get_ada_entity_name(path)
    logging.debug("path %s", path)
    logging.debug("package %s", package)
    if not package:
        package = base + "KNUNCHED"
    file_name = package + ext.lower()
    return os.path.join(dirs, file_name)


def build_view(src_root, mount_root):
    """Create a plain directory hierarchy representing the virtual FS."""
    created_dirs = set()
    for root, _, files in os.walk(src_root):
        rel_dir = os.path.relpath(root, src_root)
        target_dir = os.path.join(mount_root, rel_dir) if rel_dir != '.' else mount_root
        os.makedirs(target_dir, exist_ok=True)
        created_dirs.add(target_dir)
        for f in files:
            if not (f.endswith('.ads') or f.endswith('.adb')):
                continue
            src_file = os.path.join(root, f)
            virt = map_to_virtual(src_root, src_file)
            dest = os.path.join(mount_root, virt)
            dest_dir = os.path.dirname(dest)
            if dest_dir not in created_dirs:
                os.makedirs(dest_dir, exist_ok=True)
                created_dirs.add(dest_dir)
            if not os.path.exists(dest):
                # Use absolute symlinks so later directory moves don't break
                # the references when running post-processing passes.
                os.symlink(os.path.abspath(src_file), dest)

    # Make all created directories read-only to mimic a read-only mount
    for d in sorted(created_dirs, key=len, reverse=True):
        try:
            os.chmod(d, 0o755)
        except OSError:
            pass


def _categorize_dir(path: str, pkg_prefix: str) -> None:
    entries = os.listdir(path)
    subdirs = [d for d in entries if os.path.isdir(os.path.join(path, d))]
    for d in subdirs:
        _categorize_dir(os.path.join(path, d), f"{pkg_prefix}.{d}")

    has_spec = os.path.isfile(os.path.join(path, os.path.basename(path) + ".ads"))
    has_body = os.path.isfile(os.path.join(path, os.path.basename(path) + ".adb"))
    if subdirs and (has_spec or has_body):
        parent = os.path.dirname(path)
        group_dir = os.path.join(parent, pkg_prefix)
        if os.path.abspath(group_dir) != os.path.abspath(path):
            os.makedirs(group_dir, exist_ok=True)
            try:
                shutil.move(path, os.path.join(group_dir, os.path.basename(path)))
            except (OSError, shutil.Error) as e:
                print(f"Error moving {path} to {os.path.join(group_dir, os.path.basename(path))}: {e}", file=sys.stderr)
                # Optionally, re-raise the exception or handle it as needed


def categorize_directory(root: str) -> None:
    for name in os.listdir(root):
        p = os.path.join(root, name)
        if os.path.isdir(p):
            _categorize_dir(p, name)


def print_tree(path: str) -> None:
    """Print directory tree of path if the `tree` command exists."""

    tree_bin = shutil.which("tree")
    if tree_bin:
        import subprocess
        subprocess.run([tree_bin, path], check=False)

def main():
    argv = sys.argv[1:]

    parser = argparse.ArgumentParser(description="Simulate Ada FUSE view")
    parser.add_argument("command", choices=["unmount", "mount", "test"])
    parser.add_argument("source")
    parser.add_argument("mountpoint", nargs="?")
    args = parser.parse_args(argv)

    command = args.command

    mountpoint = args.mountpoint
    if mountpoint is None:
        mountpoint = args.source.rstrip(os.sep) + ".fuse"
        print("Mount dir not given, using : ", mountpoint)

    if command in [ "mount", "test"]:
        build_view(args.source, mountpoint)
        categorize_directory(mountpoint)

    if command == "test":
        print_tree(mountpoint)

    if command in [ "unmount", "test" ]:
        if os.path.isdir(mountpoint):
            shutil.rmtree(mountpoint)



if __name__ == "__main__":
    main()
