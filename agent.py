from __future__ import annotations

from typing import Any

from prompts import TEST_CASE_PROMPT

try:
    from langchain_core.prompts import PromptTemplate
    from langchain_ollama import OllamaLLM
except ImportError as exc:
    PromptTemplate = None
    OllamaLLM = None
    _LANGCHAIN_IMPORT_ERROR: ImportError | None = exc
else:
    _LANGCHAIN_IMPORT_ERROR = None


class ModelConnectionError(RuntimeError):
    """Raised when the configured local model cannot be used."""


def invoke_local_model(
    requirement: str,
    model_name: str,
    base_url: str | None = None,
) -> str:
    if _LANGCHAIN_IMPORT_ERROR is not None:
        raise ModelConnectionError(
            "LangChain's Ollama integration is not installed. Run "
            "`pip install -r requirements.txt`."
        ) from _LANGCHAIN_IMPORT_ERROR

    model_options: dict[str, Any] = {
        "model": model_name,
        "temperature": 0,
        "format": "json",
    }
    if base_url:
        model_options["base_url"] = base_url

    try:
        llm = OllamaLLM(**model_options)
        prompt = PromptTemplate.from_template(TEST_CASE_PROMPT)
        chain = prompt | llm
        response = chain.invoke({"requirement": requirement})
    except Exception as exc:
        raise ModelConnectionError(
            "The local model request failed. Check that Ollama is running, "
            f"the model '{model_name}' is installed, and the model URL is correct. "
            f"Details: {exc}"
        ) from exc

    if not isinstance(response, str):
        raise ModelConnectionError("The local model returned an unsupported response.")
    return response