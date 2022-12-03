FROM python:3.11
WORKDIR /app
RUN pip install -U pip
RUN pip install fitparse matplotlib
COPY src/analyze.py .
ENTRYPOINT ["python", "analyze.py"]
