FROM python:3.12-slim
WORKDIR /app
COPY app.py index.html ./
USER 10001
EXPOSE 8000
CMD ["python", "-u", "app.py"]
