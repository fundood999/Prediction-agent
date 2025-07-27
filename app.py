from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
import logging
import json # Import the json module

from models.request import Request
# from models.anomaly_detection_response import CityAnomalyReport
from Agents.agent import root_agent, get_past_incident_data, get_feature_weather_data, feature_event_prediction_agent
from Agents.agent_runner import get_adk_runner, get_message, get_session_service

from tools.get_data_from_big_query import find_location_anomaly_match

APP_NAME = "city_predictor_agent"

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

session_service = get_session_service()  # Get the session service instance

# --- FastAPI Application Initialization ---
app = FastAPI(
    title="ADK Agent API",
    description="API for interacting with a Google ADK agent.",
    version="1.0.0",
)

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# --- API Endpoint ---
@app.post("/query", status_code=200)
async def query_agent(
    request: Request,
):
    """
    Processes a user query using the ADK agent and returns a response.

    - **user_input**: The text message from the user.
    - **user_id**: An identifier for the user (defaults to "default_user").
    - **session_id**: An identifier for the conversation session (defaults to "default_session").
    """
    user_input = request.user_input 
    user_id = request.user_id
    session_id = request.session_id

    runner = get_adk_runner(root_agent, APP_NAME, session_service)
    
    logger.info(f"Received request from user '{user_id}', session '{session_id}'")


    try:
        # Check if session exists.
        existing_session = await session_service.get_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id
        )

        if not existing_session:
            # Create a new session if it doesn't exist.
            await session_service.create_session(
                app_name=APP_NAME,
                user_id=user_id,
                session_id=session_id
            )
            logger.info(f"Created new session for user '{user_id}' with ID '{session_id}'.")
        else:
            logger.info(f"Using existing session for user '{user_id}' with ID '{session_id}'.")

        agent_raw_response_text = "" 
        # The runner.run_async method is an async generator
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=get_message(user_input)
        ):
            if event.is_final_response():
                agent_raw_response_text = event.content.parts[0].text
                # logger.info(f"Agent 1 raw response for session '{session_id}': '{agent1_raw_response_text}'")
                
        if not agent_raw_response_text:
            logger.warning(f"Agent 1 did not produce a final response for session '{session_id}'.")
            raise HTTPException(status_code=500, detail="Agent did not produce a response.")
        # --- NEW LOGIC: Parse JSON string and create AgentResponse instance ---
        try:
            # Assuming agent_raw_response_text is a valid JSON string
            parsed_json = json.loads(agent_raw_response_text)
            
            matches = await find_location_anomaly_match(parsed_json['locations'])

            if len(matches) == 0:
                return {"final_output": "No anomaly found"}

            search_query = ""
            our_data = []
            for i, match in enumerate(matches):
                search_query = f"Event_{i} : {",".join(match[:-2])}"
                our_data.append(
                    {
                        "event_type": match[0],
                        "sub_event_type": match[1],
                        "area_name": match[2],
                        "street_name": match[3],
                        "city": match[4],
                        "description": match[5],
                        "severity_score": match[6]
                    }
                )


            past_news_data = await get_past_incident_data(search_query, user_id, session_id, session_service, APP_NAME)

            feature_weather_data = await get_feature_weather_data(parsed_json['locations'], user_id, session_id, session_service,APP_NAME)

            final_output = await feature_event_prediction_agent(our_data, user_id, session_id, session_service, APP_NAME)

            return {"final_output": final_output}
           
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse agent response as JSON: {e}. Raw response: {agent_raw_response_text}", exc_info=True)
            raise HTTPException(status_code=500, detail="Agent returned invalid JSON.")
        except Exception as e:
            logger.error(f"Failed to validate agent response against CityAnomalyReport model: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Agent response did not match expected structure.")

    except HTTPException: # Re-raise HTTPExceptions directly
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing query for session '{session_id}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")

