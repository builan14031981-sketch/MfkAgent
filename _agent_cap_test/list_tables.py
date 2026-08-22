import sqlite3
c = sqlite3.connect(r"e:\智慧项目\Mfkagent\backend\mfkagent.db")
print([r[0] for r in c.execute("select name from sqlite_master where type='table' order by name")])
c.close()
