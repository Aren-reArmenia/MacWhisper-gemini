# 🚀 Fast Gemini Audio Proxy

High-performance audio transcription proxy server using Gemini API with OpenAI Whisper API compatibility.

## Features

- **Maximum Speed** — optimized for minimal latency
- **OpenAI Compatible** — drop-in replacement for Whisper API
- **Multilingual** — excellent support for Armenian, Russian, English
- **Large Files** — supports up to 100MB
- **Clean Transcription** — automatically removes fillers and repetitions

## Quick Start

### Installation
```bash
pip install flask google-generativeai
```

### Run
```bash
python main.py
```
Server starts at `http://localhost:8080`

### Test
```bash
curl -X POST http://localhost:8080/v1/audio/transcriptions \
  -H "Authorization: Bearer YOUR_GEMINI_API_KEY" \
  -F "file=@audio.mp3" \
  -F "response_format=text"
```

## API

### Endpoint
```
POST /v1/audio/transcriptions
```

### Headers
```
Authorization: Bearer YOUR_GEMINI_API_KEY
Content-Type: multipart/form-data
```

### Parameters
| Parameter | Type | Description |
|-----------|------|-------------|
| `file` | file | Audio file (mp3, wav, m4a, etc.) |
| `model` | string | Model name (any, ignored) |
| `response_format` | string | `json`, `text`, `verbose_json` |
| `language` | string | Audio language (optional) |
| `prompt` | string | Context for better recognition |

### Supported Formats
`flac`, `m4a`, `mp3`, `mp4`, `mpeg`, `mpga`, `oga`, `ogg`, `wav`, `webm`

## Usage Examples

### Simple Transcription
```bash
curl -X POST http://localhost:8080/v1/audio/transcriptions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "file=@meeting.mp3" \
  -F "response_format=text"
```

### With Context
```bash
curl -X POST http://localhost:8080/v1/audio/transcriptions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "file=@call.wav" \
  -F "language=armenian" \
  -F "prompt=Business call about AI automation"
```

### JSON Response
```bash
curl -X POST http://localhost:8080/v1/audio/transcriptions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "file=@audio.mp3" \
  -F "response_format=json"
```

## Response Formats

### Text Format
```
Hello everyone, today we'll discuss artificial intelligence.
```

### JSON Format
```json
{
  "text": "Hello everyone, today we'll discuss artificial intelligence."
}
```

### Verbose JSON
```json
{
  "task": "transcribe",
  "language": "auto",
  "duration": 1.0,
  "text": "Hello everyone, today we'll discuss artificial intelligence.",
  "segments": [
    {
      "id": 0,
      "start": 0.0,
      "end": 1.0,
      "text": "Hello everyone, today we'll discuss artificial intelligence."
    }
  ]
}
```

## Getting Gemini API Key

1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create new API key
3. Use it in `Authorization: Bearer YOUR_KEY`

## Deployment

### Docker
```dockerfile
FROM python:3.9-slim
COPY . /app
WORKDIR /app
RUN pip install flask google-generativeai
EXPOSE 8080
CMD ["python", "app.py"]
```

### Docker Run
```bash
docker build -t gemini-proxy .
docker run -p 8080:8080 gemini-proxy
```

## Performance

- **Local**: ~2-5 seconds for 1-2 minute files
- **Cloud**: depends on ping to Gemini API
- **Limits**: 100MB per file, no request limits

## Troubleshooting

### API Key Error
```
{"error": {"message": "Invalid API key"}}
```
Check your Gemini API key is correct

### Unsupported Format
```  
{"error": {"message": "Unsupported format: txt"}}
```
Use audio formats: mp3, wav, m4a, etc.

### File Too Large
Maximum size: 100MB. Compress file or split into parts.

---

**Built for maximum speed and simplicity** ⚡
