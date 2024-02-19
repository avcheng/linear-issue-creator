import requests
import os
import json

from dotenv import load_dotenv

load_dotenv()
linear_api_key = os.environ.get('LINEAR_API_KEY')
LINEAR_API_ENDPOINT = "https://api.linear.app/graphql"

def retrieve_team_id():
    """
    Retrieves the ID of the Linear team.
    
    Returns:
    - team_id: The ID of the Linear team.
    """
    body = """
    query Teams {
        teams {
            nodes {
            id
            name
            }
        }
    }
    """
    response = requests.post(url=LINEAR_API_ENDPOINT, json={"query": body}, headers={'Authorization': linear_api_key})
    if response.status_code == 200:
        # For now, we are assuming there is only one team
        return json.loads(response.content)["data"]["teams"]["nodes"][0]["id"]
    else:
        return None
    
TEAM_ID = retrieve_team_id()


def retrieve_linear_issue_label_id(name):
    """
    Retrieves the ID of a Linear issue label based on the name of the label.
    
    Args:
    - name: The name of the Linear issue label to retrieve.
    
    Returns:
    - label_id: The ID of the Linear issue label. If the label does not exist, returns None.
    """

    body = """
    query IssueLabels {
        issueLabels(
            filter: {
            name: {
                eq: "%s"
            }
            }
        ) {
            nodes {
            id
            }
        }
    }
    """ % (name)
    response = requests.post(url=LINEAR_API_ENDPOINT, json={"query": body}, headers={'Authorization': linear_api_key})
    if response.status_code == 200:
        return json.loads(response.content)["data"]["issueLabels"]["nodes"][0]["id"]
    else:
        return None


def create_linear_issue(name, description, label_id):
    body = """
    mutation IssueCreate {
        issueCreate(
            input: {
                title: \"""%s\"""
                description: \"""%s\"""
                teamId: \"""%s\"""
                labelIds: ["%s"]
            }
        ) {
            success
            issue {
                id
                title
            }
        }
    }
    """ % (name, description, TEAM_ID, label_id)
    response = requests.post(url=LINEAR_API_ENDPOINT, json={"query": body}, headers={'Authorization': linear_api_key})
    if response.status_code == 200:
        return json.loads(response.content)["data"]["issueCreate"]["issue"]["id"]
    else:
        return None


def add_comment_to_linear_issue(issue_id, comment):
    body = """
    mutation CommentCreate {
        CommentCreate(
            input: {
                id: \"""%s\"""
                body: \"""%s\"""
            }
        ) {
            success
        }
    }
    """ % (issue_id, comment)
    response = requests.post(url=LINEAR_API_ENDPOINT, json={"query": body}, headers={'Authorization': linear_api_key})
    if response.status_code == 200:
        return True
    else:
        return False
    

def get_all_active_issues():
    body = """
    query Issues {
        issues(
            filter: {
                team: {
                    id: {
                      eq: "%s"
                    }
                }
            }
        ) {
            nodes {
                id
                title
                description
            }
        }
    }
    """  % (TEAM_ID)
    response = requests.post(url=LINEAR_API_ENDPOINT, json={"query": body}, headers={'Authorization': linear_api_key})
    if response.status_code == 200:
        return json.loads(response.content)["data"]["issues"]["nodes"]
    else:
        return None