@echo off
echo ==============================================================================
echo LuminaIQ - Azure Container Apps Deployment Script (Windows CMD)
echo ==============================================================================

echo [1/2] Creating Azure Container App Environment 'luminaiq-env'...
az containerapp env create --name luminaiq-env --resource-group LuminaIQ-RG --location centralindia

echo [2/2] Creating Azure Container App 'luminaiq-backend'...
az containerapp create ^
  --name luminaiq-backend ^
  --resource-group LuminaIQ-RG ^
  --environment luminaiq-env ^
  --image luminaiqacr.azurecr.io/luminaiq-backend:latest ^
  --target-port 8000 ^
  --ingress external ^
  --env-vars ^
      MODEL_API_KEY="your-azure-openai-key-here" ^
      AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/" ^
      AZURE_OPENAI_DEPLOYMENT="gpt-5-mini" ^
      AZURE_OPENAI_MODEL="gpt-5-mini" ^
      AZURE_OPENAI_EMBED_DEPLOYMENT="text-embedding-3-small" ^
      SUPABASE_URL="https://your-project.supabase.co" ^
      SUPABASE_KEY="your-supabase-anon-key" ^
      SUPABASE_SERVICE_KEY="your-supabase-service-role-key"

echo ==============================================================================
echo Done!
