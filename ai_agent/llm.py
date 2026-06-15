import os
import asyncio
from pathlib import Path
from typing import Any, List
from dotenv import load_dotenv
from langchain.chat_models.base import init_chat_model

BASE_DIR = Path(__file__).resolve().parent
ROOT_ENV = BASE_DIR.parent / ".env"
LOCAL_ENV = BASE_DIR / ".env"
if ROOT_ENV.exists():
    load_dotenv(ROOT_ENV)
elif LOCAL_ENV.exists():
    load_dotenv(LOCAL_ENV)
else:
    load_dotenv()

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4.1-mini")
TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.0"))


def _build_model_name(provider: str, model_name: str) -> str:
    provider = provider.lower()
    if provider == "gemini":
        return f"google_genai:{model_name}"
    if provider == "google_genai":
        return f"google_genai:{model_name}"
    if provider == "openai":
        return f"openai:{model_name}"
    return model_name


class LLMClient:
    def __init__(self, model_name: str = MODEL_NAME, temperature: float = TEMPERATURE):
        self.model_name = model_name
        self.temperature = temperature
        self.llm = self._load_llm(LLM_PROVIDER, model_name, temperature)

    @staticmethod
    def _load_llm(provider: str, model_name: str, temperature: float):
        resolved_model = _build_model_name(provider, model_name)
        try:
            return init_chat_model(model=resolved_model, temperature=temperature)
        except ImportError as exc:
            raise ImportError(
                f"LLM provider '{provider}' requires additional integration packages. "
                f"Install the correct LangChain provider package and ensure your virtual environment is active. Original error: {exc}"
            ) from exc
        except Exception as exc:
            raise RuntimeError(
                f"Failed to initialize LLM for provider '{provider}' with model '{resolved_model}'. "
                f"Check your environment variables and package installation. Original error: {exc}"
            ) from exc

    async def generate(self, messages: List[Any]) -> str:
        response = await self.llm.ainvoke(messages)
        return str(response.content)
