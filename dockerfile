# Use a lightweight Python image
FROM python:3.13

# Set the working directory inside the container
WORKDIR /app

# Prevent Python from writing .pyc files and buffer stdout
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy the rest of your application code
COPY . .

EXPOSE 5000

CMD ["python", "app.py"]