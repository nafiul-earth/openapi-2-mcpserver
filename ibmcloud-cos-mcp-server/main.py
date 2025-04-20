import json
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Any
import uvicorn

from dotenv import load_dotenv
load_dotenv()

app = FastAPI()

# Load OpenAPI spec from IBM COS API
OPENAPI_URL = "https://cloud.ibm.com/apidocs/cos/cos-compatibility.json"

class ToolCallInput(BaseModel):
    tool_name: str
    input: Dict[str, Any]

# In-memory registry of tools
tool_registry = {}

async def fetch_openapi_spec():
    async with httpx.AsyncClient() as client:
        response = await client.get(OPENAPI_URL)
        response.raise_for_status()
        return response.json()

def generate_tools_from_openapi(openapi: Dict[str, Any]):
    paths = openapi.get("paths", {})
    for path, methods in paths.items():
        for method, details in methods.items():
            operation_id = details.get("operationId") or f"{method}_{path.replace('/', '_')}"
            summary = details.get("summary", "")

            # Create a basic tool function with a name and HTTP method
            def make_tool(p, m):
                async def tool_func(input_data):
                    region = input_data.get("region", "us-south")
                    headers = input_data.get("headers", {})
                    body = input_data.get("body", None)
                    params = input_data.get("params", None)
                    params = input_data.get("params", {})
                    formatted_path = p
                    for key, value in params.items():
                        formatted_path = formatted_path.replace(f"{{{key}}}", value)
                    url = f"https://s3.{region}.cloud-object-storage.appdomain.cloud{formatted_path}"
                    async with httpx.AsyncClient() as client:
                        req = client.build_request(m.upper(), url, headers=headers, json=body, params=params)
                        res = await client.send(req)
                        return {"status_code": res.status_code, "body": res.text}
                return tool_func

            tool_registry[operation_id] = make_tool(path, method)

@app.post("/invoke")
async def invoke_tool(call: ToolCallInput):
    tool_name = call.tool_name
    input_data = call.input
    print(input_data)
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
    openapi = await fetch_openapi_spec()
    generate_tools_from_openapi(openapi)
    print(f"Registered tools: {list(tool_registry.keys())}")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
