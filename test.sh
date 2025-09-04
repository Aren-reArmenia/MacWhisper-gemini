# 🚀 БЫСТРЫЙ ТЕСТ ДЛЯ ОДНОГО ФАЙЛА

# Замените YOUR_API_KEY на ваш ключ
API_KEY="AIzaSyASBl3l36CZ7b2l-l00T34X22fJfmqIJao"
HOST="https://gemini-audio-proxy-376331661111.europe-west1.run.app"

# Тест для короткого файла
echo "🎯 Testing short.mp3..."
curl -X POST "$HOST/v1/audio/transcriptions" \
  -H "Authorization: Bearer $API_KEY" \
  -F "file=@short.mp3" \
  -w "\n📊 PERFORMANCE METRICS:\n⏱️  DNS Lookup: %{time_namelookup}s\n🔗 Connection: %{time_connect}s\n📤 Upload Time: %{time_pretransfer}s\n🖥️  Server Processing: %{time_starttransfer}s (from start)\n📥 Total Time: %{time_total}s\n📈 HTTP Code: %{http_code}\n📁 Upload Size: %{size_upload} bytes\n📄 Download Size: %{size_download} bytes\n\n" \
  -v

# Вычисляем этапы (нужен bc для расчетов)
echo ""
echo "🧮 Calculating breakdown..."

# Для точных расчетов используйте скрипт выше, эта команда показывает сырые данные

# Тест для длинного файла  
echo ""
echo "📚 Testing long.mp3..."
curl -X POST "$HOST/v1/audio/transcriptions" \
  -H "Authorization: Bearer $API_KEY" \
  -F "file=@long.mp3" \
  -w "\n📊 PERFORMANCE METRICS:\n⏱️  DNS Lookup: %{time_namelookup}s\n🔗 Connection: %{time_connect}s\n📤 Upload Time: %{time_pretransfer}s\n🖥️  Server Processing: %{time_starttransfer}s (from start)\n📥 Total Time: %{time_total}s\n📈 HTTP Code: %{http_code}\n📁 Upload Size: %{size_upload} bytes\n📄 Download Size: %{size_download} bytes\n\n" \
  -v
