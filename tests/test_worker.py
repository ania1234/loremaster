import asyncio
import os
import subprocess
import sys
import time

import pytest

from app import worker

DOC = "11111111-1111-1111-1111-111111111111"
USER = "22222222-2222-2222-2222-222222222222"


@pytest.fixture
def child(monkeypatch):
    """Replace the real job with a small script; returns the failures recorded."""
    recorded = []

    async def record(document_id, uid, message):
        recorded.append((document_id, uid, message))

    monkeypatch.setattr(worker, "_record_failure", record)

    def use(script):
        monkeypatch.setattr(
            worker, "_job_command", lambda *args: [sys.executable, "-c", script]
        )
        return recorded

    return use


def _run_job():
    return worker.ingest_document({}, DOC, USER)


def _is_running(pid: int) -> bool:
    # A killed child is reaped by _run_child, so its pid stops existing.
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def _sleeper(pid_file):
    return (
        f"import os, time; open({str(pid_file)!r}, 'w').write(str(os.getpid())); "
        "time.sleep(60)"
    )


def test_worker_does_not_load_the_pipeline():
    """The whole point of the split: this process is billed for idle memory."""
    code = (
        "import sys, app.worker; "
        "heavy = {'litellm', 'pymupdf', 'pymupdf4llm', 'onnxruntime', 'sqlalchemy'}; "
        "print(', '.join(sorted(heavy & set(sys.modules))))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == ""


def test_success_records_nothing(child):
    recorded = child("raise SystemExit(0)")
    asyncio.run(_run_job())
    assert recorded == []


def test_failure_the_child_recorded_keeps_its_message(child):
    recorded = child(f"raise SystemExit({worker.FAILURE_RECORDED})")
    with pytest.raises(RuntimeError):
        asyncio.run(_run_job())
    assert recorded == []


def test_crash_is_recorded_for_the_child(child):
    recorded = child("raise SystemExit(1)")
    with pytest.raises(RuntimeError):
        asyncio.run(_run_job())
    assert [r[:2] for r in recorded] == [(DOC, USER)]
    assert "stopped unexpectedly" in recorded[0][2]


def test_killed_child_is_recorded(child):
    # What the out-of-memory killer looks like from here.
    recorded = child("import os, signal; os.kill(os.getpid(), signal.SIGKILL)")
    with pytest.raises(RuntimeError):
        asyncio.run(_run_job())
    assert "stopped unexpectedly" in recorded[0][2]


def test_timeout_kills_the_child_and_records_it(child, monkeypatch, tmp_path):
    pid_file = tmp_path / "pid"
    recorded = child(_sleeper(pid_file))
    monkeypatch.setattr(worker, "JOB_TIMEOUT", 1)

    with pytest.raises(TimeoutError):
        asyncio.run(_run_job())

    assert not _is_running(int(pid_file.read_text()))
    assert "took longer" in recorded[0][2]


def test_cancelling_kills_the_child_without_recording(child, tmp_path):
    """arq cancels jobs at shutdown and re-queues them, so this isn't a failure."""
    pid_file = tmp_path / "pid"
    recorded = child(_sleeper(pid_file))

    async def scenario():
        task = asyncio.create_task(_run_job())
        deadline = time.monotonic() + 10
        while not (pid_file.exists() and pid_file.read_text()):
            assert time.monotonic() < deadline
            await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
    assert not _is_running(int(pid_file.read_text()))
    assert recorded == []


def test_arq_gives_the_job_time_to_record_a_timeout():
    assert worker.WorkerSettings.job_timeout > worker.JOB_TIMEOUT
