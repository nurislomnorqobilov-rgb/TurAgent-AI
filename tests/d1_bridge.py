"""Only for local integration testing: SQLite bridge emulates the D1 SQL binding."""
import sys,json,sqlite3
file=sys.argv[1]; payload=json.loads(sys.argv[2]); db=sqlite3.connect(file); db.row_factory=sqlite3.Row
try:
  c=db.execute(payload['sql'],payload.get('args',[]))
  if c.description:
    result={'rows':[dict(x) for x in c.fetchall()]}
  else:
    result={'rows':[],'changes':c.rowcount}
  db.commit(); print(json.dumps(result,ensure_ascii=False))
except Exception as e:
  db.rollback(); print(json.dumps({'error':str(e)}));sys.exit(1)
finally:db.close()
