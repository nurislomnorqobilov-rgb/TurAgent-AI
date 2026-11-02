FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PORT=8000 HOST=0.0.0.0
RUN pip install --no-cache-dir 'psycopg[binary]>=3.2,<4'
COPY public ./public
COPY server ./server
RUN useradd -r -u 10001 -m turagent && chown -R turagent:turagent /app
USER turagent
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=4)" || exit 1
CMD ["python","server/app.py"]
