import os

from dotenv import load_dotenv


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()


# ============================================================
# OLLAMA CONFIGURATION
# ============================================================

OLLAMA_HOST = os.getenv(
    "OLLAMA_HOST",
    "http://localhost:11434"
)

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "llama3.2:1b"
)


# ============================================================
# EXTERNAL API KEYS
# ============================================================

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
EXCHANGERATE_API_KEY = os.getenv("EXCHANGERATE_API_KEY")


# ============================================================
# VALIDATION
# ============================================================

def validate_config():

    missing = []

    if not FINNHUB_API_KEY:
        missing.append("FINNHUB_API_KEY")

    if not TAVILY_API_KEY:
        missing.append("TAVILY_API_KEY")

    if not EXCHANGERATE_API_KEY:
        missing.append("EXCHANGERATE_API_KEY")

    if missing:
        raise RuntimeError(
            "Missing environment variables: "
            + ", ".join(missing)
        )


# ============================================================
# DISPLAY CONFIGURATION
# ============================================================

def print_config():

    print("Configuration loaded successfully.")
    print(f"Ollama host: {OLLAMA_HOST}")
    print(f"Ollama model: {OLLAMA_MODEL}")