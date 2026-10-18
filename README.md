# Meal Tracker

## Application features

* Users can create an account and sign in to the application.
* Users can add, edit, browse, and delete meals.
* Users can view meals added to the application and search for meals by name, price, meal type, and diet category.
* Users can view public user pages with the meals they have added.
* Users can add ratings and comments to meals. Meal owners can reply to comments.
* Users can view profile statistics and receive notifications about comments and replies.
* The application validates submitted data and protects POST forms against CSRF.

## Installing the application

Install the required Python packages:

```
python3 -m pip install -r requirements.txt
```

The database tables and initial data are created automatically from `init.sql` when the application starts. Existing databases are not migrated; use a database created with the current schema.

## Starting the application

Run the application from the project directory:

```
python3 app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000/) in a browser and create an account to add meals.

## Running the tests

Install pytest if needed:

```
python3 -m pip install pytest
```

Run the test suite from the project directory:

```
python3 -m pytest
```
