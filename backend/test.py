

from openai import OpenAI

endpoint = "https://eastus.api.cognitive.microsoft.com/openai/v1/"
deployment_name = "text-embedding-3-small"
api_key = "REDACTED"

client = OpenAI(
    base_url = endpoint,
    api_key = api_key,
)

response = client.embeddings.create(
    input = "How do I use Python in VS Code?",
    model = deployment_name
)
print(response.data[0].embedding)
