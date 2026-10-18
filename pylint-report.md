# Pylint report

Generated with:

```bash
python -m pylint app.py config.py db.py meals.py users.py
```

```text
************* Module app
app.py:150:4: W0621: Redefining name 'user_meals' from outer scope (line 359) (redefined-outer-name)
app.py:161:4: W0621: Redefining name 'user_meals' from outer scope (line 359) (redefined-outer-name)
app.py:366:4: W0621: Redefining name 'user_meals' from outer scope (line 359) (redefined-outer-name)
app.py:815:8: W0612: Unused variable 'meal_id' (unused-variable)
************* Module db
db.py:102:0: W0102: Dangerous default value [] as argument (dangerous-default-value)
db.py:114:0: W0102: Dangerous default value [] as argument (dangerous-default-value)
************* Module meals
meals.py:43:0: R0913: Too many arguments (10/5) (too-many-arguments)
meals.py:43:0: R0917: Too many positional arguments (10/5) (too-many-positional-arguments)
************* Module users
users.py:2:0: C0411: third party import "werkzeug.security.check_password_hash" should be placed before first party import "db"  (wrong-import-order)

------------------------------------------------------------------
Your code has been rated at 9.86/10 (previous run: 9.84/10, +0.02)
```
