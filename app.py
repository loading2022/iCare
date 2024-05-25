import os
import time
import threading
import queue
import azure.cognitiveservices.speech as speechsdk
from flask import Flask, render_template, request, jsonify, url_for, send_from_directory
import openai
import uuid
import requests
import json

region = 'eastus2'

app = Flask(__name__)
app.secret_key = 'JQDxzgL0hjIHBO-xcCwGMw' 

openai.api_key = os.getenv('OPENAI_API_KEY')
subscription_key = os.getenv('AZURE_SUBSCRIPTION_KEY')

# 線程安全的佇列用來存儲結果 URL
result_queue = queue.Queue()

def call_gpt(text):
    response = openai.ChatCompletion.create(
        model ="gpt-4o",
        messages=[
            {"role": "system", "content": "使用者為年長者，你須扮演一個陪伴年長者的角色，依據 user 內容給予適當回應，請以較口語化的方式回應，並請勿反駁使用者所說的內容，結果請以繁體中文"},
            {"role": "user", "content": text}
        ]
    )
    return response.choices[0].message.content

class ContinuousRecognizer:
    def __init__(self):
        self.speech_config = speechsdk.SpeechConfig(subscription=subscription_key, region=region)
        self.speech_config.speech_recognition_language="zh-TW"
        self.audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)
        self.recognizer = speechsdk.SpeechRecognizer(speech_config=self.speech_config, audio_config=self.audio_config)
        self.last_speech_time = time.time()
        self.timer = None
        self.audio_path = None

    def start(self):
        self.recognizer.recognized.connect(self.recognized)
        self.recognizer.start_continuous_recognition()

    def recognized(self, args):
        if args.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            self.last_speech_time = time.time()
            print("Recognized: {}".format(args.result.text))
            if self.timer:
                self.timer.cancel()
            self.timer = threading.Timer(3.0, self.respond, [args.result.text])
            self.timer.start()

    def respond(self, text):
        try:
            print(f"Responding to text: {text}")  # 確認此函數被調用
            response_text = call_gpt(text)
            print("GPT Response: {}".format(response_text))  # 檢查 GPT 回應
            result_url = create_did(response_text)
            print("Result URL: {}".format(result_url))  # 確認 URL
            result_queue.put(result_url)  # 將 URL 放入佇列中
        except Exception as e:
            print(f"Error in respond: {e}")  # 打印任何錯誤

