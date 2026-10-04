# Meal Tracker

Meal Tracker is a Flask web application for recording, browsing, and managing meals. It stores meal and account data in SQLite and supports searching meals by name, price, meal type, and diet category.

## Features

- Create an account, sign in, and sign out.
- Manage your profile by changing your username or password, viewing meal statistics, or deleting your account.
- Add, edit, and delete your own meals, including meal type, calories, protein, carbohydrates, fat, price, and diet categories.
- Browse meal details and view meals shared by other users.
- Search and filter meals by name, minimum or maximum price, meal type, and diet category.
- Comment on meals, reply to comments on your own meals, and rate meals from one to five stars.
- View meal statistics by meal type and diet category, including calorie and price totals.
- Use database-backed meal types and diet categories, initialized with default values when the application starts.
- Benefit from server-side validation for text lengths and numeric values, along with CSRF protection for form submissions.

## Setup

1. Clone the repository and open a terminal in the project directory:

   ```bash
   git clone https://github.com/tomppaaa/Meal_Tracker.git
   cd Meal_Tracker
   ```

2. Make sure Python 3 is installed, then install the dependencies:

   ```bash
   python3 -m pip install -r requirements.txt
   ```

3. Start the application:

   ```bash
   python3 app.py
   ```

   On startup, the application reads `init.sql` and creates or initializes the SQLite database. The `init.sql` file must remain in the project directory alongside `db.py`.

4. Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in a browser. Create an account to add and manage meals.

## Running tests

Run the test suite from the project directory:

```bash
python3 -m pytest
```

To check the Python source with Pylint:

```bash
pylint app.py config.py db.py meals.py users.py
```
