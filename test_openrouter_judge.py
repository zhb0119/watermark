#!/usr/bin/env python
"""测试 OpenRouter GPT-4o judge 调用"""
import os
import sys
from openai import OpenAI

# 读取环境变量
api_key = os.getenv("OPENROUTER_API_KEY")
base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
model = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o")
timeout = float(os.getenv("OPENROUTER_TIMEOUT", "30"))

print(f"[Config]")
print(f"  API Key: {api_key[:20] if api_key else 'None'}...")
print(f"  Base URL: {base_url}")
print(f"  Model: {model}")
print(f"  Timeout: {timeout}s")
print()

if not api_key:
    print("[Error] OPENROUTER_API_KEY not set")
    sys.exit(1)

# 创建 client
print("[Client] Creating OpenAI client...")
try:
    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=timeout
    )
    print("[Client] ✓ Created")
except Exception as exc:
    print(f"[Client] ✗ Failed: {exc}")
    sys.exit(1)

# 测试简单调用
print()
print("[Test 1] Simple completion...")
try:
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Say OK only"}],
        max_tokens=10,
        temperature=0
    )
    print(f"[Test 1] ✓ Response: {response.choices[0].message.content}")
except Exception as exc:
    print(f"[Test 1] ✗ Failed: {type(exc).__name__}: {exc}")
    sys.exit(1)

# 测试 LongMemEval judge prompt
print()
print("[Test 2] LongMemEval judge prompt...")
question = "What is my degree?"
answer = "Computer Science"
hypothesis = "Based on the memory records, your degree is Computer Science."

prompt = (
    "I will give you a question, a correct answer, and a response from a model. "
    "Please answer yes if the response contains the correct answer. Otherwise, answer no. "
    "If the response is equivalent to the correct answer or contains all the intermediate steps "
    "to get the correct answer, you should also answer yes. If the response only contains a subset "
    "of the information required by the answer, answer no. \n\n"
    f"Question: {question}\n\n"
    f"Correct Answer: {answer}\n\n"
    f"Model Response: {hypothesis}\n\n"
    "Is the model response correct? Answer yes or no only."
)

try:
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=10,
        temperature=0,
        timeout=timeout
    )
    raw = response.choices[0].message.content.strip()
    label = "yes" in raw.lower()
    print(f"[Test 2] ✓ Raw response: {raw}")
    print(f"[Test 2] ✓ Label: {label}")
except Exception as exc:
    print(f"[Test 2] ✗ Failed: {type(exc).__name__}: {exc}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()
print("[Success] All tests passed!")
