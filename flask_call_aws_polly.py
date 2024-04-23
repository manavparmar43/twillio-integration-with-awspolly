import audioop
import base64,time,threading
import json,asyncio
from flask import Flask, request
from flask_sock import Sock, ConnectionClosed
from twilio.twiml.voice_response import VoiceResponse,Connect
from twilio.rest import Client
from openai import OpenAI
from amazon_transcribe.client import TranscribeStreamingClient
from amazon_transcribe.handlers import TranscriptResultStreamHandler
from amazon_transcribe.model import TranscriptEvent
app = Flask(__name__)
sock = Sock(app)

account_sid = "twillio_accountsid"
auth_token = "twillio_authtoken"
stream_lock = threading.Lock()
twilio_client = Client(account_sid, auth_token)
audio_data_stream = []
start_time = None
duration =10  
CL = '\x1b[0K'
BS = '\x08'
client = OpenAI(
    api_key="openai-key",
)
msg_data=[{"role": "system", "content": "You are on a phone call with the user."}]


class MyEventHandler(TranscriptResultStreamHandler):
    async def handle_transcript_event(self, transcript_event: TranscriptEvent):
        results = transcript_event.transcript.results
        for result in results:
            for alt in result.alternatives:
                print(alt.transcript)

async def write_chunks(stream):
    try:
        global audio_data_stream
        await stream.input_stream.send_audio_event(audio_chunk=b''.join(audio_data_stream))
        await stream.input_stream.end_stream()
        audio_data_stream =[]
    except Exception as e:
        print(f"Error:{e}")
        
async def basic_transcribe():
    client = TranscribeStreamingClient(region="ap-south-1")
    stream = await client.start_stream_transcription(
        language_code="en-US",
        media_sample_rate_hz=16000,
        media_encoding="pcm"
    )
    handler = MyEventHandler(stream.output_stream)
    await asyncio.gather(write_chunks(stream), handler.handle_events())



@app.route('/call', methods=['GET'])
def call():
    call = twilio_client.calls.create(
                        twiml=audio_stream(),
                        from_='+12015946095',
                        to='+919662771526'
                    )
    return str("calling.....")


def audio_stream():
    try:
        response = VoiceResponse()
        response.say('Ask Question AI responde after 5 second')
        connect = Connect()
        connect.stream(url=f'wss://{request.headers.get("host")}/stream')
        response.append(connect)   
        return str(response), 200, {'Content-Type': 'text/xml'}
    except Exception as e:
        print(e)

       
def handle_thread():
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(basic_transcribe())
    except Exception as e:
        print(e)


@sock.route('/stream')
def stream(ws):
    global audio_data_stream, start_time
    try:
        stop_event=threading.Event()
        thread = threading.Thread(target=handle_thread)
        thread.daemon = True
        thread.start()
        while True:
            message = ws.receive()
            packet = json.loads(message)
            if packet['event'] == 'start':
                pass
            elif packet['event'] == 'stop':
                print('\nStreaming has stopped')
                stop_event.set()
                break
            elif packet['event'] == 'media':
                audio = base64.b64decode(packet['media']['payload'])
                audio = audioop.ulaw2lin(audio, 2)
                audio = audioop.ratecv(audio, 2, 1, 8000, 16000, None)[0] 
                audio_data_stream.append(bytes(audio))

                    
    except ConnectionClosed:
        print("WebSocket connection closed.")
    except Exception as e:
        print(f"An error occurred: {str(e)}")        
                
                
if __name__ == '__main__':
    from pyngrok import ngrok
    port = 5000
    public_url = ngrok.connect(port, bind_tls=True).public_url
    number = twilio_client.incoming_phone_numbers.list()[0]
    number.update(voice_url=public_url + '/call')
    print(f'{public_url}')

    app.run(port=5000)


