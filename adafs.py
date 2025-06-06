import os
import sys
import errno
from fuse import FUSE, FuseOSError, Operations

class AdaFS(Operations):
    def __init__(self, root):
        self.root = root
        self.files = {}
        self.directories = {}
        self._build_filesystem()

    def _build_filesystem(self):
        for dirpath, dirnames, filenames in os.walk(self.root):
            for filename in filenames:
                if filename.endswith(('.ads', '.adb')):
                    virtual_path = self._map_to_virtual_path(dirpath, filename)
                    self.files[virtual_path] = os.path.join(dirpath, filename)
                    dir_path = os.path.dirname(virtual_path)
                    if dir_path not in self.directories:
                        self.directories[dir_path] = set()
                    self.directories[dir_path].add(virtual_path)

    def _map_to_virtual_path(self, dirpath, filename):
        basename, ext = os.path.splitext(filename)
        package_name = basename.split('-')[0].replace('_dot_', '/').upper()
        return os.path.join('/', package_name, package_name + ext.upper())

    def getattr(self, path, fh=None):
        if path in self.files:
            st = os.lstat(self.files[path])
            return dict((key, getattr(st, key)) for key in ('st_atime', 'st_ctime', 'st_gid', 'st_mode', 'st_mtime', 'st_nlink', 'st_size', 'st_uid'))
        elif path in self.directories:
            return dict(st_mode=(os.stat.S_IFDIR | 0o755), st_nlink=2)
        else:
            raise FuseOSError(errno.ENOENT)

    def readdir(self, path, fh):
        if path == '/':
            return ['.', '..'] + [d.split('/')[1] for d in self.directories.keys()]
        else:
            dir_path = path.rstrip('/')
            if dir_path in self.directories:
                return ['.', '..'] + [os.path.basename(f) for f in self.directories[dir_path]]
            else:
                return ['.', '..']

    def open(self, path, flags):
        if path not in self.files:
            raise FuseOSError(errno.ENOENT)
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT):
            raise FuseOSError(errno.EROFS)
        return os.open(self.files[path], flags)

    def read(self, path, size, offset, fh):
        os.lseek(fh, offset, os.SEEK_SET)
        return os.read(fh, size)

    def mkdir(self, path, mode):
        raise FuseOSError(errno.EROFS)

    def rmdir(self, path):
        raise FuseOSError(errno.EROFS)

    def unlink(self, path):
        raise FuseOSError(errno.EROFS)

    def rename(self, old, new):
        raise FuseOSError(errno.EROFS)

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print('usage: %s <source> <mountpoint>' % sys.argv[0])
        sys.exit(1)

    source = sys.argv[1]
    mountpoint = sys.argv[2]

    FUSE(AdaFS(source), mountpoint, nothreads=True, foreground=True, ro=True)
