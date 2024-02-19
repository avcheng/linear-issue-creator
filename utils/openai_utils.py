import time
import os

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

openai_api_key = os.environ.get('OPENAI_API_KEY')
client = OpenAI(api_key=openai_api_key)

"""
Assistant that processes a conversation transcript between a customer and a service representative. Based on the transcript, 
determines if the customer is asking for a feature request, reporting a bug, or neither.
"""
script_processing_assistant = client.beta.assistants.create(
    name="Script Processor",
    instructions="You are an assistant that processes a conversation transcript between a customer and a service representative. Based on the transcript, determine if the customer is asking for a feature request, reporting a bug, or neither. Using this call a function to create a linear ticket if it is a feature or bug.",
    tools=[
        {
            "type": "function", 
            "function": {
                "name": "invoke_linear_api",
                "description": "Based on a transcript, this function call pings the Linear API depending on if the customer is requesting a feature, reporting a bug, or neither.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "request_type": {
                            "type": "string",
                            "description": "The type of request the customer is making. Must be 'feature', 'bug', or 'neither'.",
                            "enum": ["feature", "bug", "neither"]
                        },
                        "name": {
                            "type": "string",
                            "description": "The name of the Linear issue to create. If the type is 'neither', this is ignored."
                        },
                        "description": {
                            "type": "string",
                            "description": "The description of the Linear issue to create. Should include the customer name and relevant stakeholders. If the type is 'neither', this is ignored."
                        }
                    },
                    "required": ["request_type"]
                },
            }
        },
    ],
    model="gpt-4-turbo-preview"
)

"""
Assistant that processes a new issue ticket and existing issue tickets. Based on the previous issues' descriptions and the new issues' description,
determines if the new issue is completely new, or if it is similar to a previous issue and returns that previous issue's ID.
"""
linear_issue_matching_assistant = client.beta.assistants.create(
    name="Linear Issue Matching Assistant",
    instructions="You are an assistant that processes takes in a new issue ticket and existing issue tickets. Based on the previous issues' descriptions and the new issues' description, determine if the new issue is completely new, or if it is similar to a previous issue and return that previous issue's ID.",
    tools=[
        {
            "type": "function", 
            "function": {
                "name": "query_issues",
                "description": "Queries all existing active issues and determins if the new issue presented is completely new or if it is the extension of a previous issue.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "is_new_issue": {
                            "type": "boolean",
                            "description": "Whether the new issue is related to any of the existing issues.",
                        },
                        "old_issue_id": {
                            "type": "string",
                            "description": "The specific existing issue that the new issue is related to. If there is no existing issue that the new issue is related to, this is ignored."
                        },
                        "description": {
                            "type": "string",
                            "description": "The comment to add to the existing issue, based on what relevant new context the new issue adds to that existing issue. If there is no existing issue that the new issue is related to, this is ignored."
                        }
                    },
                    "required": ["is_new_issue"]
                },
            }
        },
    ],
    model="gpt-4-turbo-preview"
)


def wait_on_run(run, client, thread_id):
    """
    Utility function to wait on a run to complete.

    Args:
    - run: The run to wait on.
    - client: The OpenAI client.
    - thread_id: The ID of the thread to wait on.

    Returns:
    - The run object.
    """
    while run.status == "queued" or run.status == "in_progress":
        run = client.beta.threads.runs.retrieve(
            thread_id=thread_id,
            run_id=run.id,
        )
        time.sleep(0.2)
    return run

