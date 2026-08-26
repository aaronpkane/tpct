## Command Line

### Creating tpct.db

python -c "import sqlite3; conn = sqlite3.connect('tpct.db'); conn.executescript(open('schema.sql').read()); conn.close()"

### Running new files

python (file).py

### Deleting tpct.db and reseeding

del tpct.db

python -c "import sqlite3; conn = sqlite3.connect('tpct.db'); conn.executescript(open('schema.sql').read()); conn.close()"

python seed.py
