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

