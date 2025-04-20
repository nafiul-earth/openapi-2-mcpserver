import json
import httpx
import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Any
from dotenv import load_dotenv
import uvicorn

# Load environment variables
load_dotenv()

app = FastAPI()

# Load API_DEFINITIONS from environment variables
API_DEFINITIONS = [
  {
    "name":"watsonx-ai-cp",
    "url":"https://cloud.ibm.com/apidocs/watsonx-ai-cp/watsonx-ai-cp-2.1.2.json",
    "version":"2.1.2"
  },
  {
    "name":"watsonx-ai",
    "url":"https://cloud.ibm.com/apidocs/watsonx-ai.json"
  },
  {
    "name":"machine-learning-cp",
    "url":"https://cloud.ibm.com/apidocs/machine-learning-cp/machine-learning-cp-5.1.2.json",
    "version":"5.1.2"
  },
  {
    "name":"ai-openscale",
    "url":"https://cloud.ibm.com/apidocs/ai-openscale.json"
  },
  {
   "name":"ai-openscale",
    "url":"https://cloud.ibm.com/apidocs/machine-learning.json"
  }

]

class ToolCallInput(BaseModel):
    tool_name: str
    input: Dict[str, Any]

# In-memory registry of tools
tool_registry = {}

async def fetch_openapi_spec(url):
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()

def generate_tools_from_openapi(openapi: Dict[str, Any], prefix: str):
    base_url = openapi.get("servers", [{}])[0].get("url", "")
    paths = openapi.get("paths", {})
    if  not paths:
         raise ValueError(f"Path is empty or invalid for {service_name}")
    
    for path, methods in paths.items():
        for method, details in methods.items():
            if not isinstance(details, dict):
                print(f"Skipping invalid details in path '{path}' method '{method}'")
                continue
            else:
                operation_id = details.get("operationId") or f"{method}_{path.replace('/', '_')}"
                summary = details.get("summary", "")
                tool_name = f"{prefix}_{operation_id}"

                def make_tool(p, m, base):
                    async def tool_func(input_data):
                        region = input_data.get("region", "us-south")
                        headers = input_data.get("headers", {})
                        body = input_data.get("body", None)
                        params = input_data.get("params", {})
                        formatted_path = p
                        for key, value in params.items():
                            formatted_path = formatted_path.replace(f"{{{key}}}", value)
                        url = f"{base}{formatted_path}"
                        async with httpx.AsyncClient() as client:
                            req = client.build_request(m.upper(), url, headers=headers, json=body, params=params)
                            res = await client.send(req)
                            return {"status_code": res.status_code, "body": res.text}
                    return tool_func

                tool_registry[tool_name] = make_tool(path, method, base_url)

@app.post("/invoke")
async def invoke_tool(call: ToolCallInput):
    tool_name = call.tool_name
    input_data = call.input

    if tool_name not in tool_registry:
        return JSONResponse(status_code=404, content={"error": "Tool not found"})

    tool_func = tool_registry[tool_name]
    try:
        result = await tool_func(input_data)
        return JSONResponse(content={"output": result})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/tools")
async def list_tools():
    return JSONResponse(content={"tools": list(tool_registry.keys())})

@app.on_event("startup")
async def startup():
    for api in API_DEFINITIONS:
        try:
            print(f"Loading {api['name']} from {api['url']}")
            openapi = await fetch_openapi_spec(api["url"])
            generate_tools_from_openapi(openapi, api["name"])
        except Exception as e:
            print(f"Failed to load {api['name']}: {e}")
    print(f"Registered tools: {list(tool_registry.keys())})")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)