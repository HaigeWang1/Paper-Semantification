# Here we will create the docker image for the python application

FROM python:3.8.16
RUN pip install --upgrade pip
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

RUN apt-get update && apt-get install --no-install-recommends -y \
    cifs-utils \
    ca-certificates

WORKDIR /code
COPY . .

# Assuming that we will have a fastapi application
ENTRYPOINT ["python -m uvicorn main:app --host 0.0.0.0 --port 8001"]