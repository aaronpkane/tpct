## Command Line

### Creating tpct.db

python -c "import sqlite3; conn = sqlite3.connect('tpct.db'); conn.executescript(open('schema.sql').read()); conn.close()"

### Running new files

python (file).py

### Deleting tpct.db and reseeding

del tpct.db

python -c "import sqlite3; conn = sqlite3.connect('tpct.db'); conn.executescript(open('schema.sql').read()); conn.close()"

python seed.py

### Overrides 

import sqlite3, overrides

conn = sqlite3.connect("tpct.db")
overrides.print_plan(conn, request_id=1)

result = overrides.reassign_task_instructor_by_name(
    conn, request_id=1, task_name="1-06: Defense and Control Group 3", new_instructor_name="ME3 Wood"
)
print(result)

### Running app

python -m streamlit run app.py
