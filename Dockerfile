# Here we will create the docker image for the python application

# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

# Install git
RUN apt-get update && \
    apt-get install -y git && \
    apt-get clean


# Install dblp
RUN git clone https://github.com/sebastianGehrmann/dblp-pub.git && \
    cd dblp-pub && \
    python setup.py install && \
    cd .. && \
    rm -rf dblp-pub

# Copy the dependencies file to the working directory
COPY requirements.txt .

# Install any dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code to the working directory
COPY paper_semantification/ ./paper_semantification/

COPY test/ ./test/

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "paper_semantification.main:app", "--host", "0.0.0.0", "--port", "8000"]
