FROM node:24-slim AS web
WORKDIR /source/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY app/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app/boards ./boards
COPY --from=web /source/frontend/dist ./boards/static
USER 10001
EXPOSE 8080
CMD ["python", "-m", "boards.start"]
