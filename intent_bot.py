# -*- coding: utf-8 -*-
import json
import numpy as np
import random
from pythainlp.tokenize import word_tokenize
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
import google.generativeai as genai
import os

# =====================
# Load intent data
# =====================
with open("intents.json", encoding="utf-8") as file:
    intent_data = json.load(file)

# =====================
# Gemini config
# =====================
API_KEYS = os.getenv("GEMINI_API_KEYS").split(",")

MODELS_TO_TRY = [
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash"
]

# =====================
# Prepare intent model
# =====================
patterns = []
tags = []
responses = {}

for intent in intent_data["intents"]:
    for pattern in intent["patterns"]:
        patterns.append(pattern)
        tags.append(intent["tag"])
    responses[intent["tag"]] = intent["responses"]

tokenized_patterns = [
    " ".join(word_tokenize(p, engine="newmm")) for p in patterns
]

vectorizer = TfidfVectorizer()
classifier = LogisticRegression(
    solver="lbfgs",
    max_iter=1000,
    multi_class="multinomial"
)
model = make_pipeline(vectorizer, classifier)
model.fit(tokenized_patterns, tags)

# =====================
# Intent prediction
# =====================
def predict_intent(user_input, threshold=0.5):
    tokenized_input = " ".join(word_tokenize(user_input, engine="newmm"))
    probs = model.predict_proba([tokenized_input])[0]
    idx = np.argmax(probs)
    confidence = probs[idx]

    if confidence >= threshold:
        return model.classes_[idx], confidence
    return None, confidence

# =====================
# Gemini with auto key + model switch
# =====================
def query_gemini(user_input):
    knowledge_base = json.dumps(intent_data, ensure_ascii=False, indent=2)

    prompt = f"""คุณเป็นเจ้าหน้าที่หญิงของเทศบาล คอยตอบคำถามและรับเรื่องร้องเรียนด้วยความสุภาพ 
ข้อมูลอ้างอิงของเทศบาล (อ้างอิงจาก intents.json):
{knowledge_base}

คำถามจากประชาชน: {user_input}

คำแนะนำในการตอบ:
1. หากคำถามตรงกับข้อมูลใน 'patterns' ให้ดึงคำตอบจาก 'responses' มาประยุกต์ใช้
2. ตอบให้กระชับและเป็นกันเอง
3. ไม้ต้องสวัสดีทุกรอบในการตอบก็ได้
4. ห้ามบอกว่าคือลูกค้าหรืออย่างอื่น ให้แทน User ว่าคุณ
5. ตอบให้เข้าใจง่าย
6. ห้ามตอบเรื่องศาสนา การเมือง พระมาหากษัตริย์ 
"""

    for api_key in API_KEYS:
        genai.configure(api_key=api_key)

        for model_name in MODELS_TO_TRY:
            try:
                print(f"Trying key={api_key[:8]}... model={model_name}")

                gemini_model = genai.GenerativeModel(model_name)
                response = gemini_model.generate_content(prompt)

                if response and response.text:
                    return response.text.strip()

            except Exception as e:
                err = str(e).lower()

                # quota / limit / resource exhausted
                if "quota" in err or "limit" in err or "resource" in err:
                    print("Quota hit → switching model/key")
                    continue

                print(f"Gemini error: {e}")
                continue

    return "ขอโทษค่ะ ขณะนี้มีผู้ใช้งานจำนวนมาก กรุณาลองใหม่ภายหลัง 🙏"

# =====================
# Chatbot main logic
# =====================
def chatbot_response(user_input, threshold=0.5):
    intent, confidence = predict_intent(user_input, threshold)

    if intent and confidence >= threshold:
        return random.choice(responses[intent]) + f" (ความมั่นใจ: {round(confidence, 2)})"
    else:
        return query_gemini(user_input)
