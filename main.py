import json
import logging

from utils.openai_utils import (
    wait_on_run, 
    client, 
    script_processing_assistant, 
    linear_issue_matching_assistant
)
from utils.linear_api_utils import (
    retrieve_linear_issue_label_id,
    create_linear_issue, 
    get_all_active_issues, 
    add_comment_to_linear_issue
)


def invoke_linear_api(type, name = "", description = ""):
    """
    Invokes the Linear API depending on if the customer is requesting a feature, reporting a bug, or neither.

    Args:
    - type: The type of request the customer is making. Must be 'feature', 'bug', or 'neither'.
    - name: The name of the Linear issue to create. If the type is 'neither', this is ignored.
    - description: The description of the Linear issue to create. If the type is 'neither', this is ignored.

    Returns:
    - issue_id: The ID of the Linear issue that was created. If the type is 'neither', no issue is created and this is None.
    """

    if type == "neither":
        return None
    
    if type == "feature":
        # Retrieve a Feature label ID
        label_id = retrieve_linear_issue_label_id("Feature")
    else:
        # Retrieve a Bug label ID
        label_id = retrieve_linear_issue_label_id("Bug")

    issue_id = create_linear_issue(name, description, label_id)
    return issue_id
        

def check_new_issue_against_existing(script_args):
    """
    Queries all existing active issues and determines if the new issue presented is completely new or if it is the extension of a previous issue using GPT4 Assistant.
    
    Args:
    - script_args: The arguments from the script processing assistant, containing the type of request, the name of the issue, and the description of the issue.

    Returns:
    - linear_args: The arguments to be used in the Linear API call. 
        'is_new_issue': If the new issue is completely new, set to True, else False 
        'old_issue_id': Field set to the ID of the existing issue
        'description': Field set to the comment to add to the existing issue, based on what relevant new context the new issue adds to that existing issue.
    """

    new_issue_prompt = "The following the existing issues in Linear.\n\n"
    for issue in get_all_active_issues():
        new_issue_prompt += f"Issue id: {issue['id']}\n" + f"Issue title: {issue['title']}\n" +  f"Issue description: {issue['title']}\n\n"

    new_issue_prompt += "This is the new issue: \n\n" + f"Issue title: {script_args['name']}\n" + f"Issue description: {script_args['description']}\n\n"

    linear_comparison_thread = client.beta.threads.create()
    linear_comparison_thread_id = linear_comparison_thread.id

    linear_message = client.beta.threads.messages.create(
        thread_id=linear_comparison_thread_id,
        role="user",
        content=new_issue_prompt
    )

    linear_comparison_run = client.beta.threads.runs.create(
        thread_id=linear_comparison_thread_id,
        assistant_id=linear_issue_matching_assistant.id
    )

    linear_comparison_run = wait_on_run(linear_comparison_run, client, linear_comparison_thread_id)
    
    linear_args = None
    if linear_comparison_run.status == "requires_action":
        linear_tool_call = linear_comparison_run.required_action.submit_tool_outputs.tool_calls[0]
        linear_args = json.loads(linear_tool_call.function.arguments)
    
    # Delete the linear comparison assistant
    client.beta.assistants.delete(linear_issue_matching_assistant.id)
    return linear_args


def process_transcript(transcript):
    """
    Processes the transcript and creates a Linear ticket based on if GPT4 Assistant thinks it is a feature request, bug report, or neither.

    Args:
    - transcript: The transcript of the conversation between the customer and the customer service agent.

    Returns:
    - ticket: The ID of the Linear ticket that was created. If no ticket was created, this is None.
    """
    script_thread = client.beta.threads.create()
    script_thread_id = script_thread.id

    script_message = client.beta.threads.messages.create(
        thread_id=script_thread_id,
        role="user",
        content=transcript
    )

    script_run = client.beta.threads.runs.create(
        thread_id=script_thread_id,
        assistant_id=script_processing_assistant.id
    )

    script_run = wait_on_run(script_run, client, script_thread_id)

    if script_run.status == "requires_action":
        script_tool_call = script_run.required_action.submit_tool_outputs.tool_calls[0]
        script_args = json.loads(script_tool_call.function.arguments)

        if script_args["request_type"] == "neither":
            print("Transcript did not include bug or feature request.")
            return None
        
        linear_args = check_new_issue_against_existing(script_args)

        if linear_args is None:
            # Default to adding new issue to Linear
            logging.error("Unable to compare to existing issues. Defaulting to adding new issue to Linear.")
            ticket = invoke_linear_api(script_args["request_type"], script_args["name"], script_args["description"])
            if ticket:
                print("Linear ticket created with ID: ", ticket)

        elif linear_args["is_new_issue"]:
            # Add new issue to Linear
            logging.info("New issue is not related to any existing issues.")
            ticket = invoke_linear_api(script_args["request_type"], script_args["name"], script_args["description"])
            if ticket:
                print("Linear ticket created with ID: ", ticket)
        else:
            # Add comment to existing issue
            logging.info("New issue is related to an existing issue.")
            updated = add_comment_to_linear_issue(linear_args['old_issue_id'], linear_args['description'])
            if updated:
                print("Ticket updated with comment")
            else:
                logging.error("Unable to update ticket with comment.")

    elif script_run.status != "completed":
        # Mark the script processing run as failed
        logging.error("Run did not complete successfully.")

    # delete script processing assistant
    client.beta.assistants.delete(script_processing_assistant.id)



if __name__ == '__main__':
    transcript = """
    [Customer Service Agent (CSA)]: Good morning, thank you for calling XYZ SaaS Support. This is Sarah, how may I assist you today?

    [Customer (C)]: Hi Sarah, this is John from ABC Corporation. I've been using your platform for a while now, and I have a feature request that I believe would greatly benefit our workflow.

    [CSA]: Of course, John. We're always looking to improve our platform based on our users' needs. What feature would you like to see implemented?

    [C]: Well, currently, we're finding it challenging to track the progress of multiple projects simultaneously. It would be incredibly helpful if we could have a dashboard that provides a comprehensive overview of all ongoing projects with their respective statuses and timelines.

    [CSA]: I see, having a centralized dashboard for project management sounds like a valuable addition. Could you please elaborate on the specific functionalities or metrics you'd like to see displayed on this dashboard?

    [C]: Certainly. We'd need to see the project name, assigned team members, current status (such as in progress, completed, on hold), upcoming deadlines, and any critical milestones. Additionally, it would be beneficial to have a filter option to view projects based on different criteria like priority or department.

    [CSA]: That sounds like a robust solution for your project management needs. I'll make sure to pass on your feedback to our development team for consideration. Is there anything else you'd like to add or any other pain points you've encountered?

    [C]: No, that covers it for now. I appreciate your attention to our suggestion, Sarah.

    [CSA]: You're very welcome, John. We truly value your feedback, as it helps us tailor our product to better suit your needs. If you have any further questions or concerns in the future, don't hesitate to reach out. Have a great day!

    [C]: Thank you, Sarah. You too, goodbye.
    """
    process_transcript(transcript=transcript)
