import os
from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.tools import google_search
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from .models import Outputformat
from .agent_runner import get_message

from dotenv import load_dotenv
load_dotenv()

# Retrieve the API key from an environment variable or directly insert it.
# Using an environment variable is generally safer.
# Ensure this environment variable is set in the terminal where you run 'adk web'.
# Example: export GOOGLE_MAPS_API_KEY="YOUR_ACTUAL_KEY"
google_maps_api_key = os.getenv("GOOGLE_MAPS_API_KEY")

if not google_maps_api_key:
    # Fallback or direct assignment for testing - NOT RECOMMENDED FOR PRODUCTION
    google_maps_api_key = "YOUR_GOOGLE_MAPS_API_KEY_HERE" # Replace if not using env var
    if google_maps_api_key == "YOUR_GOOGLE_MAPS_API_KEY_HERE":
        print("WARNING: GOOGLE_MAPS_API_KEY is not set. Please set it as an environment variable or in the script.")
        # You might want to raise an error or exit if the key is crucial and not found.

location_finder = LlmAgent(
    name="tool_agent",
    model="gemini-2.0-flash",
    description="Tool agent",
    instruction="""
    The user will give a query Like this 'I have to go from Hoodi to Silk Board" and you should extract the 
    place names like this source: Hoodi and destination: Silk Board.
    Then you have to use the googles `geo_encode` agent to encode the source and destination into geo codes
    Input : I have to go from Hoodi to Silk Board.
    Tool call: maps_geocode('Hoodi') and maps_geocode('Silk Board')
    Output: {'Source' : {'Longitude': 77.09 , 'Latitude': 112.89}, 'Destination' : {'Longitude': 67.09 , 'Latitude': 100.89}}

    **Tools**
    - maps_geocode
    """,
    tools=[
        MCPToolset(
            connection_params=StdioConnectionParams(
                server_params = StdioServerParameters(
                    command='npx',
                    args=[
                        "-y",
                        "@modelcontextprotocol/server-google-maps",
                    ],
                    # Pass the API key as an environment variable to the npx process
                    # This is how the MCP server for Google Maps expects the key.
                    env={
                        "GOOGLE_MAPS_API_KEY": google_maps_api_key
                    },
                ),
                timeout=180
            ),
            # You can filter for specific Maps tools if needed:
            tool_filter=['maps_geocode']
        )
    ],
    output_key='geocode'
)

first_agent = LlmAgent(
    model='gemini-2.0-flash',
    name='maps_assistant_agent',
    instruction="""
    Instruction:
    Assist the user with mapping, navigation, and place discovery using Google Maps tools.
    Your input will be something like this :
    Access the {geocode} to get the source and destination and get the directions.
    Use the tool `maps_directions` tool to generate directions from a given source to a specified destination.
    Extract and list all place names, street names, along the route.
    """,
    tools=[
        MCPToolset(
            connection_params=StdioConnectionParams(
                server_params = StdioServerParameters(
                    command='npx',
                    args=[
                        "-y",
                        "@modelcontextprotocol/server-google-maps",
                    ],
                    # Pass the API key as an environment variable to the npx process
                    # This is how the MCP server for Google Maps expects the key.
                    env={
                        "GOOGLE_MAPS_API_KEY": google_maps_api_key
                    },
                ),
                timeout=180
            ),
            # You can filter for specific Maps tools if needed:
            tool_filter=['maps_directions']
        )
    ],
    output_key='directions'
)

formatter_agent = LlmAgent(
    model='gemini-2.0-flash',
    name='formatter_agent',

    instruction=''''
    Instruction:
    Access the {directions} data generated from the maps_directions tool.
    Parse and convert this data into the OutputFormat Pydantic model, ensuring the structure and field types strictly match the definition of OutputFormat.
    ''',
    output_schema=Outputformat
)

root_agent = SequentialAgent(
    name="Pipeline",
    sub_agents=[location_finder, first_agent, formatter_agent]
)

async def get_past_incident_data(search_query: str, user_id, session_id, session_service, app_name):
    get_past_data = LlmAgent(
        model='gemini-2.0-flash',
        name='get_past_data',
        instruction='''
        Your task is to search the news about tease keywords and get all the past news 
        search Query
        use have access to `google_search` tool to search the news.
        ''',
        tools=[
            google_search
        ],
        output_key='news'
    )


    message = get_message(f'Search Queries : {search_query}')

    runner = Runner(agent=get_past_data, session_service=session_service, app_name=app_name)

    agent_raw_response_text = ""
    async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=message
        ):
            if event.is_final_response():
                agent_raw_response_text = event.content.parts[0].text
    
    return agent_raw_response_text

async def get_feature_weather_data(locations: list, user_id, session_id, session_service, app_name):
    get_past_data = LlmAgent(
        model='gemini-2.0-flash',
        name='get_feature_weather_data',
        instruction='''
        Your task is to search about possible feature wether from 
        the given locations
        use have access to `google_search` tool to search the news.
        ''',
        tools=[
            google_search
        ],
        output_key='feature_weather'
    )

    message = get_message(f'Locations : {locations}')

    runner = Runner(agent=get_past_data, session_service=session_service, app_name=app_name)

    agent_raw_response_text = ""
    async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=message
        ):
            if event.is_final_response():
                agent_raw_response_text = event.content.parts[0].text
    
    return agent_raw_response_text


async def feature_event_prediction_agent(our_data, user_id, session_id, session_service, app_name):
    get_past_data = LlmAgent(
        model='gemini-2.5-flash',
        name='prediction',
        instruction='''
        The user will give you three inputs you should access the inputs from session state
        Input 1: {news} It is the past anomaly happened in that location for that particular event
        Input 2: {feature_weather} It is the possible weather condition in those locations for that particular events
        Input 3: the user will be providing the current condition of the Place

        Using all these data decide what might happen in that area after 1 or 2 hrs. Will anomaly will still be there or
        the anomaly will be gone or because of the wether the anomaly will increase you have to tell that.
        And Limit your output words to less than 100 words along with the advice to the user to avoid the inconvinence.
        ''',
        output_key='final_output'
    )

    message = get_message(f'Current Data : {our_data}')

    runner = Runner(agent=get_past_data, session_service=session_service, app_name=app_name)

    agent_raw_response_text = ""
    async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=message
        ):
            if event.is_final_response():
                agent_raw_response_text = event.content.parts[0].text
    
    return agent_raw_response_text
