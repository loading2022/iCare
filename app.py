import os
import time
import threading
import queue
import azure.cognitiveservices.speech as speechsdk
from flask import Flask, render_template, request, jsonify, url_for, send_from_directory
import openai
import requests
import json

region = 'eastus2'

app = Flask(__name__)
app.secret_key = 'JQDxzgL0hjIHBO-xcCwGMw' 

openai.api_key = os.getenv('OPENAI_API_KEY')
subscription_key = os.getenv('AZURE_SUBSCRIPTION_KEY')

# 線程安全的佇列用來存儲結果 URL
result_queue = queue.Queue()
def speech_recognition_with_push_stream():
    """gives an example how to use a push audio stream to recognize speech from a custom audio
    source"""
    speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)

    # setup the audio stream
    stream = speechsdk.audio.PushAudioInputStream()
    audio_config = speechsdk.audio.AudioConfig(stream=stream)

    # instantiate the speech recognizer with push stream input
    speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

    # Connect callbacks to the events fired by the speech recognizer
    speech_recognizer.recognizing.connect(lambda evt: print('RECOGNIZING: {}'.format(evt)))
    speech_recognizer.recognized.connect(lambda evt: print('RECOGNIZED: {}'.format(evt)))
    speech_recognizer.session_started.connect(lambda evt: print('SESSION STARTED: {}'.format(evt)))
    speech_recognizer.session_stopped.connect(lambda evt: print('SESSION STOPPED {}'.format(evt)))
    speech_recognizer.canceled.connect(lambda evt: print('CANCELED {}'.format(evt)))

    # The number of bytes to push per buffer
    n_bytes = 3200
    wav_fh = wave.open(weatherfilename)

    # start continuous speech recognition
    speech_recognizer.start_continuous_recognition()

    # start pushing data until all data has been read from the file
    try:
        while(True):
            frames = wav_fh.readframes(n_bytes // 2)
            print('read {} bytes'.format(len(frames)))
            if not frames:
                break

            stream.write(frames)
            time.sleep(.1)
    finally:
        # stop recognition and clean up
        wav_fh.close()
        stream.close()
        speech_recognizer.stop_continuous_recognition()

def speech_recognition_with_pull_stream():
    """gives an example how to use a pull audio stream to recognize speech from a custom audio
    source"""
    class WavFileReaderCallback(speechsdk.audio.PullAudioInputStreamCallback):
        """Example class that implements the Pull Audio Stream interface to recognize speech from
        an audio file"""
        def __init__(self, filename: str):
            super().__init__()
            self._file_h = wave.open(filename, mode=None)

            self.sample_width = self._file_h.getsampwidth()

            assert self._file_h.getnchannels() == 1
            assert self._file_h.getsampwidth() == 2
            assert self._file_h.getframerate() == 16000
            assert self._file_h.getcomptype() == 'NONE'

        def read(self, buffer: memoryview) -> int:
            """read callback function"""
            size = buffer.nbytes
            frames = self._file_h.readframes(size // self.sample_width)

            buffer[:len(frames)] = frames

            return len(frames)

        def close(self):
            """close callback function"""
            self._file_h.close()

    speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)

    # specify the audio format
    wave_format = speechsdk.audio.AudioStreamFormat(samples_per_second=16000, bits_per_sample=16,
            channels=1)

    # setup the audio stream
    callback = WavFileReaderCallback(weatherfilename)
    stream = speechsdk.audio.PullAudioInputStream(callback, wave_format)
    audio_config = speechsdk.audio.AudioConfig(stream=stream)

    # instantiate the speech recognizer with pull stream input
    speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

    done = False

    def stop_cb(evt):
        """callback that signals to stop continuous recognition upon receiving an event `evt`"""
        print('CLOSING on {}'.format(evt))
        nonlocal done
        done = True

    # Connect callbacks to the events fired by the speech recognizer
    speech_recognizer.recognizing.connect(lambda evt: print('RECOGNIZING: {}'.format(evt)))
    speech_recognizer.recognized.connect(lambda evt: print('RECOGNIZED: {}'.format(evt)))
    speech_recognizer.session_started.connect(lambda evt: print('SESSION STARTED: {}'.format(evt)))
    speech_recognizer.session_stopped.connect(lambda evt: print('SESSION STOPPED {}'.format(evt)))
    speech_recognizer.canceled.connect(lambda evt: print('CANCELED {}'.format(evt)))
    # stop continuous recognition on either session stopped or canceled events
    speech_recognizer.session_stopped.connect(stop_cb)
    speech_recognizer.canceled.connect(stop_cb)

    # Start continuous speech recognition
    speech_recognizer.start_continuous_recognition()

    while not done:
        time.sleep(.5)

    speech_recognizer.stop_continuous_recognition()

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

