# Use official Python image
FROM python:3.11

# Set work directory
WORKDIR /app

# Install dependencies
# COPY requirements.txt .

# Install pipenv
RUN pip install pipenv

# Copy Pipfile and Pipfile.lock
COPY Pipfile Pipfile.lock ./

# Install dependencies using pipenv
RUN pipenv install --deploy --ignore-pipfile

# Set the path so pipenv's virtualenv is used
ENV PIPENV_VENV_IN_PROJECT=1
ENV PATH="/app/.venv/bin:$PATH"

# Copy project files
COPY . .

# Collect static files (optional)
RUN python manage.py collectstatic --noinput

# Run migrations (optional)
RUN python manage.py migrate

RUN pipenv run python manage.py train_forecastmodel

# Default command
CMD ["gunicorn", "--worker-tmp-dir", "/dev/shm", "fruitcast.wsgi"]