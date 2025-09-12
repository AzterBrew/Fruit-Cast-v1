# Use an official Python image
FROM python:3.11

# Set the working directory inside the container
WORKDIR /app

# Copy Pipfile and Pipfile.lock first to leverage Docker's build cache
COPY Pipfile Pipfile.lock ./

# Install project dependencies
RUN pipenv install --deploy --ignore-pipfile

# Set the environment variables for pipenv's virtual environment
ENV PIPENV_VENV_IN_PROJECT=1
ENV PATH="/app/.venv/bin:$PATH"

# **Correct step: Copy all project files into the container**
# This must happen before any commands that use your project code.
COPY . .

# Now, with the code in place, run Django management commands
RUN python manage.py collectstatic --noinput
RUN python manage.py migrate
RUN pipenv run python manage.py train_forecastmodel

# Expose the port your app will run on
EXPOSE 8000

# Specify the command to run the application
# This should match your Procfile
CMD ["gunicorn", "--worker-tmp-dir", "/dev/shm", "fruitcast.wsgi:application"]