from dotenv import load_dotenv, find_dotenv
import os
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from prompts.whatsapp_template_prompt import template_prompt
from utils.cost_calculator import calculate_cost
import uvicorn

# Load environment variables
load_dotenv(find_dotenv(), override=True)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# Initialize Gemini model
llm = ChatOpenAI(
    model="gpt-4o-mini",
    openai_api_key=OPENAI_API_KEY
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


# ✅ Universal JSON sanitizer
def clean_json_output(raw_text: str):
    """Cleans and extracts valid JSON from Gemini responses, even if wrapped in ```json fences."""
    if not raw_text:
        return None

    text = raw_text.strip()

    # Remove markdown fences if present
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()

    # Handle multiple JSON objects if concatenated
    try:
        if text.count('}{') > 0:
            parts = text.replace('}{', '}|||{').split('|||')
            return [json.loads(p.strip()) for p in parts]
        else:
            return [json.loads(text)]
    except json.JSONDecodeError as e:
        print("⚠️ JSON cleaning failed:", e, "Raw text:", raw_text)
        return None


async def call_llm(messages):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, llm.invoke, messages)


class ConversationState:
    """Stores conversation history per WebSocket connection."""
    def __init__(self):
        self.history = []
        self.last_sent_body = None
        self.last_sent_buttons = None
        self.awaiting_followup = False
        self.last_category_code = None
        self.total_spent=0.0


