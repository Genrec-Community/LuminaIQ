# Which models the app's Bedrock key can use, and how candidates do on a small LuminaIQ-style task.
import os, time, json
from openai import OpenAI
c = OpenAI(api_key=os.environ["LLM_API_KEY"], base_url="https://bedrock-mantle.ap-southeast-2.api.aws/v1", max_retries=0, timeout=120)
ids = sorted(m.id for m in c.models.list().data)
print("MODELS", len(ids), ids)
print("GPT5-ish", [i for i in ids if "gpt-5" in i or "gpt5" in i])
TASK = ('Return JSON only: {"questions":[{"q":...,"options":[4 strings],"answer":index,"explain":...}]} with 2 MCQs '
        'for a Class 8 student on photosynthesis. Use $...$ for any formula.')
cands = [i for i in ids if "gpt-5" in i] + ["openai.gpt-5.4", "openai.gpt-5.4-mini", "openai.gpt-5", "openai.gpt-5-mini",
         "deepseek.v3.2", "moonshotai.kimi-k2.5", "zai.glm-5", "qwen.qwen3-235b-a22b-2507", "mistral.mistral-large-3-675b-instruct",
         "minimax.minimax-m2.5", "qwen.qwen3-next-80b-a3b-instruct", "openai.gpt-oss-120b", "qwen.qwen3-vl-235b-a22b-instruct"]
seen = set()
for m in cands:
    if m in seen: continue
    seen.add(m)
    t = time.time()
    try:
        r = c.chat.completions.create(model=m, messages=[{"role": "user", "content": TASK}], max_tokens=1500)
        txt = (r.choices[0].message.content or "")
        try:
            s = txt[txt.find("{"): txt.rfind("}") + 1]; ok = len(json.loads(s)["questions"]) == 2
        except Exception:
            ok = False
        print(f"OK  {m:45s} {time.time()-t:5.1f}s json_ok={ok} usage={r.usage.prompt_tokens}/{r.usage.completion_tokens} :: {txt[:120]!r}")
    except Exception as e:
        print(f"ERR {m:45s} {str(e)[:160]}")
