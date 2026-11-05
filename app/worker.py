import asyncio
import os
import sys

from arq.connections import RedisSettings

# This process stays up around the clock and is billed for the memory it holds,
# so it must stay small: never import the pipeline (litellm, pymupdf4llm, ...)
# here. Each job runs in a child process instead -- see app/ingest_job.py.

REDIS = RedisSettings.from_dsn(
    os.environ.get("REDIS_URL", "redis://localhost:6379")
)

JOB_TIMEOUT = 900

# Exit code for "the job failed, and the document already says why".
FAILURE_RECORDED = 3


def _job_command(*args: str) -> list[str]:
    return [sys.executable, "-m", "app.ingest_job", *args]


async def _run_child(*args: str, timeout: float | None = None) -> int:
    proc = await asyncio.create_subprocess_exec(*_job_command(*args))
    try:
        return await asyncio.wait_for(proc.wait(), timeout)
    finally:
        # Reached with the child still running on a timeout, or when arq
        # cancels the job at shutdown (arq then re-queues it).
        if proc.returncode is None:
            proc.kill()
            await proc.wait()


async def _record_failure(document_id: str, uid: str, message: str):
    """Mark the document failed for a child that could not do so itself."""
    code = await _run_child("--mark-failed", document_id, uid, message)
    if code != 0:
        print(f"worker: could not mark {document_id} failed (exit code {code})")


async def ingest_document(ctx, document_id: str, uid: str):
    try:
        code = await _run_child(document_id, uid, timeout=JOB_TIMEOUT)
    except TimeoutError:
        await _record_failure(
            document_id, uid,
            f"Ingestion failed: it took longer than {JOB_TIMEOUT // 60} minutes.",
        )
        raise

    if code == 0:
        return
    # Anything else died before it could record a reason: out of memory, a
    # crash, or an error before the pipeline started. Without this the document
    # would sit in "processing" forever.
    if code != FAILURE_RECORDED:
        await _record_failure(
            document_id, uid, "Ingestion failed: the job stopped unexpectedly.",
        )
    raise RuntimeError(f"ingestion of {document_id} failed (exit code {code})")


async def hello(ctx, name: str):
    print(f"worker: starting job for {name}")
    await asyncio.sleep(5)
    print(f"worker: done with {name}")
    return f"hello {name}"

class WorkerSettings:
    functions = [ingest_document, hello]
    redis_settings = REDIS
    max_jobs = 2
    # A backstop only: leaves ingest_document time to stop a child that hits
    # JOB_TIMEOUT and record the failure before arq cancels it.
    job_timeout = JOB_TIMEOUT + 60
