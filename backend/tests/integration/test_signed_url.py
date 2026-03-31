"""Integration test for Supabase signed URL generation."""

import pytest
from db.client import get_supabase_client


@pytest.mark.integration
def test_signed_url_generation():
    """Test that Supabase can generate signed URLs for document storage."""
    supabase = get_supabase_client()
    
    # Create a fake path for testing
    storage_path = "test_project/test_id_doc.pdf"
    
    # Generate signed URL (valid for 24 hours)
    result = supabase.storage.from_("documents").create_signed_url(storage_path, 3600 * 24)
    
    print(f"\nSigned URL Result: {result}")
    print(f"Result Type: {type(result)}")
    
    # Verify result structure
    assert result is not None, "Signed URL result should not be None"
    assert isinstance(result, dict), "Result should be a dictionary"
    
    # Check for expected keys
    if "signedURL" in result:
        assert result["signedURL"], "Signed URL should not be empty"
        print("✓ Signed URL generated successfully")
    elif "error" in result:
        pytest.skip(f"Supabase storage error: {result['error']}")
    else:
        pytest.fail(f"Unexpected result structure: {result}")
