from flask import Flask, request
import google.generativeai as genai
import tempfile
import os
import json
import time

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

# Увеличили лимит до 100MB для больших файлов
MAX_FILE_SIZE = 100 * 1024 * 1024
SUPPORTED_FORMATS = {'flac','m4a','mp3','mp4','mpeg','mpga','oga','ogg','wav','webm'}

def extract_api_key(request):
    """Быстрое извлечение ключа без лишних проверок"""
    auth_header = request.headers.get('Authorization', '')
    return auth_header[7:].strip() if auth_header.startswith('Bearer ') else None

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

@app.route('/v1/audio/transcriptions', methods=['POST'])
def transcribe_audio():
    try:
        # 1. Быстрая проверка API ключа
        api_key = extract_api_key(request)
        if not api_key:
            return {"error": {"message": "No API key"}}, 401
            
        # Убрали проверку формата ключа - принимаем любой
        genai.configure(api_key=api_key)
        
        # 2. Быстрая проверка файла
        audio_file = request.files.get('file')
        if not audio_file or not audio_file.filename:
            return {"error": {"message": "No file provided"}}, 400
            
        # Проверка расширения через set для O(1)
        ext = audio_file.filename.lower().split('.')[-1] if '.' in audio_file.filename else ''
        if ext not in SUPPORTED_FORMATS:
            return {"error": {"message": f"Unsupported format: {ext}"}}, 400
        
        # 3. Получаем параметры без дополнительных проверок
        response_format = request.form.get('response_format', 'json')
        language = request.form.get('language')
        prompt = request.form.get('prompt', '')
        
        # 4. Сохраняем файл напрямую без лишних операций
        file_ext = os.path.splitext(audio_file.filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
            # Прямое сохранение без seek
            audio_file.save(temp_file.name)
            temp_path = temp_file.name
        
        try:
            # 5. Загружаем файл в Gemini (самая медленная часть)
            uploaded_file = genai.upload_file(temp_path)
            
            # 6. Минимальный промпт для скорости
            base_prompt = """Transcribe this audio to text. Rules:
- Keep original language (Armenian/English/Russian mix is common)
- Remove filler words (uh, um, like)
- Clean up false starts and repetitions
- Output only the clean transcription text"""
            
            if language:
                base_prompt += f"\nLanguage: {language}"
            if prompt:
                base_prompt += f"\nContext: {prompt}"
            
            # 7. Быстрая генерация
            model = genai.GenerativeModel("gemini-2.5-flash")
            response = model.generate_content([base_prompt, uploaded_file])
            
            if not response or not response.text:
                raise Exception("Empty response from Gemini")
                
            transcribed_text = response.text.strip()
            
            # 8. Очистка ресурсов
            genai.delete_file(uploaded_file.name)
            os.unlink(temp_path)
            
            # 9. Быстрый ответ
            if response_format == "text":
                return transcribed_text, 200, {'Content-Type': 'text/plain'}
            else:
                response_data = create_openai_response(transcribed_text, response_format)
                return response_data, 200
                
        except Exception as e:
            # Очистка при ошибке
            if 'uploaded_file' in locals():
                try:
                    genai.delete_file(uploaded_file.name)
                except:
                    pass
            try:
                os.unlink(temp_path)
            except:
                pass
            raise e
            
    except Exception as e:
        return {"error": {"message": str(e)}}, 500

@app.after_request  
def after_request(response):
    # Минимальные CORS заголовки
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'POST'
    return response

if __name__ == '__main__':
    print("🚀 Fast Gemini Audio Proxy")
    # Отключаем debug в продакшене для скорости
    app.run(host='0.0.0.0', port=8080, debug=False, threaded=True)
