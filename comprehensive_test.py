#!/usr/bin/env python3
"""
🧪 КОМПЛЕКСНОЕ ТЕСТИРОВАНИЕ ВСЕХ ОПТИМИЗАЦИЙ
Автоматический тест всех функций супер-быстрого Gemini Proxy
"""

import requests
import time
import os
import sys
import json
import threading
import concurrent.futures
from pathlib import Path
import statistics

class Color:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

class OptimizationTester:
    def __init__(self, base_url, api_key, audio_file):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.audio_file = audio_file
        self.results = {}
        
    def log(self, message, color=Color.ENDC):
        print(f"{color}{message}{Color.ENDC}")
        
    def make_request(self, endpoint="", method="GET", **kwargs):
        """Универсальный метод для запросов"""
        url = f"{self.base_url}{endpoint}"
        headers = kwargs.get('headers', {})
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        kwargs['headers'] = headers
        
        try:
            if method == "GET":
                return requests.get(url, timeout=30, **kwargs)
            elif method == "POST":
                return requests.post(url, timeout=120, **kwargs)
        except Exception as e:
            self.log(f"❌ Ошибка запроса к {endpoint}: {e}", Color.FAIL)
            return None
    
    def transcribe_audio(self, format_type="json"):
        """Выполняет транскрипцию"""
        start_time = time.perf_counter()
        
        with open(self.audio_file, 'rb') as f:
            files = {'file': (self.audio_file, f, 'audio/wav')}
            data = {
                'response_format': format_type,
                'language': 'auto'
            }
            
            response = self.make_request(
                "/v1/audio/transcriptions",
                method="POST",
                files=files,
                data=data
            )
            
            duration = time.perf_counter() - start_time
            
            if response and response.status_code == 200:
                if format_type == "text":
                    text = response.text
                else:
                    result = response.json()
                    text = result.get('text', '')
                
                return {
                    'success': True,
                    'duration': duration,
                    'text': text,
                    'text_length': len(text),
                    'chars_per_second': len(text) / duration if duration > 0 else 0
                }
            else:
                return {
                    'success': False,
                    'duration': duration,
                    'error': response.text if response else "No response"
                }
        
    def test_01_health_check(self):
        """Тест 1: Проверка здоровья и оптимизаций"""
        self.log("\n" + "="*60, Color.HEADER)
        self.log("🏥 ТЕСТ 1: ПРОВЕРКА ЗДОРОВЬЯ И ОПТИМИЗАЦИЙ", Color.HEADER)
        self.log("="*60, Color.HEADER)
        
        response = self.make_request("/health")
        if not response or response.status_code != 200:
            self.log("❌ Health check не прошел", Color.FAIL)
            return False
            
        health_data = response.json()
        self.log("✅ Сервер работает", Color.GREEN)
        
        # Проверяем активные оптимизации
        optimizations = health_data.get('optimizations', {})
        self.log("\n🔧 Статус оптимизаций:", Color.CYAN)
        
        opt_count = 0
        for opt_name, enabled in optimizations.items():
            emoji = "✅" if enabled else "❌"
            color = Color.GREEN if enabled else Color.WARNING
            self.log(f"   {emoji} {opt_name}: {enabled}", color)
            if enabled:
                opt_count += 1
        
        system_info = health_data.get('system', {})
        self.log(f"\n📊 Системная информация:", Color.CYAN)
        self.log(f"   🔥 Прогрет: {system_info.get('prewarmed', False)}")
        self.log(f"   🔗 Активные соединения: {system_info.get('active_connections', 0)}")
        self.log(f"   🗄️ Размер кеша: {system_info.get('cache_size', 0)}")
        
        self.results['health_check'] = {
            'success': True,
            'optimizations_active': opt_count,
            'system_info': system_info
        }
        
        return True
    
    def test_02_basic_transcription(self):
        """Тест 2: Базовая транскрипция"""
        self.log("\n" + "="*60, Color.HEADER)
        self.log("🎵 ТЕСТ 2: БАЗОВАЯ ТРАНСКРИПЦИЯ", Color.HEADER)
        self.log("="*60, Color.HEADER)
        
        result = self.transcribe_audio()
        
        if result['success']:
            self.log(f"✅ Транскрипция успешна", Color.GREEN)
            self.log(f"   ⏱️ Время: {result['duration']:.3f}s")
            self.log(f"   📝 Длина текста: {result['text_length']} символов")
            self.log(f"   🚀 Скорость: {result['chars_per_second']:.1f} симв/сек")
            self.log(f"   📄 Текст: {result['text'][:100]}...")
        else:
            self.log(f"❌ Ошибка транскрипции: {result['error']}", Color.FAIL)
            
        self.results['basic_transcription'] = result
        return result['success']
    
    def test_03_cache_effectiveness(self):
        """Тест 3: Эффективность кеширования"""
        self.log("\n" + "="*60, Color.HEADER)
        self.log("🗄️ ТЕСТ 3: ЭФФЕКТИВНОСТЬ КЕШИРОВАНИЯ", Color.HEADER)
        self.log("="*60, Color.HEADER)
        
        # Очищаем кеш
        self.make_request("/cache/clear", method="POST")
        self.log("🧹 Кеш очищен")
        
        # Первый запрос (cold)
        self.log("\n1️⃣ Первый запрос (cold cache):")
        first_result = self.transcribe_audio()
        
        if not first_result['success']:
            self.log("❌ Первый запрос не удался", Color.FAIL)
            return False
            
        self.log(f"   ⏱️ Cold cache: {first_result['duration']:.3f}s", Color.CYAN)
        
        # Второй запрос (warm)
        self.log("\n2️⃣ Второй запрос (warm cache):")
        second_result = self.transcribe_audio()
        
        if not second_result['success']:
            self.log("❌ Второй запрос не удался", Color.FAIL)
            return False
            
        self.log(f"   ⏱️ Warm cache: {second_result['duration']:.3f}s", Color.CYAN)
        
        # Анализ эффективности
        if first_result['text'] == second_result['text']:
            speedup = first_result['duration'] / second_result['duration']
            time_saved = first_result['duration'] - second_result['duration']
            efficiency = (time_saved / first_result['duration']) * 100
            
            self.log(f"\n📊 РЕЗУЛЬТАТЫ КЕШИРОВАНИЯ:", Color.GREEN)
            self.log(f"   🚀 Ускорение: {speedup:.1f}x")
            self.log(f"   ⏱️ Время сэкономлено: {time_saved:.3f}s")
            self.log(f"   💾 Эффективность: {efficiency:.1f}%")
            
            cache_effective = speedup > 2  # Кеш должен ускорять минимум в 2 раза
            if cache_effective:
                self.log("✅ Кеширование работает отлично!", Color.GREEN)
            else:
                self.log("⚠️ Кеширование работает, но не очень эффективно", Color.WARNING)
                
        else:
            self.log("❌ Результаты транскрипции отличаются!", Color.FAIL)
            cache_effective = False
        
        self.results['cache_test'] = {
            'first_duration': first_result['duration'],
            'second_duration': second_result['duration'],
            'speedup': speedup if 'speedup' in locals() else 0,
            'effective': cache_effective if 'cache_effective' in locals() else False
        }
        
        return cache_effective if 'cache_effective' in locals() else False
    
    def test_04_warmup_effectiveness(self):
        """Тест 4: Эффективность прогрева"""
        self.log("\n" + "="*60, Color.HEADER)  
        self.log("🔥 ТЕСТ 4: ЭФФЕКТИВНОСТЬ ПРОГРЕВА", Color.HEADER)
        self.log("="*60, Color.HEADER)
        
        # Вызываем прогрев
        warmup_response = self.make_request("/warmup", method="POST")
        
        if warmup_response and warmup_response.status_code == 200:
            warmup_data = warmup_response.json()
            self.log(f"✅ Прогрев выполнен: {warmup_data.get('warmed', False)}", Color.GREEN)
        else:
            self.log("⚠️ Прогрев не удался, но это не критично", Color.WARNING)
        
        # Проверяем статус прогрева
        health_response = self.make_request("/health")
        if health_response:
            health_data = health_response.json()
            prewarmed = health_data.get('system', {}).get('prewarmed', False)
            self.log(f"🌡️ Система прогрета: {prewarmed}")
            
        self.results['warmup_test'] = {'success': True, 'prewarmed': prewarmed}
        return True
    
    def test_05_concurrent_requests(self):
        """Тест 5: Параллельные запросы (тест пула соединений)"""
        self.log("\n" + "="*60, Color.HEADER)
        self.log("🔗 ТЕСТ 5: ПАРАЛЛЕЛЬНЫЕ ЗАПРОСЫ", Color.HEADER)
        self.log("="*60, Color.HEADER)
        
        num_concurrent = 3
        self.log(f"🚀 Отправляем {num_concurrent} параллельных запросов...")
        
        def single_request():
            return self.transcribe_audio()
        
        start_time = time.perf_counter()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_concurrent) as executor:
            futures = [executor.submit(single_request) for _ in range(num_concurrent)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        total_time = time.perf_counter() - start_time
        
        successful = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]
        
        self.log(f"📊 РЕЗУЛЬТАТЫ ПАРАЛЛЕЛЬНЫХ ЗАПРОСОВ:", Color.CYAN)
        self.log(f"   ✅ Успешных: {len(successful)}/{num_concurrent}")
        self.log(f"   ❌ Неуспешных: {len(failed)}/{num_concurrent}")
        self.log(f"   ⏱️ Общее время: {total_time:.3f}s")
        
        if successful:
            durations = [r['duration'] for r in successful]
            avg_duration = statistics.mean(durations)
            self.log(f"   📈 Среднее время запроса: {avg_duration:.3f}s")
        
        self.results['concurrent_test'] = {
            'total_requests': num_concurrent,
            'successful': len(successful),
            'failed': len(failed),
            'total_time': total_time,
            'avg_duration': avg_duration if successful else 0
        }
        
        return len(successful) >= num_concurrent * 0.8  # 80% успешных запросов
    
    def test_06_different_formats(self):
        """Тест 6: Различные форматы ответа"""
        self.log("\n" + "="*60, Color.HEADER)
        self.log("📄 ТЕСТ 6: ФОРМАТЫ ОТВЕТА", Color.HEADER)
        self.log("="*60, Color.HEADER)
        
        formats = ['json', 'text', 'verbose_json']
        format_results = {}
        
        for fmt in formats:
            self.log(f"\n🧪 Тестируем формат: {fmt}")
            result = self.transcribe_audio(fmt)
            
            if result['success']:
                self.log(f"   ✅ {fmt}: {result['duration']:.3f}s", Color.GREEN)
                format_results[fmt] = True
            else:
                self.log(f"   ❌ {fmt}: {result['error']}", Color.FAIL)
                format_results[fmt] = False
        
        successful_formats = sum(format_results.values())
        self.log(f"\n📊 Поддерживаемых форматов: {successful_formats}/{len(formats)}")
        
        self.results['format_test'] = format_results
        return successful_formats >= 2  # Минимум 2 формата должны работать
    
    def test_07_metrics_endpoint(self):
        """Тест 7: Эндпоинт метрик"""
        self.log("\n" + "="*60, Color.HEADER)
        self.log("📊 ТЕСТ 7: ЭНДПОИНТ МЕТРИК", Color.HEADER)
        self.log("="*60, Color.HEADER)
        
        response = self.make_request("/metrics")
        
        if response and response.status_code == 200:
            try:
                metrics_data = response.json()
                self.log("✅ Метрики доступны", Color.GREEN)
                
                # Проверяем наличие ключевых метрик
                cache_stats = metrics_data.get('cache_stats', {})
                if cache_stats:
                    self.log(f"   🗄️ Кеш: размер {cache_stats.get('size', 0)}, макс {cache_stats.get('max_size', 0)}")
                
                performance_logs = metrics_data.get('performance_logs', [])
                self.log(f"   📝 Логов производительности: {len(performance_logs)}")
                
                self.results['metrics_test'] = {'success': True, 'cache_stats': cache_stats}
                return True
                
            except json.JSONDecodeError:
                self.log("❌ Метрики вернули некорректный JSON", Color.FAIL)
        else:
            self.log("❌ Эндпоинт метрик недоступен", Color.FAIL)
        
        self.results['metrics_test'] = {'success': False}
        return False
    
    def run_all_tests(self):
        """Запускаем все тесты"""
        self.log(f"\n{Color.BOLD}🧪 ЗАПУСК КОМПЛЕКСНОГО ТЕСТИРОВАНИЯ{Color.ENDC}")
        self.log(f"{'='*70}")
        self.log(f"🌐 URL: {self.base_url}")
        self.log(f"📄 Файл: {self.audio_file}")
        self.log(f"📏 Размер: {os.path.getsize(self.audio_file)/1024:.1f} KB")
        
        tests = [
            self.test_01_health_check,
            self.test_02_basic_transcription,
            self.test_03_cache_effectiveness,
            self.test_04_warmup_effectiveness, 
            self.test_05_concurrent_requests,
            self.test_06_different_formats,
            self.test_07_metrics_endpoint
        ]
        
        passed_tests = 0
        total_tests = len(tests)
        
        start_time = time.perf_counter()
        
        for i, test in enumerate(tests, 1):
            try:
                if test():
                    passed_tests += 1
                    self.log(f"✅ Тест {i} пройден", Color.GREEN)
                else:
                    self.log(f"❌ Тест {i} не пройден", Color.FAIL)
            except Exception as e:
                self.log(f"💥 Тест {i} упал с ошибкой: {e}", Color.FAIL)
        
        total_time = time.perf_counter() - start_time
        
        # Финальный отчет
        self.generate_final_report(passed_tests, total_tests, total_time)
        
        return passed_tests, total_tests
    
    def generate_final_report(self, passed, total, duration):
        """Генерируем финальный отчет"""
        self.log("\n" + "="*70, Color.HEADER)
        self.log("📊 ФИНАЛЬНЫЙ ОТЧЕТ", Color.HEADER)
        self.log("="*70, Color.HEADER)
        
        success_rate = (passed / total) * 100
        color = Color.GREEN if success_rate >= 80 else Color.WARNING if success_rate >= 60 else Color.FAIL
        
        self.log(f"🎯 РЕЗУЛЬТАТ: {passed}/{total} тестов пройдено ({success_rate:.1f}%)", color)
        self.log(f"⏱️ ОБЩЕЕ ВРЕМЯ: {duration:.1f} секунд")
        
        # Детальная разбивка
        self.log(f"\n📈 ДЕТАЛЬНЫЕ РЕЗУЛЬТАТЫ:")
        
        if 'basic_transcription' in self.results and self.results['basic_transcription']['success']:
            bt = self.results['basic_transcription']
            self.log(f"   🎵 Базовая транскрипция: {bt['duration']:.3f}s, {bt['chars_per_second']:.1f} симв/сек")
        
        if 'cache_test' in self.results and self.results['cache_test']['effective']:
            ct = self.results['cache_test'] 
            self.log(f"   🗄️ Кеширование: ускорение {ct['speedup']:.1f}x")
        
        if 'concurrent_test' in self.results:
            conc = self.results['concurrent_test']
            self.log(f"   🔗 Параллельные запросы: {conc['successful']}/{conc['total_requests']} успешных")
        
        # Рекомендации
        self.log(f"\n💡 РЕКОМЕНДАЦИИ:")
        
        if success_rate < 60:
            self.log("   🔴 КРИТИЧНО: Много тестов не прошли. Проверьте конфигурацию и логи.", Color.FAIL)
        elif success_rate < 80:
            self.log("   🟡 ВНИМАНИЕ: Некоторые оптимизации работают неоптимально.", Color.WARNING)
        else:
            self.log("   🟢 ОТЛИЧНО: Все оптимизации работают хорошо!", Color.GREEN)
        
        if 'cache_test' in self.results and not self.results['cache_test']['effective']:
            self.log("   📌 Кеширование неэффективно - увеличьте CACHE_SIZE или проверьте конфигурацию")
        
        if 'concurrent_test' in self.results and self.results['concurrent_test']['failed'] > 0:
            self.log("   📌 Есть проблемы с параллельными запросами - увеличьте MAX_CONNECTIONS")

