FROM python:3.11
WORKDIR /app
RUN apt update && apt install -y gcc libgeos-dev && apt-get clean
COPY src/requirements.txt .
RUN pip install -r requirements.txt
COPY src/analyze.py .
ENTRYPOINT ["python", "analyze.py"]
