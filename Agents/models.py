from pydantic import BaseModel, Field
from typing import List

class Outputformat(BaseModel):
    locations: List[str] = Field(..., description="List of all the locations")