def main():
    print(f"{Color.BOLD}🚀 КОМПЛЕКСНЫЙ ТЕСТЕР ОПТИМИЗАЦИЙ{Color.ENDC}")
    print("="*70)
    
    # Параметры
    LOCAL_URL = "http://localhost:8080"
    CLOUD_URL = os.getenv('CLOUD_RUN_URL')
    API_KEY = os.getenv('GEMINI_API_KEY')
    
    if not API_KEY:
        print(f"{Color.FAIL}❌ Установите переменную окружения GEMINI_API_KEY{Color.ENDC}")
        sys.exit(1)
    
    # Проверяем наличие тестового файла
    test_files = ['test_audio.wav', 'test_audio.mp3', 'test_audio.m4a']
    audio_file = None
    
    for file_name in test_files:
        if os.path.exists(file_name):
            audio_file = file_name
            break
    
    if not audio_file:
        print(f"{Color.FAIL}❌ Создайте тестовый аудио файл: {' или '.join(test_files)}{Color.ENDC}")
        sys.exit(1)
    
    # Тестирование локального сервера
    print(f"\n{Color.BLUE}🏠 ТЕСТИРОВАНИЕ ЛОКАЛЬНОГО СЕРВЕРА{Color.ENDC}")
    print("-" * 50)
    
    local_tester = OptimizationTester(LOCAL_URL, API_KEY, audio_file)
    try:
        local_passed, local_total = local_tester.run_all_tests()
        print(f"\n{Color.CYAN}📊 Локальный сервер: {local_passed}/{local_total} тестов{Color.ENDC}")
    except Exception as e:
        print(f"{Color.FAIL}💥 Ошибка тестирования локального сервера: {e}{Color.ENDC}")
    
    # Тестирование Cloud Run (если доступен)
    if CLOUD_URL:
        print(f"\n{Color.BLUE}☁️ ТЕСТИРОВАНИЕ CLOUD RUN{Color.ENDC}")
        print("-" * 50)
        
        cloud_tester = OptimizationTester(CLOUD_URL, API_KEY, audio_file)
        try:
            cloud_passed, cloud_total = cloud_tester.run_all_tests()
            print(f"\n{Color.CYAN}📊 Cloud Run: {cloud_passed}/{cloud_total} тестов{Color.ENDC}")
        except Exception as e:
            print(f"{Color.FAIL}💥 Ошибка тестирования Cloud Run: {e}{Color.ENDC}")
    else:
        print(f"\n{Color.WARNING}⚠️ Установите CLOUD_RUN_URL для тестирования Cloud Run{Color.ENDC}")
    
    # Итоговые рекомендации
    print(f"\n{Color.BOLD}🎯 ОБЩИЕ РЕКОМЕНДАЦИИ{Color.ENDC}")
    print("="*50)
    print("1. 🔍 Проверьте логи сервера для детального анализа")
    print("2. 📊 Мониторьте /metrics для отслеживания производительности") 
    print("3. ⚙️ Настройте переменные окружения под вашу нагрузку")
    print("4. 🔄 Регулярно запускайте этот тест после изменений")
    print("5. 📈 Сравнивайте результаты до и после оптимизаций")

if __name__ == "__main__":
    main()
