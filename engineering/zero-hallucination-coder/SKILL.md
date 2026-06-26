---
name: "zero-hallucination-coder"
description: "Enforce a verify-before-use discipline to eliminate invented APIs, fictional library methods, and fabricated behavior. Use when writing code that depends on external libraries, third-party APIs, or any interface you haven't personally verified in this session."
---

# Zero Hallucination Coder

## Overview

This skill installs a mandatory verification gate between "I think this API exists" and "I write code using this API." Every external claim — library method signature, SDK argument, CLI flag, HTTP endpoint — must be confirmed against a source of truth before it enters the codebase. Suspicion that something exists is not evidence that it does.

## Core Content

### The Claim — Verify — Write loop

Never write code in a single pass from memory. Use this three-step loop:

```
1. CLAIM  — State what you intend to use and why you believe it exists.
2. VERIFY — Confirm it against a primary source (docs, source code, --help output).
3. WRITE  — Only then write the code.
```

If verification fails, revise the claim. Do not proceed to Write with an unverified claim.

### Verification sources (in priority order)

1. **Official documentation** — the library's own docs at the exact version you are installing.
2. **Source code** — read the actual function signature from the package's source.
3. **`--help` / `-h` output** — for CLI tools, run `tool --help` and read what is listed.
4. **Type stubs** — `.d.ts` files, `.pyi` stubs, Go `go doc`. These are generated from source.
5. **REPL confirmation** — `python3 -c "import lib; help(lib.func)"` or `node -e "require('lib').func"`.

**Never treat these as verification:**
- Your training data recollection of an API.
- A blog post, Stack Overflow answer, or README example not pinned to a version.
- A plausible-sounding function name (`client.getUser`, `db.findOne`) with no source.

### Annotating verified claims in code

Every call to an external API that you verified must be traceable:

```python
# verified: boto3 3.x — s3.upload_file(Filename, Bucket, Key)
# source: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/upload_file.html
s3.upload_file(local_path, bucket_name, key)
```

For internal functions, no annotation is needed. Only external interfaces — packages, REST endpoints, CLIs — require a trace comment.

### Handling uncertainty

When you cannot verify a claim, write the code with an explicit unknown marker:

```python
# UNVERIFIED: assuming signature is client.create_record(table, data)
# TODO: confirm against Airtable API docs before merging
result = client.create_record(table_name, payload)
```

Never silently proceed with an unverified API. The unknown marker makes the risk visible so a reviewer can catch it before it ships.

Run `scripts/verify-claim.py` to scan for unverified markers before opening a PR:

```bash
python3 scripts/verify-claim.py --src . --ext py,ts,tsx,js
```

### Version pinning is part of verification

A method that exists in `requests 2.31` may not exist in `requests 2.28`. Every verified claim must name the version:

```
# verified: stripe 7.x — stripe.PaymentIntent.create(amount, currency)
```

Pin the dependency in `requirements.txt` / `package.json` / `go.mod` at that same version. Verification against a floating `latest` is incomplete.

### When the source code is the truth

If docs are stale or missing, read the source:

```bash
# Find the actual method in a Python package
python3 -c "import inspect, boto3; print(inspect.getsource(boto3.client('s3').upload_file))"

# Or open the installed package
python3 -c "import boto3; import os; print(os.path.dirname(boto3.__file__))"
```

Reading the implementation is always more authoritative than reading docs.

### Test-driven verification

Write a test that calls the external API before writing application code. If the test passes, you have live proof the API behaves as expected. If it fails, you catch the hallucination in a safe environment:

```python
def test_s3_upload_file_signature():
    """Verifies that upload_file accepts positional Filename, Bucket, Key."""
    # If this call signature is wrong, this test fails loudly
    s3 = boto3.client("s3", region_name="us-east-1")
    with pytest.raises(ClientError):   # expect auth error, not TypeError
        s3.upload_file("/tmp/test.txt", "nonexistent-bucket-x9k2", "test.txt")
```

A TypeError means you got the signature wrong. A domain-level error means the method exists and you called it correctly.

## Anti-Patterns

**Don't write a plausible stub and assume it's real.** `axios.postJSON(url, data)` sounds like it could exist. It does not. `axios.post(url, data)` is the real method.

**Don't conflate similar libraries.** `requests.get(url).json()` is Python. Assuming Node's `fetch(url).json()` is the same pattern without checking is how you ship broken code. (`fetch(url).then(r => r.json())` is the actual form.)

**Don't skip verification because "this is obvious."** The most common hallucinations involve the most common libraries — because familiarity breeds overconfidence.

**Don't use AI-generated code examples as a verification source.** A model generating an example is not a primary source. A model citing a doc URL is not a primary source unless you visit the URL yourself.

**Don't use deprecated APIs verified only in old docs.** Check the version number on the documentation page. If the docs show a deprecation notice, find the replacement.

## Cross-References

- [engineering/karpathy-coder](../karpathy-coder/SKILL.md) — complementary coding discipline focused on clarity and surgical changes
- [engineering/security-guidance](../security-guidance/SKILL.md) — unverified external behavior is also a security surface
- [engineering/statistical-analyst](../statistical-analyst/SKILL.md) — apply the same "source of truth" discipline to statistical claims
- [engineering/prompt-governance](../prompt-governance/SKILL.md) — prompt-level verification practices for LLM-integrated code
