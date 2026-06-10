# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY instructor/requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the shared models and instructor code
COPY shared/ /app/shared/
COPY instructor/ /app/instructor/

# Set environment variable to allow python to find the shared module
ENV PYTHONPATH=/app

# Expose port 8000 for the FastAPI app
EXPOSE 8000

# Run the application
CMD ["uvicorn", "instructor.main:app", "--host", "0.0.0.0", "--port", "8000"]