def create_did(text):
    result_url = "https://d-id-talks-prod.s3.us-west-2.amazonaws.com/google-oauth2%7C105929470202191278895/tlk_cylcop6sef76SriF4Or7h/1716552186447.mp4?AWSAccessKeyId=AKIA5CUMPJBIK65W6FGA&Expires=1716638589&Signature=%2FAMUEa63lViaedVmoQGk%2FgqVDX4%3D"
    """
    url = "https://api.d-id.com/talks"

    payload = {
    "script": {
        "type": "text",
        "subtitles": "false",
        "provider": {
            "type": "microsoft",
            "voice_id": "zh-CN-XiaoxiaoNeural"
        },
        "ssml": "false",
        "input": text
    },
    "config": {
        "fluent": "false",
        "pad_audio": "0.0"
    },
    "source_url": "https://create-images-results.d-id.com/api_docs/assets/noelle.jpeg"
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": "Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6Ik53ek53TmV1R3ptcFZTQjNVZ0J4ZyJ9.eyJodHRwczovL2QtaWQuY29tL2ZlYXR1cmVzIjoiIiwiaHR0cHM6Ly9kLWlkLmNvbS9zdHJpcGVfcHJvZHVjdF9pZCI6InByb2RfTXRkY2RrM29nR3hkNlkiLCJodHRwczovL2QtaWQuY29tL3N0cmlwZV9jdXN0b21lcl9pZCI6ImN1c19ROXF5a0E4UThTWnR4SyIsImh0dHBzOi8vZC1pZC5jb20vc3RyaXBlX3Byb2R1Y3RfbmFtZSI6ImxpdGUtbW9udGgtNjQiLCJodHRwczovL2QtaWQuY29tL3N0cmlwZV9zdWJzY3JpcHRpb25faWQiOiJzdWJfMVBKWEdESnhFS1oyekF5blVMRldtVjF0IiwiaHR0cHM6Ly9kLWlkLmNvbS9zdHJpcGVfYmlsbGluZ19pbnRlcnZhbCI6Im1vbnRoIiwiaHR0cHM6Ly9kLWlkLmNvbS9zdHJpcGVfcGxhbl9ncm91cCI6ImRlaWQtbGl0ZSIsImh0dHBzOi8vZC1pZC5jb20vc3RyaXBlX3ByaWNlX2lkIjoicHJpY2VfMU5TYmR6SnhFS1oyekF5bmNYN1dRVWoxIiwiaHR0cHM6Ly9kLWlkLmNvbS9zdHJpcGVfcHJpY2VfY3JlZGl0cyI6IjY0IiwiaHR0cHM6Ly9kLWlkLmNvbS9jaGF0X3N0cmlwZV9zdWJzY3JpcHRpb25faWQiOiIiLCJodHRwczovL2QtaWQuY29tL2NoYXRfc3RyaXBlX3ByaWNlX2NyZWRpdHMiOiIiLCJodHRwczovL2QtaWQuY29tL2NoYXRfc3RyaXBlX3ByaWNlX2lkIjoiIiwiaHR0cHM6Ly9kLWlkLmNvbS9wcm92aWRlciI6Imdvb2dsZS1vYXV0aDIiLCJodHRwczovL2QtaWQuY29tL2lzX25ldyI6ZmFsc2UsImh0dHBzOi8vZC1pZC5jb20vYXBpX2tleV9tb2RpZmllZF9hdCI6IjIwMjQtMDUtMjNUMDg6NTI6NDUuMTc0WiIsImh0dHBzOi8vZC1pZC5jb20vb3JnX2lkIjoiIiwiaHR0cHM6Ly9kLWlkLmNvbS9hcHBzX3Zpc2l0ZWQiOlsiU3R1ZGlvIl0sImh0dHBzOi8vZC1pZC5jb20vY3hfbG9naWNfaWQiOiIiLCJodHRwczovL2QtaWQuY29tL2NyZWF0aW9uX3RpbWVzdGFtcCI6IjIwMjMtMTEtMjNUMDg6MTM6MjEuMTQ4WiIsImh0dHBzOi8vZC1pZC5jb20vYXBpX2dhdGV3YXlfa2V5X2lkIjoiYmo4eHpxODdkMiIsImh0dHBzOi8vZC1pZC5jb20vdXNhZ2VfaWRlbnRpZmllcl9rZXkiOiJ1c2dfQUU3QXhGWERucTdzOWtFYnJHbjR4IiwiaHR0cHM6Ly9kLWlkLmNvbS9oYXNoX2tleSI6InBlZTlNOUd0OE82eFAtRi1teXNjdSIsImh0dHBzOi8vZC1pZC5jb20vcHJpbWFyeSI6dHJ1ZSwiaHR0cHM6Ly9kLWlkLmNvbS9lbWFpbCI6IjExMXl6dWltYmlsYWJAZ21haWwuY29tIiwiaHR0cHM6Ly9kLWlkLmNvbS9wYXltZW50X3Byb3ZpZGVyIjoic3RyaXBlIiwiaXNzIjoiaHR0cHM6Ly9hdXRoLmQtaWQuY29tLyIsInN1YiI6Imdvb2dsZS1vYXV0aDJ8MTA1OTI5NDcwMjAyMTkxMjc4ODk1IiwiYXVkIjpbImh0dHBzOi8vZC1pZC51cy5hdXRoMC5jb20vYXBpL3YyLyIsImh0dHBzOi8vZC1pZC51cy5hdXRoMC5jb20vdXNlcmluZm8iXSwiaWF0IjoxNzE2NTQ1MjE1LCJleHAiOjE3MTY2MzE2MTUsInNjb3BlIjoib3BlbmlkIHByb2ZpbGUgZW1haWwgcmVhZDpjdXJyZW50X3VzZXIgdXBkYXRlOmN1cnJlbnRfdXNlcl9tZXRhZGF0YSBvZmZsaW5lX2FjY2VzcyIsImF6cCI6Ikd6ck5JMU9yZTlGTTNFZURSZjNtM3ozVFN3MEpsUllxIn0.OcGfh3TJ0uInXoEUmEp6ddTuYKrsEQw6zrraVxaNWnRy95LVG_339scDFhOQJbauMPiYDgW-BhYyq-dVKykKAwPmeWOnQbPHtaAx3BToAVT8r3Kxv52Nq7Hxr2L3VI6RuiQC3POPSiWUyr5B1NpS9nHLfAiThooyMZ3m1_oGPgwQfOUaotxJS95z39DEHDBNYdm35dNDDAQ275KxUQ_-WcLW6xAiJPiN79c2Uiuv11AR6S4M__juRbvtiTbAkrqr2IZ5W2ajdwj5FdFIvGYtUQv6_tW-jK4XXlxsEfuF2TSd1HnNJ_vOU4-3H8oONU0oLxxncgEJe10ttFnEjP-hFw"
    }

    response = requests.post(url, json=payload, headers=headers)
    response_json = json.loads(response.text)
    print(response_json)

    talk_id = response_json['id']
    url = "https://api.d-id.com/talks/"+talk_id

    headers = {
        "accept": "application/json",
        "authorization": "Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6Ik53ek53TmV1R3ptcFZTQjNVZ0J4ZyJ9.eyJodHRwczovL2QtaWQuY29tL2ZlYXR1cmVzIjoiIiwiaHR0cHM6Ly9kLWlkLmNvbS9zdHJpcGVfcHJvZHVjdF9pZCI6InByb2RfTXRkY2RrM29nR3hkNlkiLCJodHRwczovL2QtaWQuY29tL3N0cmlwZV9jdXN0b21lcl9pZCI6ImN1c19ROXF5a0E4UThTWnR4SyIsImh0dHBzOi8vZC1pZC5jb20vc3RyaXBlX3Byb2R1Y3RfbmFtZSI6ImxpdGUtbW9udGgtNjQiLCJodHRwczovL2QtaWQuY29tL3N0cmlwZV9zdWJzY3JpcHRpb25faWQiOiJzdWJfMVBKWEdESnhFS1oyekF5blVMRldtVjF0IiwiaHR0cHM6Ly9kLWlkLmNvbS9zdHJpcGVfYmlsbGluZ19pbnRlcnZhbCI6Im1vbnRoIiwiaHR0cHM6Ly9kLWlkLmNvbS9zdHJpcGVfcGxhbl9ncm91cCI6ImRlaWQtbGl0ZSIsImh0dHBzOi8vZC1pZC5jb20vc3RyaXBlX3ByaWNlX2lkIjoicHJpY2VfMU5TYmR6SnhFS1oyekF5bmNYN1dRVWoxIiwiaHR0cHM6Ly9kLWlkLmNvbS9zdHJpcGVfcHJpY2VfY3JlZGl0cyI6IjY0IiwiaHR0cHM6Ly9kLWlkLmNvbS9jaGF0X3N0cmlwZV9zdWJzY3JpcHRpb25faWQiOiIiLCJodHRwczovL2QtaWQuY29tL2NoYXRfc3RyaXBlX3ByaWNlX2NyZWRpdHMiOiIiLCJodHRwczovL2QtaWQuY29tL2NoYXRfc3RyaXBlX3ByaWNlX2lkIjoiIiwiaHR0cHM6Ly9kLWlkLmNvbS9wcm92aWRlciI6Imdvb2dsZS1vYXV0aDIiLCJodHRwczovL2QtaWQuY29tL2lzX25ldyI6ZmFsc2UsImh0dHBzOi8vZC1pZC5jb20vYXBpX2tleV9tb2RpZmllZF9hdCI6IjIwMjQtMDUtMjNUMDg6NTI6NDUuMTc0WiIsImh0dHBzOi8vZC1pZC5jb20vb3JnX2lkIjoiIiwiaHR0cHM6Ly9kLWlkLmNvbS9hcHBzX3Zpc2l0ZWQiOlsiU3R1ZGlvIl0sImh0dHBzOi8vZC1pZC5jb20vY3hfbG9naWNfaWQiOiIiLCJodHRwczovL2QtaWQuY29tL2NyZWF0aW9uX3RpbWVzdGFtcCI6IjIwMjMtMTEtMjNUMDg6MTM6MjEuMTQ4WiIsImh0dHBzOi8vZC1pZC5jb20vYXBpX2dhdGV3YXlfa2V5X2lkIjoiYmo4eHpxODdkMiIsImh0dHBzOi8vZC1pZC5jb20vdXNhZ2VfaWRlbnRpZmllcl9rZXkiOiJ1c2dfQUU3QXhGWERucTdzOWtFYnJHbjR4IiwiaHR0cHM6Ly9kLWlkLmNvbS9oYXNoX2tleSI6InBlZTlNOUd0OE82eFAtRi1teXNjdSIsImh0dHBzOi8vZC1pZC5jb20vcHJpbWFyeSI6dHJ1ZSwiaHR0cHM6Ly9kLWlkLmNvbS9lbWFpbCI6IjExMXl6dWltYmlsYWJAZ21haWwuY29tIiwiaHR0cHM6Ly9kLWlkLmNvbS9wYXltZW50X3Byb3ZpZGVyIjoic3RyaXBlIiwiaXNzIjoiaHR0cHM6Ly9hdXRoLmQtaWQuY29tLyIsInN1YiI6Imdvb2dsZS1vYXV0aDJ8MTA1OTI5NDcwMjAyMTkxMjc4ODk1IiwiYXVkIjpbImh0dHBzOi8vZC1pZC51cy5hdXRoMC5jb20vYXBpL3YyLyIsImh0dHBzOi8vZC1pZC51cy5hdXRoMC5jb20vdXNlcmluZm8iXSwiaWF0IjoxNzE2NTQ1MjE1LCJleHAiOjE3MTY2MzE2MTUsInNjb3BlIjoib3BlbmlkIHByb2ZpbGUgZW1haWwgcmVhZDpjdXJyZW50X3VzZXIgdXBkYXRlOmN1cnJlbnRfdXNlcl9tZXRhZGF0YSBvZmZsaW5lX2FjY2VzcyIsImF6cCI6Ikd6ck5JMU9yZTlGTTNFZURSZjNtM3ozVFN3MEpsUllxIn0.OcGfh3TJ0uInXoEUmEp6ddTuYKrsEQw6zrraVxaNWnRy95LVG_339scDFhOQJbauMPiYDgW-BhYyq-dVKykKAwPmeWOnQbPHtaAx3BToAVT8r3Kxv52Nq7Hxr2L3VI6RuiQC3POPSiWUyr5B1NpS9nHLfAiThooyMZ3m1_oGPgwQfOUaotxJS95z39DEHDBNYdm35dNDDAQ275KxUQ_-WcLW6xAiJPiN79c2Uiuv11AR6S4M__juRbvtiTbAkrqr2IZ5W2ajdwj5FdFIvGYtUQv6_tW-jK4XXlxsEfuF2TSd1HnNJ_vOU4-3H8oONU0oLxxncgEJe10ttFnEjP-hFw"
    }
    while True:
        response = requests.get(url, headers=headers)
        response_json = json.loads(response.text)
        status = response_json['status']
        if status == 'done':
            break
    
    result_url = response_json['result_url']
    response = requests.get(result_url)
    filename = "C:\\Users\\user\\Desktop\\lab\\icare\\record.mp4"
    with open(filename, 'wb') as f:
        f.write(response.content)
    """
    return result_url

@app.route('/')
def index():
    return render_template('index.html')

@app.route("/start_recording", methods=["POST"])
def recognize_from_microphone():
    recognizer = ContinuousRecognizer()
    recognizer.start()
    return jsonify({"status": "recognition started"})

@app.route('/get_result_url', methods=['GET'])
def get_result_url():
    try:
        result_url = result_queue.get_nowait()  # 嘗試從佇列中取得結果 URL
    except queue.Empty:
        return jsonify({"error": "影片尚未準備好"})
    else:
        return jsonify({"result_url": result_url})

if __name__ == '__main__':
    app.run(debug=True, port=os.getenv("PORT", default=5000), host='0.0.0.0', use_reloader=False)

