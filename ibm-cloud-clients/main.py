import requests
import os
from dotenv import load_dotenv
load_dotenv()
# IBM Cloud Credentials
API_KEY = os.environ["IBM_CLOUD_API_KEY"]
COS_REGION = os.environ["COS_REGION"]
COS_SERVICE_INSTANCE_ID = os.environ["COS_SERVICE_INSTANCE_ID"] 

# MCP Server URL
MCP_URL = os.environ["MCP_URL"]


def get_iam_token():
    iam_url = "https://iam.cloud.ibm.com/identity/token"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "apikey": API_KEY,
        "grant_type": "urn:ibm:params:oauth:grant-type:apikey"
    }
    response = requests.post(iam_url, headers=headers, data=data)
    response.raise_for_status()
    return response.json()["access_token"]


def list_buckets(token):
    tool_call = {
        "tool_name": "ListBuckets",
        "input": {
            "headers": {
                "Authorization": f"Bearer {token}",
                "ibm-service-instance-id": COS_SERVICE_INSTANCE_ID
            }
        }
    }
    response = requests.post(MCP_URL, json=tool_call)
    print("List Buckets:", response.json())


def create_bucket(token, bucket_name):
    tool_call = {
        "tool_name": "CreateBucket",
        "input": {
            "region": "us-south",
            "headers": {
                "Authorization": f"Bearer {token}",
                "ibm-service-instance-id": COS_SERVICE_INSTANCE_ID
            },
            "params": {
                "Bucket": bucket_name
            }
        }
    }
    response = requests.post(MCP_URL, json=tool_call)
    print(f"Create Bucket '{bucket_name}':", response.json())


if __name__ == "__main__":
    iam_token = get_iam_token()
    list_buckets(iam_token)
    create_bucket(iam_token, "demo-mcp-nafiul-earth")

