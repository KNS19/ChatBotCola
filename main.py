import sys
import intent_bot
from fastapi import Request, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from linebot.v3.webhook import WebhookParser
from linebot.v3.messaging import (
    AsyncApiClient,
    AsyncMessagingApi,
    Configuration,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import MessageEvent, TextMessageContent
import os

# =====================
# LINE CONFIG
# =====================
channel_secret = os.environ.get("LINE_CHANNEL_SECRET")
channel_access_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")

if not channel_secret or not channel_access_token:
    print("Missing LINE credentials")
    sys.exit(1)

configuration = Configuration(access_token=channel_access_token)
async_api_client = AsyncApiClient(configuration)
line_bot_api = AsyncMessagingApi(async_api_client)
parser = WebhookParser(channel_secret)

app = FastAPI()

# =====================
# WEB PAGE
# =====================
@app.get("/", response_class=HTMLResponse)
async def index():
    with open("templates/chat.html", encoding="utf-8") as f:
        return f.read()

# =====================
# WEB CHAT API
# =====================
class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    reply: str

@app.post("/chat", response_model=ChatResponse)
async def chat_api(req: ChatRequest):
    reply = intent_bot.chatbot_response(req.message, threshold=0.2)
    return {"reply": reply}

# =====================
# LINE WEBHOOK
# =====================
@app.post("/callback")
async def handle_callback(request: Request):
    signature = request.headers.get("X-Line-Signature")

    body = await request.body()
    body = body.decode("utf-8")

    try:
        events = parser.parse(body, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    for event in events:
        if not isinstance(event, MessageEvent):
            continue
        if not isinstance(event.message, TextMessageContent):
            continue

        user_text = event.message.text
        reply_text = intent_bot.chatbot_response(user_text, threshold=0.2)

        await line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            )
        )

    return "OK"
