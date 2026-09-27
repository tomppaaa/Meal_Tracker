Pylint antaa seuraavan raportin sovelluksesta:

```text
************* Module app
app.py:26:0: C0301: Line too long (113/100) (line-too-long)
app.py:48:0: C0301: Line too long (126/100) (line-too-long)
app.py:158:0: C0301: Line too long (117/100) (line-too-long)
app.py:366:0: C0301: Line too long (103/100) (line-too-long)
app.py:468:0: C0305: Trailing newlines (trailing-newlines)
app.py:3:0: C0410: Multiple imports on one line (sqlite3, db, config, users, meals) (multiple-imports)
app.py:194:4: W0621: Redefining name 'user_meals' from outer scope (line 189) (redefined-outer-name)
app.py:433:8: W0612: Unused variable 'meal_id' (unused-variable)
app.py:3:0: C0411: standard import "sqlite3" should be placed before third party imports "flask.Flask", "flask.render_template" (wrong-import-order)
app.py:3:0: W0611: Unused import sqlite3 (unused-import)
************* Module config
config.py:1:0: C0304: Final newline missing (missing-final-newline)
************* Module db
db.py:47:0: C0304: Final newline missing (missing-final-newline)
db.py:31:0: W0102: Dangerous default value [] as argument (dangerous-default-value)
db.py:43:0: W0102: Dangerous default value [] as argument (dangerous-default-value)
************* Module meals
meals.py:6:0: R0913: Too many arguments (10/5) (too-many-arguments)
meals.py:6:0: R0917: Too many positional arguments (10/5) (too-many-positional-arguments)
************* Module users
users.py:2:0: C0411: third party import "werkzeug.security.check_password_hash" should be placed before first party import "db" (wrong-import-order)

------------------------------------------------------------------
Your code has been rated at 9.55/10 (previous run: 9.55/10, +0.00)
```
