dpython3 -m vent .vevn

pip install -r requirements.txt

python main.py

сборка докер образа docker buildx build -t maxbot:latest .
запуск docker run -e TOKEN="token" maxbot:latest