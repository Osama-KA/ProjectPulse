"""Thin wrapper around the Foundry (Azure OpenAI) GPT deployment.

Reused everywhere in Project Pulse so the connection logic lives in one place.
Talks to Foundry's OpenAI-compatible v1 surface via the `openai` SDK.
"""
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

MODEL = os.environ.get("AZURE_INFERENCE_DEPLOYMENT", "gpt-5-mini")


def get_client() -> OpenAI:
    endpoint = os.environ["AZURE_INFERENCE_ENDPOINT"]
    # Foundry's OpenAI-compatible surface: base_url ends at /openai/v1/
    base_url = endpoint.split("/openai/")[0] + "/openai/v1/"
    return OpenAI(base_url=base_url, api_key=os.environ["AZURE_INFERENCE_KEY"])


def ask(system: str, user: str, client: OpenAI | None = None) -> str:
    """Send one system + user turn, return the model's text reply."""
    client = client or get_client()
    resp = client.responses.create(
        model=MODEL,
        instructions=system,
        input=user,
    )
    return resp.output_text
