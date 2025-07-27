from pydantic import BaseModel, Field
from typing import Optional


# # --- Pydantic Models for Request ---
class Request(BaseModel):
    """
    Represents the request body for submitting an anomaly report.
    """
    user_input: str = Field(..., description="Input from the user")
    user_id: str = Field("anonymous_reporter", description="A unique identifier for the user reporting the anomaly.")
    session_id: str = Field("default_anomaly_session", description="A unique identifier for the conversation session.")
