# backend_ws.py
from dotenv import load_dotenv, find_dotenv
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage
from prompts.whatsapp_template_prompt import template_prompt
import uvicorn
import json

# Load environment variables
load_dotenv(find_dotenv(), override=True)
GOOGLE_API_KEY = os.environ.get("GEMINI_API_KEY")

# Initialize Gemini model
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=GOOGLE_API_KEY
)

chat_history = []
executor = ThreadPoolExecutor(max_workers=1)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Helper to run blocking LLM call asynchronously
async def call_llm(prompt):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, llm.invoke, prompt)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Client connected via WebSocket")
    try:
        while True:
            data = await websocket.receive_text()
            chat_history.append(HumanMessage(content=data))

            # Prepare prompt
            prompt = template_prompt.invoke({"user_message": data})

            # Call LLM without blocking
            response = await call_llm(prompt)
            chat_history.append(AIMessage(content=response.content))

            # Sanitize and validate the LLM response
            raw_output = response.content.strip()
            print("Raw LLM output:", raw_output)
            # Detect if LLM wrapped response in markdown or invalid format
            if raw_output.startswith("```") or "```json" in raw_output:
                body_text = "⚠️ An error occurred while generating this response. Please try again."
                llm_buttons = []
            else:
                try:
                    llm_data = json.loads(raw_output)
                    body_text = llm_data.get("Body", raw_output)
                    llm_buttons = llm_data.get("Buttons", [])
                except json.JSONDecodeError:
                    body_text = "⚠️ An error occurred while generating this response. Please try again."
                    llm_buttons = []

            # Build final message JSON
            response_json = {
                "content":  body_text,
                "buttons": llm_buttons
            }

            await websocket.send_text(json.dumps(response_json))
    except Exception as e:
        print("Connection closed:", e)



if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8765)
