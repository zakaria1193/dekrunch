import os
import sys
import argparse
import shutil
import time


def map_to_virtual(src_root, path):
    """Return the virtual path for a single GNAT-crunched file."""
    rel = os.path.relpath(path, src_root)
    dirs, fname = os.path.split(rel)
    base, ext = os.path.splitext(fname)
    if '-' in base:
        base = base.split('-')[0]
    package = base.replace('_dot_', '/').upper()
    components = package.split('/')
    file_name = components[-1] + ext.lower()
    return os.path.join(dirs, *components[:-1], components[-1], file_name)


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
                os.symlink(os.path.relpath(src_file, dest_dir), dest)

    # Make all created directories read-only to mimic a read-only mount
    for d in sorted(created_dirs, key=len, reverse=True):
        try:
            os.chmod(d, 0o555)
        except OSError:
            pass


def main():
    argv = sys.argv[1:]

    parser = argparse.ArgumentParser(description="Simulate Ada FUSE view")
    parser.add_argument("command", choices=["unmount", "mount"])
    parser.add_argument("source")
    parser.add_argument("mountpoint", nargs="?")
    args = parser.parse_args(argv)

    command = args.command

    mountpoint = args.mountpoint
    if mountpoint is None:
        mountpoint = args.source.rstrip(os.sep) + ".fuse"
        print("Mount dir not given, using : ", mountpoint)

    if command == "mount":
        build_view(args.source, mountpoint)
    else:
        if os.path.isdir(mountpoint):
            shutil.rmtree(mountpoint)


if __name__ == "__main__":
    main()
