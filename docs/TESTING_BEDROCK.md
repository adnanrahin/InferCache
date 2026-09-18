# Testing InferCache with AWS Bedrock

Step-by-step guide to validate InferCache against Bedrock (Converse API).

**Status:** Bedrock adapter is implemented; treat this as a validation checklist until you mark it **Tested** in the README.

---

## Prerequisites

1. **AWS account** with Bedrock access in a region (e.g. `us-east-1`)
2. **Model access** enabled in Bedrock console for the model you will use  
   (e.g. Claude, Llama, Amazon Nova — enable each model in **Bedrock → Model access**)
3. **Credentials** on your machine (one of):
   - `aws configure` → `~/.aws/credentials`
   - Env vars: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`
   - IAM role (EC2 / ECS / CloudShell)
4. **Python env** with InferCache:

```powershell
conda activate infer_cache
pip install -e ".[bedrock]"
# or: pip install "infercache[bedrock]"
```

5. IAM permission at minimum:

```json
{
  "Effect": "Allow",
  "Action": [
    "bedrock:InvokeModel",
    "bedrock:Converse"
  ],
  "Resource": "*"
}
```

---

## 1. Smoke-test AWS + Bedrock (no InferCache)

```powershell
aws sts get-caller-identity
aws bedrock list-foundation-models --region us-east-1 --query "modelSummaries[?contains(modelId, `claude`)].modelId" --output text
```

If identity fails → fix credentials.  
If models list is empty or Converse fails → enable model access in the console.

---

## 2. Run the built-in Bedrock example

```powershell
cd path\to\InferCache

$env:AWS_DEFAULT_REGION = "us-east-1"
# optional override:
# $env:BEDROCK_MODEL = "anthropic.claude-3-5-sonnet-20241022-v2:0"

python examples/bedrock_example.py
```

**Expected:**

| Call | `cache_hit` |
|------|-------------|
| First | `False` (hits Bedrock) |
| Second (same messages) | `True` (no Bedrock charge) |

If you see `AccessDeniedException` or `ResourceNotFoundException`:

- Wrong region
- Model ID not enabled / EOL model ID
- Missing IAM action

Update `default_model` in the example or via env to a model you actually have.

---

## 3. One-liner adapter check

```powershell
python -c @"
from infercache.integrations.adapters import BedrockAdapter
a = BedrockAdapter(region_name='us-east-1')
r1 = a.chat([{'role':'user','content':'Reply with exactly: OK'}])
r2 = a.chat([{'role':'user','content':'Reply with exactly: OK'}])
print('1:', r1['cache_hit'], r1['response'][:80])
print('2:', r2['cache_hit'], r2['response'][:80])
print('provider:', r1.get('provider'))
"@
```

Expect first miss, second hit.

---

## 4. FastAPI app with Bedrock

```powershell
pip install fastapi uvicorn
$env:PROVIDER = "bedrock"
$env:AWS_REGION = "us-east-1"
$env:BEDROCK_MODEL = "anthropic.claude-3-5-sonnet-20241022-v2:0"

python -m uvicorn examples.fastapi_app:app --host 127.0.0.1 --port 8080
```

In another terminal:

```powershell
$body = @{
  user_id = "alice"
  prompt  = "What is semantic caching in one sentence?"
} | ConvertTo-Json

Invoke-RestMethod -Uri http://127.0.0.1:8080/v1/chat `
  -Method POST -ContentType "application/json" -Body $body

# Call again — expect cache_hit true
Invoke-RestMethod -Uri http://127.0.0.1:8080/v1/chat `
  -Method POST -ContentType "application/json" -Body $body
```

---

## 5. Choosing a model ID

Use a **current** Bedrock model ID from your account. Examples (verify in console; IDs change):

| Family | Example modelId |
|--------|-----------------|
| Claude | `anthropic.claude-3-5-sonnet-20241022-v2:0` (or newer) |
| Haiku | `anthropic.claude-3-5-haiku-20241022-v1:0` |
| Nova | `amazon.nova-micro-v1:0` / `amazon.nova-lite-v1:0` |

Inference profiles / cross-region IDs may look like `us.anthropic.claude-...`.  
If Converse fails with “model not found”, copy the exact ID from the Bedrock console.

Set it with:

```powershell
$env:BEDROCK_MODEL = "YOUR_MODEL_ID"
```

or pass `default_model=...` to `BedrockAdapter(...)`.

---

## 6. What to verify (checklist)

- [ ] First identical prompt → `cache_hit: false`, non-empty response  
- [ ] Second identical prompt → `cache_hit: true`, same response, much faster  
- [ ] Paraphrase (optional) → may be semantic hit depending on threshold  
- [ ] `cache.stats()` shows rising hits / tokens_saved  
- [ ] CloudWatch / billing: second call should **not** invoke Bedrock again  
- [ ] Bad credentials → clear error (not silent empty response)

---

## 7. Common failures

| Symptom | Fix |
|---------|-----|
| `NoCredentialsError` | `aws configure` or set AWS env vars |
| `AccessDeniedException` | Enable model access; fix IAM |
| `ValidationException` / unknown model | Update model ID; check region |
| Slow first call, never caches | Confirm you call `adapter.chat` / `get_or_call` twice with same model scope |
| EOL model | Pick a current Claude/Nova ID from Bedrock console |

---

## 8. Ollama vs Bedrock (same app)

| | Ollama | Bedrock |
|--|--------|---------|
| Install | Local Ollama | `pip install "infercache[bedrock]"` + AWS creds |
| Adapter | `OllamaAdapter` | `BedrockAdapter` |
| FastAPI | `PROVIDER=ollama` | `PROVIDER=bedrock` |
| Cost | Local GPU/CPU | Per-token AWS billing |
| Cache file | Same `~/.infercache/cache.db` if you use sqlite | Same |

You can A/B the same FastAPI example by switching `PROVIDER` only.

---

## 9. After Bedrock passes

1. Mark **Bedrock** as **Tested** in `README.md` / `docs/GETTING_STARTED.md` status tables.  
2. Keep model IDs out of committed secrets; use env vars.  
3. Prefer a cheap model (Haiku / Nova Micro) for CI-style smoke tests.
