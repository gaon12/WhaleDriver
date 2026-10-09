import os
import subprocess
import sys
import time

import psutil
import pytest

from whaledriver._process_job import ProcessJob


@pytest.mark.skipif(os.name != "nt", reason="Windows Job Object regression test")
def test_job_closes_late_descendants_without_stopping_an_unrelated_process(tmp_path):
    child_pid = tmp_path / "child-pid.txt"
    child_script = (
        "import pathlib, subprocess, sys, time; time.sleep(0.2); "
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
        "pathlib.Path(sys.argv[1]).write_text(str(child.pid)); time.sleep(60)"
    )
    unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    parent = subprocess.Popen([sys.executable, "-c", child_script, str(child_pid)])
    job = ProcessJob()
    try:
        job.assign(parent)
        deadline = time.monotonic() + 5
        while not child_pid.is_file() and time.monotonic() < deadline:
            time.sleep(0.05)
        descendant = psutil.Process(int(child_pid.read_text()))
        job.close()
        parent.wait(timeout=5)
        assert not psutil.wait_procs([descendant], timeout=5)[1]
        assert unrelated.poll() is None
    finally:
        job.close()
        for process in (parent, unrelated):
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
