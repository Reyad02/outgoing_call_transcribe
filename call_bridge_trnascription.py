import json
import os
import time
import threading
from flask import Flask, request, Response
from flask_sock import Sock
import ngrok
from twilio.rest import Client
from dotenv import load_dotenv
from openai import OpenAI
import time
import google.generativeai as genai


load_dotenv()

client_of_AI = OpenAI() 
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

gemini_model = genai.GenerativeModel("gemini-2.5-flash")  

PORT = 5000
DEBUG = True
VOICE_ROUTE = '/voice'

# Twilio credentials
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
api_key = os.getenv('TWILIO_API_KEY_SID')
api_secret = os.getenv('TWILIO_API_SECRET')
TWILIO_NUMBER = os.getenv('TWILIO_NUMBER')
TARGET_NUMBER = os.getenv('TARGET_NUMBER_2')
SECOND_NUMBER = os.getenv('TARGET_NUMBER_1')

client = Client(api_key, api_secret, account_sid)

app = Flask(__name__)
sock = Sock(app)

@app.route(VOICE_ROUTE, methods=["POST"])
def voice_response():
    xml = f"""
<Response>
    <Say>Dialing the second number now...</Say>
    <Start>
        <Transcription statusCallbackUrl="https://58f7b184a010.ngrok-free.app/transcription-webhook" track="both_tracks"/>
    </Start>
    <Dial>
        <Number>{SECOND_NUMBER}</Number>
    </Dial>
</Response>

""".strip()
    return Response(xml, mimetype='text/xml')

@app.route('/transcription-webhook', methods=['POST'])
def transcription_webhook():
    data = request.form.to_dict()
    transcription_data = data.get('TranscriptionData')
    track = data.get('Track')
    
    if transcription_data:
        td = json.loads(transcription_data)
        transcript = td.get('transcript')
        confidence = td.get('confidence')

        if track == 'inbound_track':
            speaker = "User A"
            print(f"{speaker}: {transcript} (Confidence: {confidence})")

        elif track == 'outbound_track':
            speaker = "User B"
            print(f"{speaker}: {transcript} (Confidence: {confidence})")
            # Send User B's message to OpenAI for a response suggestion
            # suggestion = get_response_suggestion(transcript)
            suggestion_from_gemini=get_response_suggestion_gemini(transcript)
            # print(f"Suggested reply to User A from openai: {suggestion}\n\n")
            print(f"Suggested reply to User A from gemini: {suggestion_from_gemini}")

        else:
            speaker = "Unknown"
            print(f"{speaker}: {transcript} (Confidence: {confidence})")

    return ('', 204)


def get_response_suggestion(agent_transcript):
    try:
        start_time = time.time()
        response = client_of_AI.chat.completions.create(
            model="gpt-4o", 
            messages=[
                {"role": "system", "content": "You are a helpful customer support assistant. Based on what the agent just said, suggest what the agent should say next to the customer."},
                {"role": "user", "content": agent_transcript}
            ],
            temperature=0.7,
            max_tokens=100
        )
        
        end_time = time.time() 
        duration = end_time - start_time
        
        print(f"👍👍 Response time from openai: {duration:.2f} seconds")

        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error with OpenAI API: {e}")
        return "[Error getting suggestion]"
    
def get_response_suggestion_gemini(agent_transcript):
    try:
        start_time = time.time()

        # Generate content
        response = gemini_model.generate_content(
            f"Suggest a short, simple sentence the agent should say next. User said: {agent_transcript}",
            generation_config=genai.types.GenerationConfig(
                # max_output_tokens=100,     
                temperature=0.7,          
            )
        )

        end_time = time.time()
        duration = end_time - start_time
        print(f"❤️❤️ Response time from the gemini: {duration:.2f} seconds")
        print(f"\nGemini Respnose: {response}\n")


        return response.text.strip()

    except Exception as e:
        print(f"Error with Gemini API: {e}")
        return "[Error getting suggestion]"

def run_flask():
    app.run(host="0.0.0.0", port=PORT, debug=DEBUG, use_reloader=False)

if __name__ == "__main__":
    try:
        # listener = ngrok.forward(PORT, authtoken_from_env=True, proto="http,https,tcp")
        NGROK_URL = "https://58f7b184a010.ngrok-free.app"
        print(f"Ngrok tunnel running at: {NGROK_URL}")

        flask_thread = threading.Thread(target=run_flask)
        flask_thread.daemon = True
        flask_thread.start()
        time.sleep(2)

        print(f"Dialing {TARGET_NUMBER} from {TWILIO_NUMBER}...")
        call = client.calls.create(
            from_=TWILIO_NUMBER,
            to=TARGET_NUMBER,
            url=f"{NGROK_URL}{VOICE_ROUTE}"
        )
        print(f"Call initiated. SID: {call.sid}")

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        ngrok.disconnect()