import time
import os
from db.client import get_supabase_client
from services.qdrant_service import qdrant_service
import asyncio

def test_supabase():
    start = time.time()
    try:
        client = get_supabase_client()
        print(f"Supabase init time: {time.time() - start:.2f} seconds")
        
        start2 = time.time()
        res = client.table("projects").select("*").limit(1).execute()
        print(f"Supabase query 1 time: {time.time() - start2:.2f} seconds")
        
        start3 = time.time()
        res2 = client.table("projects").select("*").limit(1).execute()
        print(f"Supabase query 2 time: {time.time() - start3:.2f} seconds")
    except Exception as e:
        print(f"Supabase error: {e}")

async def test_qdrant():
    start = time.time()
    try:
        res = await qdrant_service.async_client.get_collections()
        print(f"Qdrant time: {time.time() - start:.2f} seconds")
    except Exception as e:
        print(f"Qdrant error: {e}")

if __name__ == "__main__":
    test_supabase()
    asyncio.run(test_qdrant())
