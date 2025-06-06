import os
import pytest
import subprocess
import time

ADA_FS_SCRIPT = "adafs.py"

@pytest.fixture
def mount_fs(tmp_path, request):
    src_dir = request.param
    mnt = tmp_path / "mnt"
    mnt.mkdir()
    proc = subprocess.Popen(
        ["python3", ADA_FS_SCRIPT, str(src_dir), str(mnt)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(0.5)
    yield str(mnt), proc
    proc.terminate()
    proc.wait()

@pytest.mark.parametrize("mount_fs", [os.path.join(os.getcwd(), "tests/fixtures/case1")], indirect=True)
def test_case1_single_package(mount_fs):
    mnt, proc = mount_fs
    assert sorted(os.listdir(mnt)) == ["A"]
    a_dir = os.path.join(mnt, "A")
    assert set(os.listdir(a_dir)) == {"A.ads", "A.adb"}
    with open(os.path.join(a_dir, "A.ads"), "rb") as virt, \
         open(os.path.join(os.getcwd(), "tests/fixtures/case1/a-2adb2f.ads"), "rb") as real:
        assert virt.read() == real.read()
    with open(os.path.join(a_dir, "A.adb"), "rb") as virt, \
         open(os.path.join(os.getcwd(), "tests/fixtures/case1/a-2adb2f.adb"), "rb") as real:
        assert virt.read() == real.read()
