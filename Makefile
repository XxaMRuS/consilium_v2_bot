.PHONY: help run dev tunnel clean install

help: ## Показать эту справку
	@echo "Доступные команды:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Установить зависимости
	@echo "📦 Установка Python зависимостей..."
	pip install -r requirements.txt
	@echo "📦 Установка VK Tunnel..."
	npm install -g @vkontakte/vk-tunnel
	@echo "✅ Готово!"

run: ## Запустить локальный сервер
	@echo "🚀 Запуск FastAPI сервера..."
	python api_main.py

dev: ## Запустить с автоперезагрузкой
	@echo "🔥 Запуск с автоперезагрузкой..."
	uvicorn api_main:app --reload --host 127.0.0.1 --port 8000

tunnel: ## Запустить VK Tunnel
	@echo "🌐 Запуск VK Tunnel..."
	vk-tunnel --mode=local --http-port=8000 --https-port=6001

certs: ## Сгенерировать SSL сертификаты
	@echo "🔐 Генерация SSL сертификатов..."
	mkdir -p certs
	openssl req -x509 -newkey rsa:4096 -keyout certs/key.pem -out certs/cert.pem -days 365 -nodes
	@echo "✅ Сертификаты готовы!"

clean: ## Очистить временные файлы
	@echo "🧹 Очистка..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf certs/
	@echo "✅ Чисто!"

setup: install certs ## Полная настройка
	@echo "🎯 Настройка завершена!"
	@echo "Запусти 'make run' для старта сервера"
	@echo "Запусти 'make tunnel' для старта VK Tunnel"

test-api: ## Тест API
	@echo "🧪 Тестирование API..."
	curl http://127.0.0.1:8000/health

test-local: ## Тест локального сервера
	@echo "🧪 Тест локального сервера..."
	@echo "Открой в браузере: http://127.0.0.1:8000"
	@python -c "import webbrowser; webbrowser.open('http://127.0.0.1:8000')"
