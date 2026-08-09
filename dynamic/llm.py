"""The one place a chat model is built.  Credentials come from .env."""

import os
from pathlib import Path

import dotenv
from langchain_openai import ChatOpenAI

dotenv.load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def chat_model(temperature, timeout):
    return ChatOpenAI(
        model=os.environ["openai_model"],
        base_url=os.environ["openai_api_url"],
        api_key=os.environ["openai_api_key"],
        temperature=temperature,
        timeout=timeout,
    )
