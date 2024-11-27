# Define commands
.PHONY: install run lint clean migrate

# Set up the virtual environment and install dependencies
install:
	python3 -m venv venv
	. venv/bin/activate && pip install -r requirements.txt

# Run the Django development server
run:
	. venv/bin/activate && python manage.py runserver

# Run pylint to check for linting errors
lint:
	. venv/bin/activate && pylint --load-plugins=pylint_django $(find . -name "*.py")

# Clean up .pyc files and cache
clean:
	find . -name "*.pyc" -exec rm -f {} \;
	find . -name "__pycache__" -exec rm -rf {} \;

# Migrate the database
migrate:
	. venv/bin/activate && python manage.py migrate