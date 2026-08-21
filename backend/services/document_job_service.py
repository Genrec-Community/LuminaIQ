from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Mapping, Optional

from db.client import async_db, get_supabase_client


class DocumentJobProtocolError(RuntimeError):
    """The database returned a result that violates the lease protocol."""


@dataclass(frozen=True)
class ClaimedDocumentJob:
    id: str
    project_id: str
    document_id: str
    user_id: str
    lease_token: str
    lease_expires_at: str
    attempts: int
    max_attempts: int
    stage: str
    progress: int

    @classmethod
    def from_rpc(cls, row: Mapping[str, Any]) -> "ClaimedDocumentJob":
        required = (
            "id",
            "project_id",
            "document_id",
            "user_id",
            "lease_token",
            "lease_expires_at",
        )
        missing = [name for name in required if not row.get(name)]
        if row.get("status") != "processing" or missing:
            detail = (
                f"missing {', '.join(missing)}"
                if missing
                else "status is not processing"
            )
            raise DocumentJobProtocolError(f"Invalid claimed document job: {detail}")
        try:
            return cls(
                id=str(row["id"]),
                project_id=str(row["project_id"]),
                document_id=str(row["document_id"]),
                user_id=str(row["user_id"]),
                lease_token=str(row["lease_token"]),
                lease_expires_at=str(row["lease_expires_at"]),
                attempts=int(row.get("attempts", 0)),
                max_attempts=int(row.get("max_attempts", 0)),
                stage=str(row.get("stage", "claimed")),
                progress=int(row.get("progress", 0)),
            )
        except (TypeError, ValueError) as error:
            raise DocumentJobProtocolError(
                "Invalid numeric fields in claimed document job"
            ) from error


class DocumentJobService:
    """Lease-safe durable document job operations over Supabase RPCs."""

    def __init__(
        self,
        client=None,
        db_runner: Callable[[Callable[[], Any]], Awaitable[Any]] = async_db,
    ):
        self._client = client if client is not None else get_supabase_client()
        self._db_runner = db_runner

    async def claim(
        self, worker_id: str, lease_seconds: int
    ) -> Optional[ClaimedDocumentJob]:
        result = await self._rpc(
            "claim_document_job",
            {"p_worker_id": worker_id, "p_lease_seconds": lease_seconds},
        )
        data = result.data
        if data is None or data == []:
            return None
        if isinstance(data, Mapping):
            row = data
        elif isinstance(data, list) and len(data) == 1 and isinstance(data[0], Mapping):
            row = data[0]
        else:
            raise DocumentJobProtocolError("Claim RPC returned an unexpected row set")
        return ClaimedDocumentJob.from_rpc(row)

    async def heartbeat(
        self, job_id: str, lease_token: str, lease_seconds: int
    ) -> bool:
        result = await self._rpc(
            "heartbeat_document_job",
            {
                "p_job_id": job_id,
                "p_lease_token": lease_token,
                "p_lease_seconds": lease_seconds,
            },
        )
        return self._mutation_applied(result.data)

    async def update_progress(
        self, job_id: str, lease_token: str, stage: str, progress: int
    ) -> bool:
        result = await self._rpc(
            "update_document_job_progress",
            {
                "p_job_id": job_id,
                "p_lease_token": lease_token,
                "p_stage": stage,
                "p_progress": progress,
            },
        )
        return self._mutation_applied(result.data)

    async def complete(self, job_id: str, lease_token: str) -> bool:
        result = await self._rpc(
            "complete_document_job",
            {"p_job_id": job_id, "p_lease_token": lease_token},
        )
        return self._mutation_applied(result.data)

    async def fail(
        self,
        job_id: str,
        lease_token: str,
        error_code: str,
        error_message: str,
        retryable: bool = True,
        retry_delay_seconds: int = 30,
    ) -> bool:
        result = await self._rpc(
            "fail_document_job",
            {
                "p_job_id": job_id,
                "p_lease_token": lease_token,
                "p_error_code": error_code,
                "p_error_message": error_message,
                "p_retryable": retryable,
                "p_retry_delay_seconds": retry_delay_seconds,
            },
        )
        return self._mutation_applied(result.data)

    async def _rpc(self, name: str, payload: dict[str, Any]):
        return await self._db_runner(lambda: self._client.rpc(name, payload).execute())

    @staticmethod
    def _mutation_applied(data: Any) -> bool:
        if isinstance(data, bool):
            return data
        if isinstance(data, list) and len(data) == 1 and isinstance(data[0], bool):
            return data[0]
        raise DocumentJobProtocolError("Mutation RPC did not return a boolean")
