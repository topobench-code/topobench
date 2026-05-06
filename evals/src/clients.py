from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv


load_dotenv()


def _parse_extra_arg(value: str) -> Any:
    """Parse CLI request args while allowing plain strings."""
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def parse_request_args(pairs: list[str] | None) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for pair in pairs or []:
        if "=" not in pair:
            raise ValueError(
                f"Invalid --request-arg '{pair}'. Expected KEY=VALUE."
            )
        key, raw_value = pair.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"Invalid --request-arg '{pair}'. Empty key.")
        parsed[key] = _parse_extra_arg(raw_value.strip())
    return parsed


@dataclass(frozen=True)
class GenerationResult:
    text: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    raw: dict[str, Any] | None = None


class ModelClient:
    def generate(
        self,
        provider: str,
        model: str,
        prompt: str,
        *,
        max_output_tokens: int,
        temperature: float | None,
        extra_args: dict[str, Any] | None = None,
    ) -> GenerationResult:
        provider = provider.lower()
        extra_args = dict(extra_args or {})

        if provider == "openai":
            return self._generate_openai(
                model,
                prompt,
                max_output_tokens=max_output_tokens,
                temperature=temperature,
                extra_args=extra_args,
            )
        if provider == "openrouter":
            return self._generate_openrouter(
                model,
                prompt,
                max_output_tokens=max_output_tokens,
                temperature=temperature,
                extra_args=extra_args,
            )
        if provider == "deepseek":
            return self._generate_deepseek(
                model,
                prompt,
                max_output_tokens=max_output_tokens,
                temperature=temperature,
                extra_args=extra_args,
            )
        if provider == "anthropic":
            return self._generate_anthropic(
                model,
                prompt,
                max_output_tokens=max_output_tokens,
                temperature=temperature,
                extra_args=extra_args,
            )
        if provider == "google":
            return self._generate_google(
                model,
                prompt,
                temperature=temperature,
                extra_args=extra_args,
            )

        raise ValueError(
            f"Unsupported provider '{provider}'. Use openai, openrouter, "
            "deepseek, anthropic, or google."
        )

    def _generate_openai(
        self,
        model: str,
        prompt: str,
        *,
        max_output_tokens: int,
        temperature: float | None,
        extra_args: dict[str, Any],
    ) -> GenerationResult:
        from openai import OpenAI

        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        params: dict[str, Any] = {
            "model": model,
            "input": prompt,
            "max_output_tokens": max_output_tokens,
        }
        if temperature is not None:
            params["temperature"] = temperature
        params.update(extra_args)

        response = client.responses.create(**params)
        usage = getattr(response, "usage", None)
        return GenerationResult(
            text=response.output_text or "",
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
            total_tokens=getattr(usage, "total_tokens", None),
            raw=response.model_dump() if hasattr(response, "model_dump") else None,
        )

    def _generate_openrouter(
        self,
        model: str,
        prompt: str,
        *,
        max_output_tokens: int,
        temperature: float | None,
        extra_args: dict[str, Any],
    ) -> GenerationResult:
        from openai import OpenAI

        client = OpenAI(
            api_key=os.environ.get("OPENROUTER_API_KEY")
            or os.environ.get("OPENROUTER_KEY"),
            base_url="https://openrouter.ai/api/v1",
        )
        params: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_output_tokens,
        }
        if temperature is not None:
            params["temperature"] = temperature
        params.update(extra_args)

        response = client.chat.completions.create(**params)
        usage = getattr(response, "usage", None)
        message = response.choices[0].message
        return GenerationResult(
            text=message.content or "",
            input_tokens=getattr(usage, "prompt_tokens", None),
            output_tokens=getattr(usage, "completion_tokens", None),
            total_tokens=getattr(usage, "total_tokens", None),
            raw=response.model_dump() if hasattr(response, "model_dump") else None,
        )

    def _generate_deepseek(
        self,
        model: str,
        prompt: str,
        *,
        max_output_tokens: int,
        temperature: float | None,
        extra_args: dict[str, Any],
    ) -> GenerationResult:
        from openai import OpenAI

        client = OpenAI(
            api_key=os.environ.get("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com",
        )
        params: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_output_tokens,
        }
        if temperature is not None:
            params["temperature"] = temperature
        params.update(extra_args)

        response = client.chat.completions.create(**params)
        usage = getattr(response, "usage", None)
        message = response.choices[0].message
        return GenerationResult(
            text=message.content or "",
            input_tokens=getattr(usage, "prompt_tokens", None),
            output_tokens=getattr(usage, "completion_tokens", None),
            total_tokens=getattr(usage, "total_tokens", None),
            raw=response.model_dump() if hasattr(response, "model_dump") else None,
        )

    def _generate_anthropic(
        self,
        model: str,
        prompt: str,
        *,
        max_output_tokens: int,
        temperature: float | None,
        extra_args: dict[str, Any],
    ) -> GenerationResult:
        from anthropic import Anthropic

        client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        params: dict[str, Any] = {
            "model": model,
            "max_tokens": max_output_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if temperature is not None:
            params["temperature"] = temperature
        params.update(extra_args)

        response = client.messages.create(**params)
        text_parts = [part.text for part in response.content if getattr(part, "text", "")]
        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "input_tokens", None)
        output_tokens = getattr(usage, "output_tokens", None)
        total_tokens = None
        if input_tokens is not None and output_tokens is not None:
            total_tokens = input_tokens + output_tokens
        return GenerationResult(
            text="".join(text_parts),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            raw=response.model_dump() if hasattr(response, "model_dump") else None,
        )

    def _generate_google(
        self,
        model: str,
        prompt: str,
        *,
        temperature: float | None,
        extra_args: dict[str, Any],
    ) -> GenerationResult:
        from google import genai

        client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
        config = dict(extra_args)
        if temperature is not None:
            config["temperature"] = temperature
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=config or None,
        )
        text = getattr(response, "text", None) or ""
        usage = getattr(response, "usage_metadata", None)
        input_tokens = getattr(usage, "prompt_token_count", None)
        output_tokens = getattr(usage, "candidates_token_count", None)
        total_tokens = getattr(usage, "total_token_count", None)
        raw = response.model_dump() if hasattr(response, "model_dump") else None
        return GenerationResult(
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            raw=raw,
        )
