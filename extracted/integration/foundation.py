from dotenv import load_dotenv
import os

from foundation.config import CloudinaryConfig
from foundation.clients import (
    OpenAIClient,
    OpenRouterClient,
    OllamaClient,
    CloudinaryClient,
)


class Foundation:
    openai: OpenAIClient
    openrouter: OpenRouterClient
    ollama: OllamaClient
    cloudinary: CloudinaryClient


    def __init__(self):
        load_dotenv()

        self.openai = OpenAIClient(
            api_key=os.getenv("OPENAI_API_KEY"),
            model=os.getenv("OPENAI_MODEL", "gpt-5"),
            base_url=os.getenv(
                "OPENAI_BASE_URL",
                "https://api.openai.com/v1"
        ),
        )

        #self.openrouter = OpenRouterClient(
         #   api_key=os.getenv("OPENROUTER_API_KEY"),
          #  model=os.getenv("OPENROUTER_MODEL", "openai/gpt-5"),
           # base_url=os.getenv(
            #    "OPENAI_BASE_URL",
             #   "https://api.openai.com/v1",
            #),
        #)

        self.ollama = OllamaClient(
            host=os.getenv(
                "OLLAMA_HOST",
                "http://localhost:11434",
            ),
            model=os.getenv(
                "OLLAMA_MODEL",
                "qwen3:latest",
            ),
        )

        self.cloudinary = CloudinaryClient(
            CloudinaryConfig(
                cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
                api_key=os.getenv("CLOUDINARY_API_KEY"),
                api_secret=os.getenv("CLOUDINARY_API_SECRET"),
            )
        )




foundation = Foundation()
__all__ = ["foundation", "Foundation"]