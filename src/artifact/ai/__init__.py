"""AI module for ARTIFACT - Gemini integration for predictions and caricatures."""

from artifact.ai.client import GeminiClient, get_gemini_client
from artifact.ai.predictor import PredictionService, Prediction
from artifact.ai.caricature import CaricatureService, Caricature

__all__ = [
    # Client
    "GeminiClient",
    "get_gemini_client",
    # Prediction
    "PredictionService",
    "Prediction",
    # Caricature
    "CaricatureService",
    "Caricature",
]
