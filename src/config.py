import math
import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()


class LazyModel:
    """Allow health/API startup without model credentials; construct on first use."""
    def with_structured_output(self, schema):
        model = os.environ.get("OPENAI_MODEL", "gpt-5-nano").strip()
        if not model:
            raise ValueError("OPENAI_MODEL must not be empty")
        try:
            timeout = float(os.environ.get("OPENAI_TIMEOUT_SECONDS", "180"))
        except ValueError as error:
            raise ValueError("OPENAI_TIMEOUT_SECONDS must be a positive number") from error
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("OPENAI_TIMEOUT_SECONDS must be a positive number")
        # Reasoning models choose their own sampling settings; preserve the
        # existing structured schema rather than forcing temperature=0.
        return ChatOpenAI(model=model, timeout=timeout, max_retries=1).with_structured_output(schema)


llm = LazyModel()

NECESSITY_MODEL = os.getenv("NECESSITY_MODEL") or "MoritzLaurer/deberta-v3-large-zeroshot-v2.0"