async def detect_intent(user_input: str):
    """Use Gemini to classify user's intent (positive, negative, neutral)."""
    intent_prompt = [
        SystemMessage(content="You are an intent classifier. Output JSON only."),
        HumanMessage(content=f"""
            Determine if this user message expresses positive, negative, or neutral intent.
            Examples:
            - 'yes', 'ok', 'do it', 'sure', 'yep', 'alright', 'fine' → positive
            - 'no', 'not now', 'skip', 'maybe later' → negative
            - other unclear ones → neutral

            Respond only as JSON:
            {{
                "intent": "positive" | "negative" | "neutral"
            }}

            User message: "{user_input}"
        """)
    ]
    response = await call_llm(intent_prompt)
    print("The intent detection: 💰💰💰 ",response);
    try:
        cleaned = clean_json_output(response.content.strip())
        if cleaned and isinstance(cleaned, list):
            return cleaned[0].get("intent", "neutral")
    except Exception as e:
        print("⚠️ Intent parsing error:", e)
    return "neutral"


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("✅ Client connected")

    state = ConversationState()

    # Initialize system message
    from constants.language_constants import LANGUAGE_LIST
    messages = template_prompt.format_messages(user_message="",
                                               LANGUAGE_LIST=LANGUAGE_LIST)
    state.history.append(messages[0])  # SystemMessage

    try:
        while True:
            user_input = await websocket.receive_text()
            user_input = user_input.strip()

            # 🧠 Check if this message is a response to a suggestion
            if state.last_sent_body and "consider adding a call-to-action button" in state.last_sent_body.lower():
                user_intent = await detect_intent(user_input)

                if user_intent == "positive":
                    print("✅ User accepted suggestion – adding buttons automatically.")
                    modified_template = {
                        "Body": state.last_sent_body,
                        "Buttons": [
                            {"type": "Call to Action", "text": "Shop Now", "url": "www.google.com"},
                            {"type": "Quick Reply", "text": "Tell me more", "url": ""}
                        ]
                    }
                    await websocket.send_text(json.dumps(modified_template))
                    state.last_sent_buttons = modified_template["Buttons"]
                    continue

                elif user_intent == "negative":
                    print("❌ User declined suggestion.")
                    await websocket.send_text(json.dumps({
                        "Body": "No problem! Let me know if you'd like to modify the template later.",
                        "Buttons": []
                    }))
                    continue

            # Add user input to history
            state.history.append(HumanMessage(content=user_input))

            # Call AI for new template generation
            response = await call_llm(state.history)
            raw_output = response.content.strip()
            print("AI Raw Output:", raw_output)
            print("Response is: ", response)
            # --- START ADDING TOKEN INFORMATION HERE (Location 1) ---
            
            # --- TOKEN USAGE PRINTING (MAIN) ---
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                usage = response.usage_metadata
                input_tokens = usage.get("input_tokens", 0)
                output_tokens = usage.get("output_tokens", 0)

                print(f"💰 Usage (Main): Input={input_tokens}, Output={output_tokens}")
                cost_details=calculate_cost(input_tokens,output_tokens)
                print(f"💰 Cost (Main) ₹: {cost_details}")

            
            # print("Raw cleaned response:", cleaned)

            try:
                data_list = clean_json_output(raw_output)
                if not data_list:
                    raise ValueError("Invalid JSON from model")
                

                # Get tokens if available
                tokens = {
                    "input": input_tokens if 'input_tokens' in locals() else 0,
                    "output": output_tokens if 'output_tokens' in locals() else 0,
                    "total_cost":cost_details["total_cost"]
                }

                for data in data_list:
                    # Validate schema
                    if  "Body" not in data or "Buttons" not in data:
                        raise ValueError("JSON missing 'categoryCode', 'Body' or 'Buttons' keys")
                    state.total_spent+=cost_details["total_cost"]
                    data["total_spent"]=state.total_spent
                    data["tokens"]=tokens
                    # Check if this is a follow-up suggestion (no buttons)
                    is_followup = (len(data["Buttons"]) == 0) and (state.last_sent_body is not None)

                    # Send only if Body or Buttons changed
                    if (data["Body"] != state.last_sent_body) or (data.get("Buttons", []) != state.last_sent_buttons):
                        await websocket.send_text(json.dumps(data))
                        state.last_sent_body = data["Body"]
                        state.last_sent_buttons = data.get("Buttons", [])
                        # state.last_category_code = data["categoryCode"]

                    # Append AI response to history
                    state.history.append(AIMessage(content=json.dumps(data)))

                    # If not a follow-up, generate dynamic follow-up suggestion
                    if not is_followup:
                        follow_up_prompt = [
                            SystemMessage(content="""You are a WhatsApp template AI assistant. Only output valid JSON.
                                          
                                          IMPORTANT RULE:
                                          - The template supports limit number of buttons.
                                          - Allowed button limits(hard and strict rules):
                                            - Maximum total buttons = 10.
                                            - Maximum URL buttons = 2.
                                            - Maximum PHONE_NUMBER buttons = 1.
                                            - Maximum COPY_CODE buttons = 1.
                                            - Remaining buttons (up to total 10) must be QUICK_REPLY.
                                          - Never suggest adding more buttons if the user has already reached these limits.
                                          - If user at anytime prompts to add more buttons than the above-prescribed limits, generate templates with maximum allowed buttons only as per the above rules.For example, if user asks to add 3 URL buttons, generate template with only 2 URL buttons and ignore the rest.Similarly, if user asks to add 2 PHONE_NUMBER buttons, generate template with only 1 PHONE_NUMBER button and ignore the rest.COPY_CODE button limit is 1 as well.
                                          - After generating template with maximum allowed buttons, inform user regarding the prescribed button limits and continue with your suggestion in the same JSON.
                                          
                                          """),
                            HumanMessage(content=f"""
                                I just generated this template:
                                {json.dumps(data)}

                               

                                When the number of buttons to be added by the user and also the type of buttons exceeds the allowed limits,after generating the template with maximum buttons as per the precribed limit above,inform user about the prescribed button limits and never suggest adding more buttons in the same JSON body of suggestion which you are going to send.


                                Suggest one friendly follow-up question or suggestion to improve this template (Body or buttons).
                                
                                If the Buttons array is empty, suggest user to add CTA or quick reply buttons.
                                Don't start with ```json or any markdown. It's very important.
                                Output JSON only in this schema:
                                {{
                                    
                                    "Body": "<suggestion/question text>",
                                    "Buttons": []
                                }}
                            """)
                        ]
                        followup_response = await call_llm(follow_up_prompt)
                        raw_followup = followup_response.content.strip()
                        print("The followup_response is: " ,followup_response );
                        if hasattr(followup_response, "usage_metadata") and followup_response.usage_metadata:
                            usage = followup_response.usage_metadata
                            input_tokens = usage.get("input_tokens", 0)
                            output_tokens = usage.get("output_tokens", 0)

                            print(f"💰 Usage (Follow-up): Input={input_tokens}, Output={output_tokens}")
                            cost_details=calculate_cost(input_tokens,output_tokens)
                            print(f"💰 Cost (Follow-up) ₹: {cost_details}")
                        try:
                            followup_data = clean_json_output(raw_followup)
                            if not followup_data:
                                raise ValueError("Invalid follow-up JSON")
                            followup_json = followup_data[0]
                            followup_json["tokens"] = {
                                "input": input_tokens if 'input_tokens' in locals() else 0,
                                "output": output_tokens if 'output_tokens' in locals() else 0,
                                "total_cost":cost_details["total_cost"]
                            }
                            state.total_spent+=cost_details["total_cost"]
                            followup_json["total_spent"]=state.total_spent
                            await websocket.send_text(json.dumps(followup_json))
                            state.last_sent_body = followup_json["Body"]
                            state.last_sent_buttons = []

                        except Exception as e:
                            print("⚠️ Follow-up Parse Error:", e, "Raw follow-up:", raw_followup)

            except Exception as e:
                print("⚠️ JSON parsing error:", e)
                await websocket.send_text(json.dumps({
                    "Body": "⚠️ I couldn’t process that message correctly. Please try again.",
                    "Buttons": []
                }))

    except Exception as e:
        print("❌ Connection closed:", e)
        await websocket.close()


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8765)
