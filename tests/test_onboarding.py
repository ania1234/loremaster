import uuid
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from dotenv import load_dotenv

load_dotenv()

from app import onboarding  # noqa: E402 - app.storage reads env at import

USER = uuid.UUID("11111111-1111-1111-1111-111111111111")
SAMPLES = uuid.UUID("22222222-2222-2222-2222-222222222222")


class FakeDB:
    """Just enough of a Session for copy_samples; no database involved."""

    def __init__(self, owned_hashes=(), fail_insert=False):
        self.owned_hashes = list(owned_hashes)
        self.fail_insert = fail_insert
        self.added = []
        self.inserted_chunks = []

    def scalars(self, query):
        return self.owned_hashes

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        pass

    def execute(self, statement, rows):
        if self.fail_insert:
            raise RuntimeError("insert failed")
        self.inserted_chunks.extend(rows)


def _sample(file_hash):
    doc = {c: None for c in onboarding.DOCUMENT_COLUMNS}
    doc.update(title=f"doc {file_hash}", doc_type="ruleset",
               file_hash=file_hash, storage_path=f"{SAMPLES}/{file_hash}.pdf")
    chunk = {c: None for c in onboarding.CHUNK_COLUMNS}
    chunk.update(ordinal=0, content="text", token_count=1)
    return doc, [chunk]


@pytest.fixture
def env(monkeypatch):
    """Patch out the DB and storage; returns the pieces a test inspects."""
    state = SimpleNamespace(
        db=FakeDB(),
        profile=SimpleNamespace(onboarded_at=None),
        samples=[_sample("a"), _sample("b")],
        copied=[],
        deleted=[],
    )

    @contextmanager
    def fake_session(user_id):
        yield state.db

    def fake_copy(src, dst):
        state.copied.append((src, dst))
        return dst

    monkeypatch.setattr(onboarding.settings, "sample_user_id", SAMPLES)
    monkeypatch.setattr(onboarding, "session_for_user", fake_session)
    monkeypatch.setattr(onboarding, "get_or_create_profile",
                        lambda db, uid, lock=False: state.profile)
    monkeypatch.setattr(onboarding, "_read_samples", lambda: state.samples)
    monkeypatch.setattr(onboarding, "copy_object", fake_copy)
    monkeypatch.setattr(onboarding, "delete_object", state.deleted.append)
    return state


def test_copies_every_sample_and_marks_onboarded(env):
    ids = onboarding.copy_samples(USER)

    assert len(ids) == 2
    # Each copy gets its own file at the path the download endpoint expects.
    assert [dst for _, dst in env.copied] == [f"{USER}/{i}.pdf" for i in ids]
    assert all(d.user_id == USER and d.status == "ready" for d in env.db.added)
    assert {c["document_id"] for c in env.db.inserted_chunks} == set(ids)
    assert all(c["user_id"] == USER for c in env.db.inserted_chunks)
    assert env.profile.onboarded_at is not None


def test_skips_a_sample_the_user_already_owns(env):
    env.db.owned_hashes = ["a"]

    ids = onboarding.copy_samples(USER)

    assert len(ids) == 1
    assert [d.file_hash for d in env.db.added] == ["b"]


def test_second_copy_is_refused(env):
    env.profile.onboarded_at = "earlier"

    with pytest.raises(onboarding.AlreadyOnboarded):
        onboarding.copy_samples(USER)
    assert env.copied == []


def test_failed_insert_removes_copied_files(env):
    env.db.fail_insert = True

    with pytest.raises(RuntimeError):
        onboarding.copy_samples(USER)
    assert env.copied
    assert env.deleted == [dst for _, dst in env.copied]
    assert env.profile.onboarded_at is None


def test_no_sample_account_means_no_samples(env, monkeypatch):
    monkeypatch.setattr(onboarding.settings, "sample_user_id", None)

    assert onboarding.list_samples() == []
    with pytest.raises(onboarding.NoSamples):
        onboarding.copy_samples(USER)
