import asyncio
import os
import sys

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db.client import get_supabase_client
from config.settings import settings

def test_url():
    supabase = get_supabase_client()
    # just create a fake path
    storage_path = "test_project/test_id_doc.pdf"
    res = supabase.storage.from_("documents").create_signed_url(storage_path, 3600*24)
    print("RETURN VALUE:")
    print(res)
    print("TYPE:", type(res))
    
if __name__ == "__main__":
    test_url()
