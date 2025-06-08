import os
import errno
import argparse
import stat

from fuse import FUSE, FuseOSError, Operations, LoggingMixIn

from adafs import map_to_virtual


class AdaFuse(LoggingMixIn, Operations):
    """FUSE filesystem exposing a clean Ada package hierarchy."""

    def __init__(self, src_root: str):
        self.src_root = os.path.abspath(src_root)
        self._map = {}
        self._dirs = set()
        self._build()

    def _build(self) -> None:
        self._dirs.add("")
        for root, dirs, files in os.walk(self.src_root):
            for d in dirs:
                rel = os.path.relpath(os.path.join(root, d), self.src_root)
                self._add_dir(rel)
            for f in files:
                if not (f.endswith('.ads') or f.endswith('.adb')):
                    continue
                real = os.path.join(root, f)
                virt = map_to_virtual(self.src_root, real)
                virt = virt.replace(os.sep, '/').upper()
                self._map[virt] = real
                self._add_dir(os.path.dirname(virt))

    def _add_dir(self, path: str) -> None:
        path = self._normalize_path(path)
        while True:
            if path not in self._dirs:
                self._dirs.add(path)
            if path == '':
                break
            path = os.path.dirname(path)

    def _lookup(self, path: str) -> str:
        return path.lstrip('/').replace(os.sep, '/').upper()

    # Filesystem methods
    # ------------------
    def getattr(self, path, fh=None):
        key = self._lookup(path)
        if key == '' or key in self._dirs:
            return {
                'st_mode': stat.S_IFDIR | 0o555,
                'st_nlink': 2,
            }
        real = self._map.get(key)
        if real:
            st = os.lstat(real)
            return {
                'st_mode': stat.S_IFREG | 0o444,
                'st_nlink': 1,
                'st_size': st.st_size,
                'st_mtime': st.st_mtime,
                'st_ctime': st.st_ctime,
                'st_atime': st.st_atime,
            }
        raise FuseOSError(errno.ENOENT)

    def readdir(self, path, fh):
        key = self._lookup(path)
        entries = {'.', '..'}
        prefix = key + '/' if key else ''
        for d in self._dirs:
            if d.startswith(prefix) and d != key:
                rest = d[len(prefix):]
                if '/' not in rest:
                    entries.add(rest)
        for virt in self._map:
            if virt.startswith(prefix):
                rest = virt[len(prefix):]
                if '/' not in rest:
                    entries.add(os.path.basename(rest))
        return list(sorted(entries))

    def open(self, path, flags):
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_APPEND):
            raise FuseOSError(errno.EROFS)
        key = self._lookup(path)
        real = self._map.get(key)
        if real is None:
            raise FuseOSError(errno.ENOENT)
        return os.open(real, os.O_RDONLY)

    def read(self, path, size, offset, fh):
        os.lseek(fh, offset, os.SEEK_SET)
        return os.read(fh, size)


def main():
    parser = argparse.ArgumentParser(description="Ada package viewer (FUSE)")
    parser.add_argument('source', help='source directory with GNAT-crunched files')
    parser.add_argument('mountpoint', help='mount point')
    parser.add_argument('-f', '--foreground', action='store_true', help='run in foreground')
    args = parser.parse_args()

    fuse = FUSE(AdaFuse(args.source), args.mountpoint,
                foreground=args.foreground, ro=True, nothreads=True)


if __name__ == '__main__':
    main()
