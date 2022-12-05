FROM python:3.11
WORKDIR /app
RUN apt update && apt install -y gcc libgeos-dev && apt-get clean
RUN pip install -U pip
RUN pip install cartopy fitparse matplotlib scipy shapely
COPY src/analyze.py .
ENTRYPOINT ["python", "analyze.py"]
