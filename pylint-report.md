# Pylint report

Generated on 2026-10-18 with:

```bash
python3 -m pylint app.py config.py db.py meals.py users.py
```

Pylint score: **9.88/10**

The current run reported these warnings:

```text
app.py:188:4: W0621: Redefining name 'user_meals' from outer scope (line 466) (redefined-outer-name)
app.py:199:4: W0621: Redefining name 'user_meals' from outer scope (line 466) (redefined-outer-name)
app.py:473:4: W0621: Redefining name 'user_meals' from outer scope (line 466) (redefined-outer-name)
db.py:28:0: W0102: Dangerous default value [] as argument (dangerous-default-value)
db.py:40:0: W0102: Dangerous default value [] as argument (dangerous-default-value)
meals.py:88:0: R0913: Too many arguments (10/5) (too-many-arguments)
meals.py:88:0: R0917: Too many positional arguments (10/5) (too-many-positional-arguments)
users.py:2:0: C0411: third party import "werkzeug.security.check_password_hash" should be placed before first party import "db" (wrong-import-order)
```

These are lint warnings rather than test failures. The full automated test suite currently passes with 70 tests.
