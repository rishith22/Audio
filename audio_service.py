from flask import Flask, request, jsonify
import os
import pyaudiowpatch as pyaudio
import time
import wave
from datetime import datetime
import speech_recognition as sr

app = Flask(__name__)

class AudioService:
    def __init__(self):
        self.is_recording = False
        self.current_recording_thread = None
    
    def capture_audio(self, track_name, duration, chunk_size=512):
        """Capture system audio using WASAPI loopback"""
        filename = f"{track_name}.wav"
        
        try:
            with pyaudio.PyAudio() as p:
                # Get default WASAPI info
                try:
                    wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
                except OSError:
                    return {"error": "WASAPI is not available on the system"}
                
                # Get default WASAPI speakers
                default_speakers = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
                
                if not default_speakers["isLoopbackDevice"]:
                    for loopback in p.get_loopback_device_info_generator():
                        if default_speakers["name"] in loopback["name"]:
                            default_speakers = loopback
                            break
                    else:
                        return {"error": "Default loopback output device not found"}
                
                print(f"Recording from: ({default_speakers['index']}){default_speakers['name']}")
                
                wave_file = wave.open(filename, 'wb')
                wave_file.setnchannels(default_speakers["maxInputChannels"])
                wave_file.setsampwidth(pyaudio.get_sample_size(pyaudio.paInt16))
                wave_file.setframerate(int(default_speakers["defaultSampleRate"]))

                def callback(in_data, frame_count, time_info, status):
                    wave_file.writeframes(in_data)
                    return (in_data, pyaudio.paContinue)
                
                with p.open(format=pyaudio.paInt16,
                        channels=default_speakers["maxInputChannels"],
                        rate=int(default_speakers["defaultSampleRate"]),
                        frames_per_buffer=chunk_size,
                        input=True,
                        input_device_index=default_speakers["index"],
                        stream_callback=callback
                ) as stream:
                    print(f"Recording {duration} seconds to {filename}")
                    time.sleep(duration)
                
                wave_file.close()
                return {"success": True, "filename": filename, "filepath": os.path.abspath(filename)}
                
        except Exception as e:
            return {"error": f"Audio capture failed: {str(e)}"}
    
    def transcribe_audio(self, audio_file_path, language="en-US"):
        """Transcribe audio file using Google Web Speech API (no API key needed)"""
        try:
            if not os.path.exists(audio_file_path):
                return {"error": f"Audio file not found: {audio_file_path}"}

            recognizer = sr.Recognizer()
            with sr.AudioFile(audio_file_path) as source:
                audio = recognizer.record(source)  # read the entire file

            # Use Google free Web Speech API
            text = recognizer.recognize_google(audio, language=language)
            return {"success": True, "transcription": text}

        except sr.UnknownValueError:
            return {"error": "Google Speech Recognition could not understand the audio"}
        except sr.RequestError as e:
            return {"error": f"Google Speech Recognition request failed: {e}"}
        except Exception as e:
            return {"error": f"Transcription failed: {str(e)}"}

# Initialize service
audio_service = AudioService()

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "audio_service"})

@app.route('/capture', methods=['POST'])
def capture_audio_endpoint():
    """Capture audio endpoint"""
    try:
        data = request.json
        track_name = data.get('track_name', f'audio_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
        duration = data.get('duration', 15)
        chunk_size = data.get('chunk_size', 512)
        
        result = audio_service.capture_audio(track_name, duration, chunk_size)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": f"Request processing failed: {str(e)}"}), 400

@app.route('/transcribe', methods=['POST'])
def transcribe_audio_endpoint():
    """Transcribe audio endpoint using Google Web Speech API"""
    try:
        data = request.json
        audio_file_path = data.get('audio_file_path')
        language = data.get('language', "en-US")
        
        if not audio_file_path:
            return jsonify({"error": "audio_file_path is required"}), 400
            
        result = audio_service.transcribe_audio(audio_file_path, language)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": f"Request processing failed: {str(e)}"}), 400

@app.route('/capture_and_transcribe', methods=['POST'])
def capture_and_transcribe_endpoint():
    """Capture + transcribe with Google Web Speech API"""
    try:
        data = request.json
        track_name = data.get('track_name', f'audio_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
        duration = data.get('duration', 15)
        chunk_size = data.get('chunk_size', 512)
        language = data.get('language', "en-US")
        
        # Capture audio
        capture_result = audio_service.capture_audio(track_name, duration, chunk_size)
        if "error" in capture_result:
            return jsonify(capture_result), 500
        
        # Transcribe audio
        transcribe_result = audio_service.transcribe_audio(capture_result["filepath"], language)
        if "error" in transcribe_result:
            return jsonify(transcribe_result), 500
        
        result = {
            "success": True,
            "audio_file": capture_result["filename"],
            "filepath": capture_result["filepath"],
            "transcription": transcribe_result["transcription"]
        }
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": f"Request processing failed: {str(e)}"}), 400

@app.route('/cleanup', methods=['POST'])
def cleanup_files():
    """Clean up generated audio files"""
    try:
        data = request.json
        file_path = data.get('file_path')
        
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            return jsonify({"success": True, "message": f"File {file_path} deleted"})
        else:
            return jsonify({"error": "File not found or path not provided"}), 400
            
    except Exception as e:
        return jsonify({"error": f"Cleanup failed: {str(e)}"}), 500

if __name__ == '__main__':
    print("Starting Audio Service API...")
    print("Available endpoints:")
    print("  GET  /health - Health check")
    print("  POST /capture - Capture audio")
    print("  POST /transcribe - Transcribe audio file (Google API)")
    print("  POST /capture_and_transcribe - Capture and transcribe in one call")
    print("  POST /cleanup - Clean up audio files")
    
    # Run on localhost:5000
    if __name__ == "__main__":
        app.run(host="0.0.0.0", port=5000)
