FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY boards ./boards
# A numeric user: the platform runs pods as non-root and rejects a username.
USER 10001
EXPOSE 8080
CMD ["uvicorn", "boards.main:app", "--host", "0.0.0.0", "--port", "8080"]
