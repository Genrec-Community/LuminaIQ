@echo off
echo ==============================================================================
echo LuminaIQ - Azure Container Apps Deployment Script (Windows CMD)
echo ==============================================================================

echo [1/3] Creating Azure Container App 'luminaiq-backend'...
az containerapp create ^
  --name luminaiq-backend ^
  --resource-group LuminaIQ-RG ^
  --image luminaiqacr.azurecr.io/luminaiq-backend:latest ^
  --target-port 8000 ^
  --ingress external ^
  --env-vars ^
      MODEL_API_KEY="your-azure-openai-key-here" ^
      AZURE_OPENAI_ENDPOINT="https://liq.openai.azure.com/" ^
      AZURE_OPENAI_DEPLOYMENT="gpt-5-mini" ^
      AZURE_OPENAI_EMBED_DEPLOYMENT="text-embedding-3-small" ^
      SUPABASE_URL="https://bcosfvilvwyxtrctsmez.supabase.co" ^
      SUPABASE_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJjb3Nmdmlsdnd5eHRyY3RzbWV6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjY3ODIyMTMsImV4cCI6MjA4MjM1ODIxM30.bj9wwAT41fkvGX6CLrmyQT16-Fph4_mgqSXZintsNX0" ^
      SUPABASE_SERVICE_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2Njc4MjIxMywiZXhwIjoyMDgyMzU4MjEzfQ.Fyog6EUERO2Uo7EhlOHQAkRIXnQQEP8e-Klig9kp8I4"

echo ==============================================================================
echo Done!
