"""The one place a chat model is built.  Credentials come from .env."""

import os
from pathlib import Path

import dotenv
from langchain_openai import ChatOpenAI

dotenv.load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def chat_model(temperature, timeout, seed=None, top_p=None):
    """A chat model.

    `seed` is sent for the stages that must not drift, but this endpoint does not
    honour it: the same seed and the same prompts still changed the verdict on
    three of five skills in a back-to-back rerun.  `top_p` is the constraint that
    does bite, so the court narrows it instead of relying on the seed.
    """
    return ChatOpenAI(
        model=os.environ["openai_model"],
        base_url=os.environ["openai_api_url"],
        api_key=os.environ["openai_api_key"],
        temperature=temperature,
        timeout=timeout,
        seed=seed,
        top_p=top_p,
    )
