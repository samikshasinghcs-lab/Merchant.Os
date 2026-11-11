"""AI-assisted refund investigation.
Read-only advisory. Never authorizes or executes payments.
"""

import json
import os
import requests


def explain_refund(facts: dict) -> dict:
    enabled = os.getenv(
        "MERCHANTOS_AI_ENABLED", "false"
    ).lower() == "true"

    key = os.getenv("OPENAI_API_KEY")
    base = os.getenv(
        "OPENAI_BASE_URL",
        "https://api.openai.com/v1"
    )
    model = os.getenv(
        "MERCHANTOS_LLM_MODEL",
        "openai/gpt-4o-mini"
    )

    fallback = (
        "AI analysis is unavailable. "
        "Review the deterministic risk signals "
        "and transaction evidence manually."
    )

    if not enabled or not key:
        return {
            "provider": "disabled",
            "recommendation": "HUMAN_REVIEW_REQUIRED",
            "explanation": fallback
        }

    system = """
You are MerchantOS Refund Intelligence.

You are a read-only financial investigation analyst.

Analyze only the supplied computed transaction facts.

Your responsibilities:
1. Explain detected anomalies.
2. Identify missing evidence.
3. Explain financial exposure.
4. Highlight uncertainty.
5. Recommend whether further human investigation is needed.

Rules:
- Never invent transaction statistics.
- Never invent evidence.
- Never claim fraud without proof.
- Never authorize a refund.
- Never execute payments.
- Never override deterministic financial controls.
- A human merchant makes the final decision.

Return concise plain text.
Clearly distinguish facts from hypotheses.
"""

    try:
        response = requests.post(
            base.rstrip("/") + "/chat/completions",
            headers={
                "Authorization": "Bearer " + key,
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "temperature": 0.1,
                "max_tokens": 350,
                "messages": [
                    {
                        "role": "system",
                        "content": system
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            facts,
                            ensure_ascii=False
                        )
                    }
                ]
            },
            timeout=20
        )

        response.raise_for_status()

        explanation = response.json()[
            "choices"
        ][0]["message"]["content"].strip()

        if not explanation:
            raise ValueError("Empty AI response")

        return {
            "provider": "configured_llm",
            "recommendation": "HUMAN_REVIEW_REQUIRED",
            "explanation": explanation[:4000]
        }

    except Exception:
        return {
            "provider": "llm_unavailable",
            "recommendation": "HUMAN_REVIEW_REQUIRED",
            "explanation": fallback
        }
