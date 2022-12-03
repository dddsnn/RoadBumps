FROM python:3.11
WORKDIR /app
RUN pip install -U pip
RUN pip install fitparse
COPY src/analyze.py .
ENTRYPOINT ["python", "analyze.py"]
