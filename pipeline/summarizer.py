"""
Summarizer — calls local Ollama Gemma model to generate plain-language summaries.
"""

import requests
import logging
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent


class Summarizer:
    def __init__(self, model_config: dict, prompt_template_path: str):
        self.host = model_config["host"]
        self.model = model_config["model"]
        self.fallback = model_config.get("fallback")
        self.timeout = model_config.get("timeout", 120)

        template_path = BASE_DIR / prompt_template_path
        with open(template_path) as f:
            self.prompt_template = f.read()

    def summarize(self, bill: dict) -> str:
        bill_text = bill.get("full_text") or bill.get("summary") or bill.get("title", "")
        prompt = self.prompt_template.replace("{bill_text}", bill_text[:8000])

        for model in [self.model, self.fallback]:
            if not model:
                continue
            try:
                resp = requests.post(
                    f"{self.host}/api/generate",
                    json={"model": model, "prompt": prompt, "stream": False},
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                return resp.json()["response"].strip()
            except Exception as e:
                logging.warning(f"Model {model} failed: {e}")

        return "[Summary unavailable]"
