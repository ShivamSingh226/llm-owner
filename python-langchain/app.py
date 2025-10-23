# backend_ws.py
from dotenv import load_dotenv, find_dotenv
import os
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from prompts.whatsapp_template_prompt import template_prompt
import uvicorn

# Load environment variables
load_dotenv(find_dotenv(), override=True)
GOOGLE_API_KEY = os.environ.get("GEMINI_API_KEY")

# Initialize Gemini model
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=GOOGLE_API_KEY
)

executor = ThreadPoolExecutor(max_workers=2)
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def call_llm(messages):
    """Call the LLM asynchronously via ThreadPoolExecutor."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, llm.invoke, messages)


def safe_parse_json(raw_output):
    """Try parsing AI output to JSON safely."""
    try:
        return json.loads(raw_output)
    except json.JSONDecodeError:
        start = raw_output.find("{")
        end = raw_output.rfind("}") + 1
        if start != -1 and end != -1:
            try:
                return json.loads(raw_output[start:end])
            except:
                pass
        # fallback if parsing fails
        return {"Body": "⚠️ I couldn’t process that message correctly. Please try again.", "Buttons": []}


class ConversationState:
    """Stores conversation history per WebSocket connection."""
    def __init__(self):
        self.history = []
        self.last_sent_message = {}  # track last sent content+buttons
        self.current_buttons = []  # store the current buttons for dynamic updates


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("✅ Client connected")

    state = ConversationState()

    # Add system message once at start
    system_message_list = template_prompt.format_messages(user_message="")
    system_message = system_message_list[0]  # SystemMessage object
    state.history.append(system_message)

    try:
        while True:
            user_input = await websocket.receive_text()
            user_input = user_input.strip()

            lower_input = user_input.lower()

            # --- Handle dynamic button removal ---
            if "remove all buttons" in lower_input:
                state.current_buttons = []
            elif "remove quick reply" in lower_input:
                state.current_buttons = [b for b in state.current_buttons if b["type"] != "Quick Reply"]
            elif "remove cta" in lower_input or "remove call to action" in lower_input:
                state.current_buttons = [b for b in state.current_buttons if b["type"] != "Call to Action"]
            elif "remove button" in lower_input:
                # Remove by button text if specified
                state.current_buttons = [b for b in state.current_buttons if b["text"].lower() not in lower_input]

            # --- Add user input to history ---
            state.history.append(HumanMessage(content=user_input))

            # --- Call AI ---
            try:
                response = await asyncio.wait_for(call_llm(state.history), timeout=15)
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({
                    "content": "⚠️ The AI took too long to respond. Please try again.",
                    "buttons": state.current_buttons
                }, ensure_ascii=False))
                continue

            raw_output = response.content.strip()
            print("🤖 AI Response:", raw_output)  # Print AI response in console

            data = safe_parse_json(raw_output)

            # --- Update current buttons if AI generated new ones ---
            ai_buttons = data.get("Buttons", [])
            if ai_buttons:
                state.current_buttons = ai_buttons

            # --- Detect dynamic follow-up prompts ---
            body_lower = data.get("Body", "").lower()
            # If Buttons are empty and Body asks for text/URL, treat as follow-up
            is_followup = not data.get("Buttons") and (
                "provide" in body_lower or "text" in body_lower or "url" in body_lower
            )

            frontend_message = {
                "content": data.get("Body", ""),
                "buttons": [] if is_followup else state.current_buttons
            }

            # --- Send only if content or buttons changed ---
            content_changed = frontend_message["content"] != state.last_sent_message.get("content")
            buttons_changed = frontend_message["buttons"] != state.last_sent_message.get("buttons")

            if content_changed or buttons_changed:
                await websocket.send_text(json.dumps(frontend_message, ensure_ascii=False))
                state.last_sent_message = {
                    "content": frontend_message["content"],
                    "buttons": frontend_message["buttons"].copy()
                }

            # --- Append AI response to history ---
            state.history.append(AIMessage(content=raw_output))

    except Exception as e:
        print("❌ Connection closed:", e)
        await websocket.close()


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8765)
