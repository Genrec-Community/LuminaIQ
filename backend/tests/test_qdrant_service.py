import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, call

import httpx
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import Distance, PayloadSchemaType

from services.qdrant_service import QdrantService


class QdrantCollectionSetupTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.service = QdrantService.__new__(QdrantService)
        self.service.async_client = AsyncMock()
        self.service._initialized_collections = set()
        self.service._collection_locks = {}

    async def test_existing_collection_performs_no_list_create_or_index_calls(self):
        self.service.async_client.collection_exists.return_value = True
        self.service.async_client.get_collection.return_value = SimpleNamespace(
            payload_schema={"document_id": {}, "chunk_id": {}}
        )

        await self.service.create_collection("project_existing", vector_size=384)

        self.service.async_client.collection_exists.assert_awaited_once_with(
            "project_existing"
        )
        self.service.async_client.get_collections.assert_not_called()
        self.service.async_client.create_collection.assert_not_called()
        self.service.async_client.create_payload_index.assert_not_called()

    async def test_new_collection_creates_required_indexes_once(self):
        self.service.async_client.collection_exists.return_value = False
        self.service.async_client.create_collection.return_value = True
        self.service.async_client.get_collection.return_value = SimpleNamespace(
            payload_schema={}
        )

        await self.service.create_collection("project_new", vector_size=384)

        self.service.async_client.get_collections.assert_not_called()
        self.service.async_client.create_collection.assert_awaited_once()
        create_call = self.service.async_client.create_collection.await_args.kwargs
        self.assertEqual("project_new", create_call["collection_name"])
        self.assertEqual(384, create_call["vectors_config"].size)
        self.assertEqual(Distance.COSINE, create_call["vectors_config"].distance)
        self.assertEqual(
            [
                call(
                    collection_name="project_new",
                    field_name="document_id",
                    field_schema=PayloadSchemaType.KEYWORD,
                    wait=True,
                ),
                call(
                    collection_name="project_new",
                    field_name="chunk_id",
                    field_schema=PayloadSchemaType.INTEGER,
                    wait=True,
                ),
            ],
            self.service.async_client.create_payload_index.await_args_list,
        )

    async def test_concurrent_duplicate_create_is_idempotent(self):
        self.service.async_client.collection_exists.return_value = False
        response = httpx.Response(
            409,
            request=httpx.Request("PUT", "https://qdrant.test/collections/project_race"),
        )
        self.service.async_client.create_collection.side_effect = (
            UnexpectedResponse.for_response(response)
        )
        self.service.async_client.get_collection.return_value = SimpleNamespace(
            payload_schema={"document_id": {}, "chunk_id": {}}
        )

        await self.service.create_collection("project_race", vector_size=384)

        self.service.async_client.create_collection.assert_awaited_once()
        self.service.async_client.get_collection.assert_awaited_once_with("project_race")

    async def test_concurrent_create_returning_false_is_idempotent(self):
        self.service.async_client.collection_exists.return_value = False
        self.service.async_client.create_collection.return_value = False
        self.service.async_client.get_collection.return_value = SimpleNamespace(
            payload_schema={"document_id": {}, "chunk_id": {}}
        )

        await self.service.create_collection("project_race", vector_size=384)

        self.service.async_client.create_collection.assert_awaited_once()
        self.service.async_client.get_collection.assert_awaited_once_with("project_race")


if __name__ == "__main__":
    unittest.main()
