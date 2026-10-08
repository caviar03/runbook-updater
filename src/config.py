import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()


class LazyModel:
    """Allow health/API startup without model credentials; construct on first use."""
    def with_structured_output(self, schema):
        return ChatOpenAI(model="gpt-5.6-luna", temperature=0, timeout=60, max_retries=1).with_structured_output(schema)


llm = LazyModel()

NECESSITY_MODEL = os.getenv("NECESSITY_MODEL") or "MoritzLaurer/deberta-v3-large-zeroshot-v2.0"
