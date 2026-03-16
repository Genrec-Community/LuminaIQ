"""
Run script for Lumina IQ Main API (backend)
Start the service with: python run.py
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="debug",  # Changed to debug for more logs
        access_log=True     # Enable access logs for all requests
    )
