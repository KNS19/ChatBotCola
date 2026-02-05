import sys
import re
import intent_bot
import database
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
# MODELS
# =====================
class ChatRequest(BaseModel):
    message: str

class ComplaintRequest(BaseModel):
    issue: str
    department: str
    location: str
    detail: str

# =====================
# CHAT API
# =====================
@app.post("/chat")
async def chat_api(req: ChatRequest):
    text = req.message.strip()

    # ✅ ติดตามเฉพาะรูปแบบ: "ติดตาม 123" หรือ "ติดตาม #123"
    match = re.fullmatch(r"ติดตาม\s*#?(\d+)", text)
    if match:
        cid = int(match.group(1))

        conn = database.get_db()
        c = conn.cursor()
        c.execute("""
            SELECT issue, department, location, detail, status
            FROM complaints WHERE id=?
        """, (cid,))
        row = c.fetchone()
        conn.close()

        if row:
            return {
                "reply": (
                    f"📄 รายละเอียดคำร้อง #{cid}\n"
                    f"ปัญหา: {row[0]}\n"
                    f"กอง: {row[1]}\n"
                    f"สถานที่: {row[2]}\n"
                    f"รายละเอียด: {row[3]}\n"
                    f"สถานะ: {row[4]}"
                )
            }
        else:
            return {"reply": "❌ ไม่พบเลขคำร้องนี้ค่ะ"}

    #  ถ้าไม่ใช่รูปแบบติดตาม → chatbot ปกติ
    reply = intent_bot.chatbot_response(text, threshold=0.2)
    return {"reply": reply}


# =====================
# CREATE COMPLAINT
# =====================
@app.post("/complaint")
async def create_complaint(req: ComplaintRequest):
    conn = database.get_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO complaints (issue, department, location, detail)
        VALUES (?, ?, ?, ?)
    """, (req.issue, req.department, req.location, req.detail))
    conn.commit()
    complaint_id = c.lastrowid
    conn.close()

    return {
        "complaint_id": complaint_id,
        "message": f" รับเรื่องเรียบร้อยค่ะ เลขคำร้องของคุณคือ #{complaint_id}\n\nสามารถใช้คำว่า '{complaint_id}' เพื่อดูสถานะได้ค่ะ"
    }

# =====================
# LINE WEBHOOK
# =====================
@app.post("/callback")
async def handle_callback(request: Request):
    signature = request.headers.get("X-Line-Signature")
    body = (await request.body()).decode("utf-8")

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
