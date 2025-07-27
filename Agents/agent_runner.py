import logging

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types


# --- Logging Setup ---
# Configure basic logging to console
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_session_service():
    """
    Returns an instance of InMemorySessionService for managing user sessions.
    This is used to store and retrieve session data across requests.
    """
    logger.info("InMemorySessionService initialized.")
    return InMemorySessionService()

# --- Dependency for ADK Runner ---
# This function will be called by FastAPI to provide a Runner instance for each request.
# Using Depends ensures the Runner is correctly initialized with the global agent and session service.
def get_adk_runner(agent, app_name, session_service) -> Runner:
    """
    Provides a configured ADK Runner instance.
    """
    return Runner(agent=agent, session_service=session_service, app_name=app_name)

def get_message(user_message: str) -> types.Content:
    return types.Content(role="user", parts=[types.Part(text=user_message)])