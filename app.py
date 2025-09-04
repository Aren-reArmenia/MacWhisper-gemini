from flask import Flask, request
import google.generativeai as genai
import tempfile
import os
import time
import logging
from concurrent.futures import ThreadPoolExecutor

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Глобальные переменные для переиспользования
executor = ThreadPoolExecutor(max_workers=10)
model = None

def create_openai_response(text, format_type="json"):
    """Минимальный ответ без лишних вычислений"""
    if format_type == "text":
        return text
    
    response = {"text": text}
    if format_type == "verbose_json":
        # Упрощенная версия без сложных вычислений
        response = {
            "task": "transcribe",
            "language": "auto", 
            "duration": 1.0,
            "text": text,
            "segments": [{
                "id": 0,
                "start": 0.0,
                "end": 1.0,
                "text": text
            }]
        }
    return response

def init_model():
    """Инициализация модели при старте"""
    global model
    start_time = time.time()
    model = genai.GenerativeModel("gemini-2.5-flash")
    logger.info(f"⚡ Model initialized in {(time.time() - start_time)*1000:.1f}ms")

@app.route('/v1/audio/transcriptions', methods=['POST'])
def transcribe_audio():
    # 2. All server process time (code working time)
    server_start = time.time()
    logger.info("🎯 New transcription request started")
    
    try:
        # Валидация запроса
        api_key = request.headers.get('Authorization', '')[7:].strip()
        if not api_key:
            return {"error": {"message": "No API key"}}, 401
        
        genai.configure(api_key=api_key)
        
        audio_file = request.files.get('file')
        if not audio_file:
            return {"error": {"message": "No file"}}, 400
        
        ext = audio_file.filename.split('.')[-1].lower()
        if ext not in {'flac', 'm4a', 'mp3', 'mp4', 'mpeg', 'mpga', 'oga', 'ogg', 'wav', 'webm'}:
            return {"error": {"message": "Bad format"}}, 400
            
        response_format = request.form.get('response_format', 'json')
        
        # Получаем размер файла
        audio_file.seek(0, 2)
        file_size = audio_file.tell()
        file_size_mb = file_size / (1024 * 1024)
        audio_file.seek(0)
        
        # 3. temporary file save time
        temp_save_start = time.time()
        
        with tempfile.NamedTemporaryFile(suffix=f'.{ext}', delete=False) as temp_file:
            audio_file.save(temp_file.name)
            temp_path = temp_file.name
        
        temp_save_time = (time.time() - temp_save_start) * 1000
        logger.info(f"📁 temporary file save time: {temp_save_time:.1f}ms")
        
        try:
            # 4. google upload time
            upload_start = time.time()
            uploaded_file = genai.upload_file(temp_path)
            google_upload_time = (time.time() - upload_start) * 1000
            logger.info(f"⬆️  google upload time: {google_upload_time:.1f}ms")
            
            # 5. before transcript sent and after get transcript
            transcript_start = time.time()
            global model
            if model is None:
                init_model()
                
            response = model.generate_content([
                """Transcribe the provided speech (most likely in Armenian). Remove filler words, false starts, and repetitions. Don't alter the style, grammar choices, dialect, informal expressions and jargon of the speaker. For example, don't change "տենց" to "այդպես", or "գնում ա" to "գնում է", etc. Transcribe any English or Russian words in their original script. Add punctuation for readability. Your response must only be the final transcribed text in plain format, with no markdown or anything.""",
                uploaded_file
            ])
            transcript_time = (time.time() - transcript_start) * 1000
            logger.info(f"🤖 before transcript sent and after get transcript: {transcript_time:.1f}ms")
            
            # Удаляем файлы
            try:
                genai.delete_file(uploaded_file.name)
                os.unlink(temp_path)
            except:
                pass
            
            # 2. All server process time (завершение)
            all_server_process_time = (time.time() - server_start) * 1000
            
            logger.info(f"""
🎯 PERFORMANCE MEASUREMENTS:
📁 File: {file_size_mb:.1f}MB ({ext})
⏱️  REQUIRED MEASUREMENTS:
   • All server process time (code working time): {all_server_process_time:.1f}ms
   • temporary file process time: {temp_process_time:.1f}ms
   • google upload time: {google_upload_time:.1f}ms
   • before transcript sent and after get transcript: {transcript_time:.1f}ms
📝 Text length: {len(response.text)} chars
            """)
            
            # Очистка результата
            transcribed_text = response.text.strip()
            
            import re
            transcribed_text = re.sub(r'\d{2}:\d{2}\s*', '', transcribed_text)
            transcribed_text = re.sub(r'\n+', ' ', transcribed_text).strip()
            
            # Возвращаем ответ
            openai_response = create_openai_response(transcribed_text, response_format)
            
            if response_format == "text":
                return openai_response, 200, {'Content-Type': 'text/plain'}
            else:
                return openai_response
            
        except Exception as e:
            try:
                if 'uploaded_file' in locals():
                    genai.delete_file(uploaded_file.name)
                if 'temp_path' in locals():
                    os.unlink(temp_path)
            except:
                pass
            all_server_process_time = (time.time() - server_start) * 1000
            logger.error(f"❌ Error after All server process time: {all_server_process_time:.1f}ms: {str(e)}")
            raise
            
    except Exception as e:
        all_server_process_time = (time.time() - server_start) * 1000
        logger.error(f"❌ Request failed after All server process time: {all_server_process_time:.1f}ms: {str(e)}")
        return {"error": {"message": str(e)}}, 500

if __name__ == '__main__':
    print("🚀 Ultra-Fast Gemini Proxy with Performance Monitoring")
    init_model()
    app.run(
        host='0.0.0.0', 
        port=8080, 
        debug=False, 
        threaded=True,
        processes=1,
        use_reloader=False
    )