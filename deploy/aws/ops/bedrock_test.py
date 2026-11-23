# Which Bedrock models answer from this account right now (run on the server with its instance role).
import json, boto3
from botocore.config import Config
R = "ap-southeast-2"
rt = boto3.client("bedrock-runtime", region_name=R, config=Config(retries={"max_attempts": 1}))
models = ["openai.gpt-oss-120b-1:0", "openai.gpt-oss-20b-1:0", "amazon.nova-micro-v1:0", "amazon.nova-lite-v1:0",
          "apac.amazon.nova-micro-v1:0", "apac.amazon.nova-lite-v1:0", "au.amazon.nova-lite-v1:0",
          "global.amazon.nova-2-lite-v1:0", "au.anthropic.claude-haiku-4-5-20251001-v1:0",
          "qwen.qwen3-32b-v1:0", "deepseek.v3-v1:0", "meta.llama3-8b-instruct-v1:0", "mistral.mistral-large-3-675b-instruct",
          "google.gemma-3-12b-it", "minimax.minimax-m2", "moonshot.kimi-k2-thinking"]
for m in models:
    try:
        r = rt.converse(modelId=m, messages=[{"role": "user", "content": [{"text": "Say hi in 3 words"}]}],
                        inferenceConfig={"maxTokens": 40})
        print("OK  ", m, str(r["output"]["message"]["content"])[:60])
    except Exception as e:
        print("ERR ", m, str(e)[:160])
for m, body in [("amazon.titan-embed-text-v2:0", {"inputText": "hi", "dimensions": 1024}),
                ("cohere.embed-multilingual-v3", {"texts": ["hi"], "input_type": "search_document"})]:
    try:
        rt.invoke_model(modelId=m, body=json.dumps(body)); print("OK   embed", m)
    except Exception as e:
        print("ERR  embed", m, str(e)[:160])
try:
    sq = boto3.client("service-quotas", region_name=R)
    for q in sq.list_service_quotas(ServiceCode="bedrock", MaxResults=100)["Quotas"]:
        n = q["QuotaName"]
        if "On-demand" in n and ("tokens per minute" in n) and any(k in n for k in ("gpt-oss", "Nova", "Titan Text Embeddings V2")):
            print("QUOTA", q["Value"], q["Adjustable"], n)
except Exception as e:
    print("quota check failed", str(e)[:160])
