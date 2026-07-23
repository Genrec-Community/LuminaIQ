# Lumina IQ: Azure Migration Guide

This guide outlines the step-by-step process for migrating the Lumina IQ backend and AI services to a completely brand-new Azure account.

Because the architecture cleanly separates the frontend (Vercel), the database/auth (Supabase), and the vector database (Qdrant), migrating the Azure environment **does not involve any data loss or complex database migrations**. You are simply standing up a new server and plugging in the existing database keys.

### Estimated Time: 30–45 Minutes
### Difficulty: Easy to Moderate

---

## Step 1: Create the AI Resources

### 1.1 Azure OpenAI Service
1. Log into the Azure Portal in your new account.
2. Search for **Azure OpenAI** and create a new resource.
3. Choose a region (e.g., East US, Sweden Central) and a pricing tier (Standard S0).
4. Once deployed, open **Azure OpenAI Studio**.
5. Navigate to **Deployments** and create two models:
   - **Chat Model**: Select `gpt-4o-mini` (or standard `gpt-4o`). You can name the deployment `gpt-5-mini` if you wish to match old settings, or give it a cleaner name.
   - **Embedding Model**: Select `text-embedding-3-small`. **Important:** Name the deployment exactly `text-embedding-3-small`.
6. Go to the resource's "Keys and Endpoint" page in the Azure Portal and copy your **Key 1** and **Endpoint**.

### 1.2 Azure Document Intelligence
1. In the Azure Portal, search for **Document Intelligence** (formerly Form Recognizer) and create a new resource.
2. Choose your region and pricing tier.
3. Once deployed, go to "Keys and Endpoint" and copy your **Key 1** and **Endpoint**.

---

## Step 2: Set Up the Backend Server

1. Search for **App Services** in the Azure Portal and create a new Web App.
2. **Configuration Options:**
   - **Publish:** Code
   - **Runtime stack:** Python 3.12
   - **Operating System:** Linux
   - **App Service Plan:** Choose a plan that suits your needs (B1 Basic is a good starting point for testing).
3. Once the Web App is created, navigate to **Settings > Environment variables** (or Configuration).
4. Add all the necessary application settings. You will need:
   - `AZURE_OPENAI_ENDPOINT` (from Step 1.1)
   - `AZURE_OPENAI_API_KEY` (from Step 1.1)
   - `AZURE_OPENAI_DEPLOYMENT` (the name of your chat model deployment)
   - `AZURE_OPENAI_EMBED_DEPLOYMENT` (`text-embedding-3-small`)
   - `AZURE_OPENAI_API_VERSION` (e.g., `2024-12-01-preview`)
   - `AZURE_CV_ENDPOINT` (from Step 1.2)
   - `AZURE_CV_KEY` (from Step 1.2)
   - `SUPABASE_URL` (existing)
   - `SUPABASE_KEY` (existing)
   - `SUPABASE_SERVICE_KEY` (existing)
   - `QDRANT_URL` (existing)
   - `QDRANT_API_KEY` (existing)
   - `BACKEND_CORS_ORIGINS` (e.g., `http://localhost:5173,https://lumina-iq-he4s.vercel.app`)
   - `SCM_DO_BUILD_DURING_DEPLOYMENT` = `True`

---

## Step 3: Deploy the Code

You can deploy the backend code directly from your local machine using the Azure CLI.

1. Open PowerShell or Terminal in the `backend` folder of the LuminaIQ repository.
2. Ensure you are logged into the new Azure account:
   ```bash
   az login
   ```
3. Create a deployment ZIP file. You can use the included python zip script or manually zip the backend files.
4. Deploy using the CLI:
   ```bash
   az webapp deploy --name <YOUR_NEW_APP_NAME> --resource-group <YOUR_NEW_RESOURCE_GROUP> --src-path deploy.zip --type zip
   ```
5. Wait for the deployment to finish and the site to start.

---

## Step 4: Re-link the Frontend

1. Log into your **Vercel** account.
2. Go to the Lumina IQ project > Settings > Environment Variables.
3. Edit `VITE_MAIN_API_URL` to point to your new Azure App Service URL:
   ```
   https://<YOUR_NEW_APP_NAME>.azurewebsites.net/api/v1
   ```
4. Save the variable and trigger a new deployment on Vercel so it picks up the new URL.

**Done!** Your application is now running entirely on your new Azure account without losing any user data, chat history, or processed documents.
