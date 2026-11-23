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

# The newer OpenAI-compatible endpoint ("bedrock-mantle"), with the app's long-term Bedrock key.
import os
from openai import OpenAI
key = os.environ.get("LLM_API_KEY", "")
print("key set:", bool(key))
for base in ("https://bedrock-mantle.ap-southeast-2.api.aws/v1",):
    c = OpenAI(api_key=key, base_url=base, max_retries=0, timeout=60)
    try:
        print("mantle models:", [m.id for m in c.models.list().data][:40])
    except Exception as e:
        print("ERR mantle models", str(e)[:200])
    for m in ("openai.gpt-oss-120b", "openai.gpt-oss-20b", "qwen.qwen3-32b", "deepseek.v3.1"):
        try:
            r = c.chat.completions.create(model=m, messages=[{"role": "user", "content": "Say hi in 3 words"}], max_tokens=60)
            print("OK   mantle chat", m, (r.choices[0].message.content or "")[:60], r.usage)
        except Exception as e:
            print("ERR  mantle chat", m, str(e)[:200])
        try:
            r = c.responses.create(model=m, input="Say hi in 3 words", max_output_tokens=60)
            print("OK   mantle responses", m, (r.output_text or "")[:60])
        except Exception as e:
            print("ERR  mantle responses", m, str(e)[:200])
    try:
        r = c.embeddings.create(model="amazon.titan-embed-text-v2", input="hello")
        print("OK   mantle embed", len(r.data[0].embedding))
    except Exception as e:
        print("ERR  mantle embed", str(e)[:200])
