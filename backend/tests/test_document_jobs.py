import unittest
from types import SimpleNamespace

from config.settings import Settings
from document_worker import (
    DocumentWorkerDisabledError,
    DocumentWorkerNotIntegratedError,
    ensure_worker_enabled,
    poll_once,
)
from services.document_job_service import (
    ClaimedDocumentJob,
    DocumentJobProtocolError,
    DocumentJobService,
)


class _RPCRequest:
    def __init__(self, response):
        self._response = response

    def execute(self):
        return self._response


class _Client:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def rpc(self, name, payload):
        self.calls.append((name, payload))
        return _RPCRequest(self.responses.pop(0))


async def _inline_db(callable_fn):
    return callable_fn()


def _claimed_row(**overrides):
    row = {
        "id": "job-id",
        "project_id": "project-id",
        "document_id": "document-id",
        "user_id": "user-id",
        "status": "processing",
        "lease_token": "lease-token",
        "lease_expires_at": "2026-08-22T02:00:00+00:00",
        "attempts": 1,
        "max_attempts": 3,
        "stage": "claimed",
        "progress": 0,
    }
    row.update(overrides)
    return row


class DocumentJobServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_claim_sends_rpc_payload_and_parses_lease(self):
        client = _Client([SimpleNamespace(data=[_claimed_row()])])
        service = DocumentJobService(client, _inline_db)

        job = await service.claim("worker-1", 120)

        self.assertEqual(
            [
                (
                    "claim_document_job",
                    {"p_worker_id": "worker-1", "p_lease_seconds": 120},
                )
            ],
            client.calls,
        )
        self.assertEqual("lease-token", job.lease_token)
        self.assertEqual(1, job.attempts)

    async def test_claim_returns_none_when_queue_is_empty(self):
        service = DocumentJobService(_Client([SimpleNamespace(data=[])]), _inline_db)

        self.assertIsNone(await service.claim("worker-1", 300))

    async def test_claim_rejects_row_without_active_lease(self):
        service = DocumentJobService(
            _Client([SimpleNamespace(data=[_claimed_row(lease_token=None)])]),
            _inline_db,
        )

        with self.assertRaisesRegex(DocumentJobProtocolError, "lease_token"):
            await service.claim("worker-1", 300)

    async def test_lease_mutations_send_exact_rpc_payloads(self):
        client = _Client([SimpleNamespace(data=True) for _ in range(4)])
        service = DocumentJobService(client, _inline_db)

        self.assertTrue(await service.heartbeat("job", "lease", 90))
        self.assertTrue(await service.update_progress("job", "lease", "extracting", 25))
        self.assertTrue(await service.complete("job", "lease"))
        self.assertTrue(
            await service.fail("job", "lease", "provider_error", "offline", False, 60)
        )

        self.assertEqual(
            [
                (
                    "heartbeat_document_job",
                    {
                        "p_job_id": "job",
                        "p_lease_token": "lease",
                        "p_lease_seconds": 90,
                    },
                ),
                (
                    "update_document_job_progress",
                    {
                        "p_job_id": "job",
                        "p_lease_token": "lease",
                        "p_stage": "extracting",
                        "p_progress": 25,
                    },
                ),
                (
                    "complete_document_job",
                    {"p_job_id": "job", "p_lease_token": "lease"},
                ),
                (
                    "fail_document_job",
                    {
                        "p_job_id": "job",
                        "p_lease_token": "lease",
                        "p_error_code": "provider_error",
                        "p_error_message": "offline",
                        "p_retryable": False,
                        "p_retry_delay_seconds": 60,
                    },
                ),
            ],
            client.calls,
        )

    async def test_lost_lease_is_reported_as_false(self):
        service = DocumentJobService(_Client([SimpleNamespace(data=False)]), _inline_db)

        self.assertFalse(await service.complete("job", "stale-lease"))


class _WorkerService:
    def __init__(self, job=None):
        self.job = job
        self.claims = []
        self.failures = []

    async def claim(self, worker_id, lease_seconds):
        self.claims.append((worker_id, lease_seconds))
        return self.job

    async def fail(self, *args, **kwargs):
        self.failures.append((args, kwargs))
        return True


class DocumentWorkerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.settings = SimpleNamespace(
            DOCUMENT_JOBS_ENABLED=False,
            DOCUMENT_WORKER_ENABLED=False,
            DOCUMENT_JOB_LEASE_SECONDS=300,
            DOCUMENT_JOB_POLL_INTERVAL_SECONDS=0.01,
        )

    async def test_worker_is_disabled_by_default_flags(self):
        self.assertFalse(Settings.model_fields["DOCUMENT_JOBS_ENABLED"].default)
        self.assertFalse(Settings.model_fields["DOCUMENT_WORKER_ENABLED"].default)

        with self.assertRaisesRegex(
            DocumentWorkerDisabledError, "DOCUMENT_JOBS_ENABLED"
        ):
            ensure_worker_enabled(self.settings)

        self.settings.DOCUMENT_JOBS_ENABLED = True
        with self.assertRaisesRegex(
            DocumentWorkerDisabledError, "DOCUMENT_WORKER_ENABLED"
        ):
            ensure_worker_enabled(self.settings)

        self.settings.DOCUMENT_WORKER_ENABLED = True
        with self.assertRaisesRegex(
            DocumentWorkerNotIntegratedError, "not integrated"
        ):
            ensure_worker_enabled(self.settings)

    async def test_worker_refuses_to_claim_before_pipeline_integration(self):
        service = _WorkerService(ClaimedDocumentJob.from_rpc(_claimed_row()))

        with self.assertRaisesRegex(
            DocumentWorkerNotIntegratedError, "Refusing to claim"
        ):
            await poll_once(service, "worker", self.settings)

        self.assertEqual([], service.claims)
        self.assertEqual([], service.failures)

    async def test_empty_poll_also_refuses_before_pipeline_integration(self):
        service = _WorkerService()

        with self.assertRaises(DocumentWorkerNotIntegratedError):
            await poll_once(service, "worker", self.settings)
        self.assertEqual([], service.claims)
        self.assertEqual([], service.failures)


if __name__ == "__main__":
    unittest.main()
