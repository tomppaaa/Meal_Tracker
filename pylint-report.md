# Pylint report

Generated with:

```bash
python -m pylint app.py config.py db.py errors.py meals.py routes.py users.py
```

```text
************* Module app
app.py:4:0: W0611: Unused render_template imported from flask (unused-import)
************* Module db
db.py:102:0: W0102: Dangerous default value [] as argument (dangerous-default-value)
db.py:114:0: W0102: Dangerous default value [] as argument (dangerous-default-value)
************* Module meals
meals.py:39:0: R0913: Too many arguments (10/5) (too-many-arguments)
meals.py:39:0: R0917: Too many positional arguments (10/5) (too-many-positional-arguments)
************* Module routes
routes.py:5:0: C0410: Multiple imports on one line (db, users, meals) (multiple-imports)
routes.py:47:4: W0621: Redefining name 'user_meals' from outer scope (line 256) (redefined-outer-name)
routes.py:58:4: W0621: Redefining name 'user_meals' from outer scope (line 256) (redefined-outer-name)
routes.py:263:4: W0621: Redefining name 'user_meals' from outer scope (line 256) (redefined-outer-name)
routes.py:712:8: W0612: Unused variable 'meal_id' (unused-variable)
************* Module users
users.py:2:0: C0411: third party import "werkzeug.security.check_password_hash" should be placed before first party import "db" (wrong-import-order)

------------------------------------------------------------------
Your code has been rated at 9.83/10 (previous run: 9.59/10, +0.24)
```
