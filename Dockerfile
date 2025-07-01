# ---- Builder Stage ----
# Use a full Python image to build dependencies that might need compiling
FROM python:3.12-slim as builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies needed for building Python packages,
# including those for psycopg2 (PostgreSQL) and WeasyPrint.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install build-time tools if any
RUN pip install --upgrade pip

# Copy only the requirements file to leverage Docker's layer cache
COPY requirements.txt .

# Install application dependencies
RUN pip install -r requirements.txt


# ---- Final Stage ----
# Use a slim image for the final, smaller application image
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Set the cache directory environment variable for the 'app' user
ENV XDG_CACHE_HOME=/home/app/.cache

WORKDIR /app

# Install the RUNTIME system dependencies for WeasyPrint and Fontconfig.
# We also add 'fontconfig' to manage fonts and 'fonts-dejavu' as a default font pack.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    fontconfig \
    fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user and its home directory for better security
RUN addgroup --system app && adduser --system --group app

# Create the cache directory and ensure the 'app' user owns it.
# This also pre-builds the system-wide font cache during the image build.
RUN mkdir -p $XDG_CACHE_HOME && \
    chown -R app:app /home/app && \
    fc-cache -f -v

# Copy installed Python packages from the builder stage
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/gunicorn /usr/local/bin/gunicorn
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn

# Copy the application code
COPY . .

# Change ownership of the app directory to the non-root user
RUN chown -R app:app /app

# Switch to the non-root user
USER app

# Run collectstatic to gather all static files as the 'app' user
RUN python manage.py collectstatic --noinput

EXPOSE 8000

# Start the application
# Migrations should be run as a separate step in your deployment pipeline,
# not inside the image build.
CMD ["gunicorn", "LINKEDIN.asgi:application", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
