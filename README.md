# Meal Tracker

Meal Tracker is a Flask application for sharing and managing meals. Users can create accounts, add meals, browse and search meals, and interact through comments and ratings. The application stores data in a local SQLite database.

## Features

- Register, sign in, sign out, and manage an account.
- Store passwords as scrypt hashes rather than plain text.
- Create, edit, browse, and delete meals. Meal information includes meal type, calories, protein, carbohydrates, fat, price, and diet categories.
- Search meals by name, price range, meal type, and diet category.
- View meal details and public meal lists for users.
- Comment on meals and reply to comments on meals you own.
- Rate meals from one to five stars and view rating summaries.
- View profile statistics, including totals and breakdowns by meal type and diet category.
- Receive notifications about comments and replies.
- Validate input on the server and protect POST form submissions against CSRF.

## Requirements

- Python 3
- The packages listed in `requirements.txt`
- Pytest to run the test suite

## Setup and run

Clone the repository and change into its directory:

```bash
git clone https://github.com/tomppaaa/Meal_Tracker.git
cd Meal_Tracker
```

Install the application dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Start the development server:

```bash
python3 app.py
```

On startup, the application initializes the SQLite schema from `init.sql`. Existing databases are not migrated; use a database created with the current schema. The database file, `database.db`, is created in the current working directory. Run the command from the project directory, and keep `init.sql` alongside `db.py`.

Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in a browser and register an account to add meals.

## Tests

Install pytest if it is not already available in your Python environment:

```bash
python3 -m pip install pytest
```

Run the tests from the project directory:

```bash
python3 -m pytest
```

## Project files

- `app.py` creates the Flask app, registers request protections, sets up the database, and contains the application routes.
- `users.py` and `meals.py` implement account and meal operations.
- `db.py` contains database access and initializes supporting tables.
- `init.sql` defines and seeds the base SQLite schema.
- `templates/` contains the Jinja HTML templates; `static/` contains static assets.
- `tests/` contains the automated tests.

## Deployment note

The included `app.py` starts Flask with debug mode enabled, and `config.py` contains the application secret key. These settings are for local development only. Before deploying, disable debug mode, configure a private secret key outside source control, and run the app behind a production-ready WSGI server.
