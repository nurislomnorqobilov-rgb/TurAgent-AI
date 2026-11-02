"""TurAgent AI v3. Python 3.11+ stdlib HTTP app, PostgreSQL in production.
Set DATABASE_URL=postgresql://... and install psycopg[binary].
Set TURAGENT_LOCAL_SQLITE=1 ONLY for local smoke tests. Never use in production.
"""
from __future__ import annotations
import base64, hashlib, hmac, http.cookies, http.server, json, os, pathlib, re, secrets, sqlite3, smtplib, ssl, threading, time, urllib.parse, urllib.request, urllib.error, uuid
from datetime import datetime, timezone, date
from email.message import EmailMessage
from socketserver import ThreadingMixIn

ROOT=pathlib.Path(__file__).resolve().parent.parent

def load_env(path):
    """Read project-level .env without third-party dependencies or printing credentials."""
    if not path.is_file():return False
    for raw in path.read_text(encoding='utf-8-sig').splitlines():
        line=raw.strip()
        if not line or line.startswith('#') or '=' not in line:continue
        key,value=line.split('=',1);key=key.strip();value=value.strip()
        if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*',key):continue
        if len(value)>1 and value[0]==value[-1] and value[0] in ('"',"'"):
            value=value[1:-1]
        # Real environment (e.g. Docker and hosting) takes precedence.
        if key not in os.environ:os.environ[key]=value
    return True

if os.environ.get('TURAGENT_SKIP_DOTENV')!='1':
    load_env(ROOT/'.env')
PUBLIC=ROOT/'public'
SEED=json.loads((ROOT/'server'/'seed.json').read_text('utf-8'))
PORT=int(os.getenv('PORT','8000'))
HOST=os.getenv('HOST','0.0.0.0')
PUBLIC_URL=os.getenv('PUBLIC_URL',f'http://localhost:{PORT}').rstrip('/')
SECURE=PUBLIC_URL.startswith('https://')
SQLITE=os.getenv('TURAGENT_LOCAL_SQLITE','')=='1'
DATABASE_URL=os.getenv('DATABASE_URL','')
PGHOST=os.getenv('PGHOST','')
ADMIN_SETUP_TOKEN=os.getenv('ADMIN_SETUP_TOKEN','')
GEMINI_API_KEY=os.getenv('GEMINI_API_KEY','')
GEMINI_MODEL=os.getenv('GEMINI_MODEL','gemini-3.5-flash-lite').strip() or 'gemini-3.5-flash-lite'
GEMINI_FALLBACKS=['gemini-3.5-flash-lite','gemini-3.6-flash','gemini-2.5-flash']
GOOGLE_ID=os.getenv('GOOGLE_CLIENT_ID','')
GOOGLE_SECRET=os.getenv('GOOGLE_CLIENT_SECRET','')
SMTP_HOST=os.getenv('SMTP_HOST','')
SMTP_PORT=int(os.getenv('SMTP_PORT','587'))
SMTP_USER=os.getenv('SMTP_USER','')
SMTP_PASSWORD=os.getenv('SMTP_PASSWORD','')
SMTP_FROM=os.getenv('SMTP_FROM',SMTP_USER or 'no-reply@turagent.example')
NOTIFY_EMAIL=os.getenv('NOTIFY_EMAIL','')
RATE={}; RATELK=threading.Lock()
DBLK=threading.Lock()

if not SQLITE and not (DATABASE_URL or PGHOST):
    raise RuntimeError('DATABASE_URL is required. For temporary local tests set TURAGENT_LOCAL_SQLITE=1.')

PG_SCHEMA='''
CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,name TEXT NOT NULL,email TEXT NOT NULL UNIQUE,password_salt TEXT,password_hash TEXT,google_sub TEXT UNIQUE,role TEXT NOT NULL DEFAULT 'customer',created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),csrf TEXT NOT NULL,expires BIGINT NOT NULL);
CREATE TABLE IF NOT EXISTS tours(id TEXT PRIMARY KEY,data TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS posts(id TEXT PRIMARY KEY,data TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS favorites(user_id TEXT NOT NULL REFERENCES users(id),tour_id TEXT NOT NULL REFERENCES tours(id),PRIMARY KEY(user_id,tour_id));
CREATE TABLE IF NOT EXISTS bookings(id TEXT PRIMARY KEY,ref TEXT UNIQUE NOT NULL,user_id TEXT REFERENCES users(id),tour_id TEXT NOT NULL REFERENCES tours(id),name TEXT NOT NULL,email TEXT NOT NULL,phone TEXT NOT NULL,travel_date TEXT NOT NULL,adults INTEGER NOT NULL,children INTEGER NOT NULL,note TEXT NOT NULL,total_usd INTEGER NOT NULL,method TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',payment_status TEXT NOT NULL DEFAULT 'unpaid',created_at TEXT NOT NULL,guest_payment_hash TEXT);
CREATE TABLE IF NOT EXISTS inquiries(id TEXT PRIMARY KEY,kind TEXT NOT NULL,name TEXT NOT NULL,email TEXT NOT NULL,message TEXT NOT NULL,service TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS newsletter(email TEXT PRIMARY KEY,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS oauth_states(state_hash TEXT PRIMARY KEY,expires BIGINT NOT NULL);
CREATE TABLE IF NOT EXISTS password_resets(token_hash TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),expires BIGINT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_bookings_user ON bookings(user_id);
CREATE INDEX IF NOT EXISTS ix_sessions_expires ON sessions(expires);
'''

def connect():
    if SQLITE:
        path=pathlib.Path(os.getenv('LOCAL_SQLITE_PATH', str(ROOT/'local-dev.sqlite3')))
        c=sqlite3.connect(path, timeout=15,check_same_thread=False)
        c.row_factory=sqlite3.Row
        c.execute('PRAGMA foreign_keys=ON')
        return c
    import psycopg
    from psycopg.rows import dict_row
    if PGHOST:
        return psycopg.connect(host=PGHOST,port=int(os.getenv('PGPORT','5432')),user=os.getenv('PGUSER','turagent'),password=os.getenv('PGPASSWORD',''),dbname=os.getenv('PGDATABASE','turagent'),row_factory=dict_row,connect_timeout=8)
    return psycopg.connect(DATABASE_URL,row_factory=dict_row,connect_timeout=8)

def sqltext(statement): return statement if SQLITE else statement.replace('?', '%s')

def rows(statement,args=(),one=False):
    with DBLK:
        c=connect()
        try:
            result=c.execute(sqltext(statement), args)
            if result.description is None:
                c.commit()
                return None
            out=result.fetchone() if one else result.fetchall()
            if one:return dict(out) if out else None
            return [dict(x) for x in out]
        except Exception:
            c.rollback()
            raise
        finally:
            c.close()

def init_db():
    with DBLK:
        c=connect()
        try:
            for q in PG_SCHEMA.split(';'):
                if q.strip():c.execute(q)
            # Backward-compatible schema update for users of older local database files.
            if SQLITE:
                columns=[r['name'] for r in c.execute('PRAGMA table_info(bookings)')]
                if 'guest_payment_hash' not in columns:
                    c.execute('ALTER TABLE bookings ADD COLUMN guest_payment_hash TEXT')
            else:
                c.execute('ALTER TABLE bookings ADD COLUMN IF NOT EXISTS guest_payment_hash TEXT')
            for t in SEED['trips']:
                # Saved editable database copy; seed doesn't overwrite admin changes.
                c.execute(sqltext('INSERT INTO tours(id,data,active,created_at) VALUES(?,?,1,?) ON CONFLICT(id) DO NOTHING'),(t['id'],json.dumps(t,ensure_ascii=False),utcnow()))
            for p in SEED['posts']:
                c.execute(sqltext('INSERT INTO posts(id,data,active) VALUES(?,?,1) ON CONFLICT(id) DO NOTHING'),(p['id'],json.dumps(p,ensure_ascii=False)))
            c.commit()
        except Exception:
            c.rollback()
            raise
        finally:
            c.close()

def utcnow():return datetime.now(timezone.utc).isoformat(timespec='seconds')
def hashval(v):return hashlib.sha256(v.encode()).hexdigest()
def passmake(value,salt=None):
    salt=salt or secrets.token_bytes(16)
    val=hashlib.pbkdf2_hmac('sha256',value.encode(),salt,480000)
    return base64.b64encode(salt).decode(),base64.b64encode(val).decode()
def passok(value,salt,expected):
    try:return hmac.compare_digest(base64.b64decode(expected),hashlib.pbkdf2_hmac('sha256',value.encode(),base64.b64decode(salt),480000))
    except (TypeError,ValueError):return False

def clean(v,limit=120):return str(v or '').strip()[:limit]
def emailok(s):return bool(re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',s)) and len(s)<255

def sendmail(to,subject,body):
    if not SMTP_HOST:return False
    msg=EmailMessage();msg['From']=SMTP_FROM;msg['To']=to;msg['Subject']=subject;msg.set_content(body)
    try:
        if SMTP_PORT==465:
            with smtplib.SMTP_SSL(SMTP_HOST,SMTP_PORT,timeout=12,context=ssl.create_default_context()) as s:
                if SMTP_USER:s.login(SMTP_USER,SMTP_PASSWORD)
                s.send_message(msg)
        else:
            with smtplib.SMTP(SMTP_HOST,SMTP_PORT,timeout=12) as s:
                s.starttls(context=ssl.create_default_context())
                if SMTP_USER:s.login(SMTP_USER,SMTP_PASSWORD)
                s.send_message(msg)
        return True
    except Exception as e:
        print('SMTP delivery failed:',str(e)[:120],flush=True)
        return False

class Error(Exception):
    def __init__(self,message,status=400):self.message=message;self.status=status

def require(test,msg,status=400):
    if not test:raise Error(msg,status)

def throttle(ip,key,max_calls=15,seconds=60):
    moment=time.time();tag=(ip,key)
    with RATELK:
        calls=[t for t in RATE.get(tag,[]) if moment-t<seconds]
        if len(calls)>=max_calls:raise Error('Too many requests. Please try later.',429)
        calls.append(moment);RATE[tag]=calls
        if len(RATE)>10000:
            for k in list(RATE)[:2000]:RATE.pop(k,None)

def make_session(user_id):
    token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(24)
    rows('INSERT INTO sessions(token_hash,user_id,csrf,expires) VALUES(?,?,?,?)',(hashval(token),user_id,csrf,int(time.time())+14*86400))
    return token,csrf

def current_user(handler):
    raw=handler.headers.get('Cookie','')
    cookie=http.cookies.SimpleCookie()
    try:cookie.load(raw)
    except http.cookies.CookieError:return (None,None)
    item=cookie.get('ta_session')
    if not item:return (None,None)
    token=item.value
    session=rows('SELECT s.csrf,s.user_id,s.expires,u.name,u.email,u.role FROM sessions s JOIN users u ON s.user_id=u.id WHERE s.token_hash=?',(hashval(token),),one=True)
    if not session or session['expires']<time.time():return (None,None)
    return ({'id':session['user_id'],'name':session['name'],'email':session['email'],'role':session['role']},session['csrf'])

def get_tour(tid,admin=False):
    r=rows('SELECT data,active FROM tours WHERE id=?',(tid,),one=True)
    if not r or (not admin and not r['active']):raise Error('Tour not found',404)
    obj=json.loads(r['data']);obj['active']=bool(r['active']);return obj

def public_catalog():
    return [dict(json.loads(r['data']),active=bool(r['active'])) for r in rows('SELECT data,active FROM tours WHERE active=1 ORDER BY created_at,id')]

def b_out(b):
    return dict(b, total=b['total_usd'],tripId=b['tour_id'],date=b['travel_date'],paymentStatus=b['payment_status'],ref=b['ref'])

class Handler(http.server.BaseHTTPRequestHandler):
    server_version='TurAgent/4'
    protocol_version='HTTP/1.1'
    def log_message(self,fmt,*args):print('%s - %s'%(self.client_address[0],fmt%args),flush=True)
    def json(self,obj,status=200,addheaders=None):
        raw=json.dumps(obj,ensure_ascii=False).encode()
        self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('X-Frame-Options','DENY');self.send_header('Referrer-Policy','strict-origin-when-cross-origin');self.send_header('Content-Security-Policy',"frame-ancestors 'none'")
        for key,value in (addheaders or {}).items():self.send_header(key,value)
        self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def sendcookie(self,token,clear=False):
        secure='; Secure' if SECURE else ''
        return 'ta_session=%s; Path=/; HttpOnly; SameSite=Lax%s%s'%(token,secure,'; Max-Age=0' if clear else '; Max-Age=1209600')
    def body(self):
        length=int(self.headers.get('Content-Length','0'))
        require(0<length<=20000,'Invalid request size',413)
        require(self.headers.get('Content-Type','').startswith('application/json'),'JSON required',415)
        try:d=json.loads(self.rfile.read(length))
        except Exception:raise Error('Invalid JSON')
        require(isinstance(d,dict),'Object required')
        return d
    def securepost(self,user,csrf):
        origin=self.headers.get('Origin','')
        if origin:require(origin==PUBLIC_URL,'Origin rejected',403)
        if user:require(csrf and hmac.compare_digest(self.headers.get('X-CSRF-Token',''),csrf),'Invalid CSRF token',403)
        else:
            # Guests use a client header + same-origin checks, and restrictive cookies.
            require(self.headers.get('X-Turagent-Request','')=='1','Client header required',403)
    def do_HEAD(self):self.handle_request('HEAD')
    def do_GET(self):self.handle_request('GET')
    def do_POST(self):self.handle_request('POST')
    def do_PATCH(self):self.handle_request('PATCH')
    def do_DELETE(self):self.handle_request('DELETE')
    def handle_request(self,method):
        try:
            path=urllib.parse.urlsplit(self.path).path
            if path.startswith('/api/') or path.startswith('/auth/'):
                self.endpoint(path,method)
            elif method in ('GET','HEAD'):self.file(path)
            else:raise Error('Not found',404)
        except Error as e:self.json({'error':e.message},e.status)
        except Exception as e:
            print('SERVER ERROR',type(e).__name__,str(e)[:150],flush=True)
            self.json({'error':'Internal server error'},500)
    def file(self,path):
        if path=='/assets/hero-real.mp4' and not (PUBLIC/'assets'/'hero-real.mp4').is_file():
            # Actual Pexels Santorini footage: optional local file or hosted real clip.
            self.redirect('https://videos.pexels.com/video-files/6554717/6554717-hd_1920_1080_30fps.mp4')
            return
        if path=='/':path='/index.html'
        target=(PUBLIC/path.lstrip('/')).resolve()
        require(target.is_relative_to(PUBLIC.resolve()) and target.is_file(),'Not found',404)
        import mimetypes
        ctype=mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
        length=target.stat().st_size
        byte_range=self.headers.get('Range','') if target.suffix.lower()=='.mp4' else ''
        first,last=0,length-1
        if byte_range:
            match=re.fullmatch(r'bytes=(\d+)-(\d*)',byte_range)
            if not match:
                self.send_response(416);self.send_header('Content-Range',f'bytes */{length}');self.send_header('Content-Length','0');self.end_headers();return
            first=int(match.group(1));last=int(match.group(2)) if match.group(2) else length-1
            if first>=length or last<first:
                self.send_response(416);self.send_header('Content-Range',f'bytes */{length}');self.send_header('Content-Length','0');self.end_headers();return
            last=min(last,length-1)
        self.send_response(206 if byte_range else 200)
        self.send_header('Content-Type',ctype)
        self.send_header('Accept-Ranges','bytes')
        self.send_header('Content-Length',str(last-first+1))
        if byte_range:self.send_header('Content-Range',f'bytes {first}-{last}/{length}')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','strict-origin-when-cross-origin')
        self.send_header('Cache-Control','public,max-age=3600' if path.startswith('/assets/') else 'no-cache')
        self.end_headers()
        if self.command!='HEAD':
            with target.open('rb') as f:
                f.seek(first)
                remaining=last-first+1
                while remaining:
                    chunk=f.read(min(65536,remaining))
                    if not chunk:break
                    try:self.wfile.write(chunk)
                    except (BrokenPipeError,ConnectionResetError):break
                    remaining-=len(chunk)
    def redirect(self,url,cookie=None,extra_cookie=None):
        self.send_response(302);self.send_header('Location',url)
        if cookie:self.send_header('Set-Cookie',cookie)
        if extra_cookie:self.send_header('Set-Cookie',extra_cookie)
        self.send_header('Content-Length','0')
        self.end_headers()
    def endpoint(self,path,method):
        user,csrf=current_user(self)
        if method=='GET':
            if path=='/api/health':return self.json({'ok':True,'db':'connected','version':'4.0'})
            if path=='/api/config':return self.json({'googleEnabled':bool(GOOGLE_ID and GOOGLE_SECRET),'aiEnabled':bool(GEMINI_API_KEY),'payments':'simulation','currencyRate':12800})
            if path=='/api/catalog':return self.json({'tours':public_catalog(),'destinations':SEED['destinations']})
            if path=='/api/posts':return self.json({'posts':[json.loads(p['data']) for p in rows('SELECT data FROM posts WHERE active=1')]})
            if path=='/api/session':
                bookings=rows('SELECT * FROM bookings WHERE user_id=? ORDER BY created_at DESC',(user['id'],)) if user else []
                favs=[x['tour_id'] for x in rows('SELECT tour_id FROM favorites WHERE user_id=?',(user['id'],))] if user else []
                return self.json({'user':user,'csrf':csrf,'bookings':[b_out(b) for b in bookings],'favorites':favs})
            if path=='/auth/google':return self.google_start()
            if path=='/auth/google/callback':return self.google_finish()
            if path=='/api/admin/overview':
                self.admin(user)
                return self.json({'users':rows('SELECT COUNT(*) AS n FROM users',one=True)['n'],'bookings':rows('SELECT COUNT(*) AS n FROM bookings',one=True)['n'],'inquiries':rows('SELECT COUNT(*) AS n FROM inquiries',one=True)['n'],'revenueDemo':rows("SELECT COALESCE(SUM(total_usd),0) AS n FROM bookings WHERE payment_status='demo_paid'",one=True)['n'],'tours':[dict(json.loads(x['data']),active=bool(x['active'])) for x in rows('SELECT data,active FROM tours')],'posts':[dict(json.loads(x['data']),active=bool(x['active'])) for x in rows('SELECT data,active FROM posts')]})
            if path=='/api/admin/bookings':
                self.admin(user);return self.json({'bookings':[b_out(x) for x in rows('SELECT * FROM bookings ORDER BY created_at DESC LIMIT 300')]})
            if path=='/api/admin/inquiries':
                self.admin(user);return self.json({'inquiries':rows('SELECT * FROM inquiries ORDER BY created_at DESC LIMIT 300')})
            if path=='/api/admin/users':
                self.admin(user);return self.json({'users':rows('SELECT id,name,email,role,created_at FROM users ORDER BY created_at DESC LIMIT 300')})
            raise Error('Not found',404)
        require(method in ('POST','PATCH','DELETE'),'Unsupported',405)
        self.securepost(user,csrf)
        data=self.body() if method!='DELETE' else {}
        throttle(self.client_address[0],path,12 if ('login' in path or 'register' in path or 'ai' in path) else 55)
        if path=='/api/register':
            name=clean(data.get('name'),90);email=clean(data.get('email'),255).lower();password=str(data.get('password',''))
            require(len(name)>=2 and emailok(email) and 10<=len(password)<=128,'Check name, email and password (10+ characters).')
            salt,ph=passmake(password);uid=uuid.uuid4().hex
            try:rows('INSERT INTO users(id,name,email,password_salt,password_hash,created_at) VALUES(?,?,?,?,?,?)',(uid,name,email,salt,ph,utcnow()))
            except Exception:raise Error('Email already registered',409)
            token,ct=make_session(uid)
            return self.json({'user':{'id':uid,'name':name,'email':email,'role':'customer'},'csrf':ct},201,{'Set-Cookie':self.sendcookie(token)})
        if path=='/api/login':
            email=clean(data.get('email'),255).lower();pw=str(data.get('password',''))
            found=rows('SELECT * FROM users WHERE email=?',(email,),one=True)
            require(found and passok(pw,found['password_salt'],found['password_hash']),'Invalid email or password',401)
            token,ct=make_session(found['id'])
            return self.json({'user':{'id':found['id'],'name':found['name'],'email':email,'role':found['role']},'csrf':ct},200,{'Set-Cookie':self.sendcookie(token)})
        if path=='/api/logout':
            if user:
                cookie=http.cookies.SimpleCookie();cookie.load(self.headers.get('Cookie',''));item=cookie.get('ta_session')
                if item:rows('DELETE FROM sessions WHERE token_hash=?',(hashval(item.value),))
            return self.json({'ok':True},200,{'Set-Cookie':self.sendcookie('',True)})
        if path=='/api/reset/request':
            email=clean(data.get('email'),255).lower()
            found=rows('SELECT id FROM users WHERE email=?',(email,),one=True)
            if found and SMTP_HOST:
                token=secrets.token_urlsafe(32)
                rows('INSERT INTO password_resets(token_hash,user_id,expires) VALUES(?,?,?)',(hashval(token),found['id'],int(time.time())+1800))
                sendmail(email,'TurAgent AI — Password reset',f'Reset your password (valid for 30 minutes): {PUBLIC_URL}/#/reset?token={token}')
            return self.json({'ok':True,'mailConfigured':bool(SMTP_HOST)})
        if path=='/api/reset/complete':
            token=clean(data.get('token'),250);pw=str(data.get('password',''))
            require(len(pw)>=10,'Password must have at least 10 characters')
            tok=rows('SELECT user_id,expires FROM password_resets WHERE token_hash=?',(hashval(token),),one=True)
            require(tok and tok['expires']>time.time(),'Invalid or expired reset link',400)
            s,p=passmake(pw);rows('UPDATE users SET password_salt=?,password_hash=? WHERE id=?',(s,p,tok['user_id']))
            rows('DELETE FROM password_resets WHERE user_id=?',(tok['user_id'],))
            rows('DELETE FROM sessions WHERE user_id=?',(tok['user_id'],))
            return self.json({'ok':True})
        if path=='/api/profile':
            require(user,'Log in to continue',401)
            name=clean(data.get('name'),90);require(len(name)>=2,'Invalid name')
            rows('UPDATE users SET name=? WHERE id=?',(name,user['id']))
            return self.json({'ok':True})
        if path=='/api/favorites':
            require(user,'Log in to save favorites',401)
            tid=clean(data.get('tourId'),120);get_tour(tid)
            old=rows('SELECT user_id FROM favorites WHERE user_id=? AND tour_id=?',(user['id'],tid),one=True)
            if old:rows('DELETE FROM favorites WHERE user_id=? AND tour_id=?',(user['id'],tid))
            else:rows('INSERT INTO favorites(user_id,tour_id) VALUES(?,?)',(user['id'],tid))
            return self.json({'favorite':not bool(old)})
        if path=='/api/bookings':
            tid=clean(data.get('tourId'),100);tour=get_tour(tid)
            ds=clean(data.get('date'),15)
            try:d=date.fromisoformat(ds);require(d>=date.today(),'Choose a future date')
            except ValueError:raise Error('Invalid travel date')
            try:adults=int(data.get('adults',1));children=int(data.get('children',0))
            except (ValueError,TypeError):raise Error('Invalid travelers')
            require(1<=adults<=12 and 0<=children<=10 and adults+children<=16,'Invalid number of travelers')
            name=clean(data.get('name') or (user['name'] if user else ''),90)
            email=clean(data.get('email') or (user['email'] if user else ''),255).lower()
            phone=clean(data.get('phone'),40)
            require(len(name)>=2 and emailok(email) and len(phone)>=7,'Provide name, email and phone')
            require(data.get('agree') is True,'Please accept the booking conditions')
            method=clean(data.get('method'),24).lower();require(method in ('card','payme','click'),'Invalid payment method')
            total=int(tour['price'])*(adults)+round(int(tour['price'])*0.65)*children
            bid=uuid.uuid4().hex;ref='TA-'+secrets.token_hex(5).upper()
            guest_token=secrets.token_urlsafe(32) if not user else ''
            rows('INSERT INTO bookings(id,ref,user_id,tour_id,name,email,phone,travel_date,adults,children,note,total_usd,method,status,payment_status,created_at,guest_payment_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(bid,ref,user['id'] if user else None,tid,name,email,phone,ds,adults,children,clean(data.get('note'),700),total,method,'pending','unpaid',utcnow(),hashval(guest_token) if guest_token else None))
            if NOTIFY_EMAIL:sendmail(NOTIFY_EMAIL,'TurAgent AI booking '+ref,f'New booking request {ref} / {name} / {email} / {total} USD')
            return self.json({'ref':ref,'id':bid,'total':total,'paymentStatus':'unpaid','guestToken':guest_token},201)
        if path=='/api/payment/simulate':
            ref=clean(data.get('ref'),50);outcome=clean(data.get('outcome'),15)
            payment_method=clean(data.get('method'),20) or 'card'
            require(payment_method in ('card','payme','click'),'Invalid payment method')
            require(outcome in ('success','declined'),'Invalid simulation result')
            booking=rows('SELECT * FROM bookings WHERE ref=?',(ref,),one=True)
            require(booking,'Booking not found',404)
            guest_ok=bool(not booking['user_id'] and data.get('guestToken') and booking.get('guest_payment_hash') and hmac.compare_digest(hashval(str(data['guestToken'])),booking['guest_payment_hash']))
            require(guest_ok or (user and (booking['user_id']==user['id'] or user['role']=='admin')),'You do not have permission to this booking',403)
            require(booking['payment_status'] in ('unpaid','demo_declined'),'Payment simulation already completed',409)
            paystatus='demo_paid' if outcome=='success' else 'demo_declined'
            rows('UPDATE bookings SET payment_status=?, method=? WHERE id=?',(paystatus,payment_method,booking['id']))
            return self.json({'ok':True,'paymentStatus':paystatus,'notice':'SIMULATION ONLY. No money was transferred.'})
        if path=='/api/bookings/cancel':
            require(user,'Log in first',401)
            booking=rows('SELECT id,status FROM bookings WHERE ref=? AND user_id=?',(clean(data.get('ref'),50),user['id']),one=True)
            require(booking,'Booking not found',404)
            require(booking['status']=='pending','Booking can no longer be cancelled',409)
            rows("UPDATE bookings SET status='cancelled' WHERE id=?",(booking['id'],))
            return self.json({'ok':True})
        if path=='/api/inquiries':
            kind=clean(data.get('kind'),40);require(kind in ('contact','service'),'Invalid message type')
            name=clean(data.get('name'),90);email=clean(data.get('email'),255).lower();message=clean(data.get('message'),1200);service=clean(data.get('service'),100)
            require(len(name)>=2 and emailok(email) and len(message)>=8,'Please fill out all fields')
            rows('INSERT INTO inquiries(id,kind,name,email,message,service,created_at) VALUES(?,?,?,?,?,?,?)',(uuid.uuid4().hex,kind,name,email,message,service,utcnow()))
            emailed=sendmail(NOTIFY_EMAIL,'TurAgent AI inquiry',f'{kind} / {service}\n{name} ({email})\n{message}') if NOTIFY_EMAIL else False
            return self.json({'ok':True,'emailSent':emailed},201)
        if path=='/api/newsletter':
            email=clean(data.get('email'),255).lower();require(emailok(email),'Invalid email')
            rows('INSERT INTO newsletter(email,created_at) VALUES(?,?) ON CONFLICT(email) DO NOTHING',(email,utcnow()))
            return self.json({'ok':True})
        if path=='/api/ai/stream':
            require(GEMINI_API_KEY,'AI is not configured',503)
            throttle(self.client_address[0],'/api/ai/stream-limit',8,60)
            question=clean(data.get('message'),1200)
            require(2<=len(question)<=1200,'Invalid message')
            context='\n'.join(f"{x['id']}: {x['title']['uz']} ({x['price']} USD, {x['days']} days)" for x in public_catalog()[:40])
            prompt=('You are TurAgent AI website assistant. Answer only about TurAgent AI booking, catalog, navigation and services. '
                'Prices are examples, bookings are requests, payments are simulated and never charge money. '
                'Do not invent tours, availability, company achievements or guarantees. '
                'Respond in the question language (Uzbek, Russian or English). Keep responses helpful and concise. '
                'Contacts: 70 700 70 70, assalomualaykum@gmail.com, t.me/uzbekistan. Catalog:\n'+context)
            payload={'systemInstruction':{'parts':[{'text':prompt}]},'contents':[{'role':'user','parts':[{'text':question}]}],
                     'generationConfig':{'maxOutputTokens':1024,'temperature':0.25}}
            # Establish upstream stream before responding, so upstream HTTP errors remain real status codes.
            upstream=None
            for model in dict.fromkeys([GEMINI_MODEL]+GEMINI_FALLBACKS):
                url=f'https://generativelanguage.googleapis.com/v1beta/models/{urllib.parse.quote(model)}:streamGenerateContent?alt=sse'
                req=urllib.request.Request(url,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','x-goog-api-key':GEMINI_API_KEY},method='POST')
                try:
                    upstream=urllib.request.urlopen(req,timeout=26)
                    break
                except urllib.error.HTTPError as exc:
                    print('Gemini streaming HTTP',exc.code,'model',model,flush=True)
                    if exc.code in (400,404,503):continue
                    if exc.code==429:raise Error('AI_QUOTA_EXCEEDED',429)
                    if exc.code in (401,403):raise Error('AI_KEY_OR_PERMISSION',503)
                    raise Error('AI_PROVIDER_TEMPORARY' if exc.code>=500 else 'AI_REQUEST_FAILED',503)
                except (urllib.error.URLError,TimeoutError) as exc:
                    print('Gemini streaming network:',type(exc).__name__,flush=True)
                    continue
            require(upstream is not None,'AI_PROVIDER_TEMPORARY',503)
            self.send_response(200)
            self.send_header('Content-Type','text/event-stream; charset=utf-8')
            self.send_header('Cache-Control','no-cache, no-transform')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('X-Accel-Buffering','no')
            self.send_header('Connection','close')
            self.close_connection=True
            self.end_headers()
            output=''
            def sse(obj):
                raw=('data: '+json.dumps(obj,ensure_ascii=False)+'\n\n').encode('utf-8')
                self.wfile.write(raw);self.wfile.flush()
            try:
                with upstream as response:
                    for line in response:
                        if not line.startswith(b'data:'):continue
                        try:event=json.loads(line[5:].strip())
                        except (ValueError,UnicodeDecodeError):continue
                        text=''.join(part.get('text','') for c in event.get('candidates',[]) for part in c.get('content',{}).get('parts',[]) if isinstance(part,dict))
                        # Google may send full accumulated text or incremental tokens; avoid duplicate display.
                        if text.startswith(output):delta=text[len(output):];output=text
                        else:delta=text;output+=text
                        if delta:
                            sse({'delta':delta})
                        if len(output)>6000:break
                if not output:sse({'error':'AI_EMPTY_RESPONSE'})
                sse({'done':True})
            except (BrokenPipeError,ConnectionResetError):pass
            except Exception as exc:
                print('Gemini streaming interrupted:',type(exc).__name__,flush=True)
                try:sse({'error':'AI_NETWORK_ERROR'})
                except (BrokenPipeError,ConnectionResetError):pass
            return
        if path=='/api/ai/chat':
            require(GEMINI_API_KEY,'AI is not configured',503)
            throttle(self.client_address[0],'/api/ai/chat-limit',8,60)
            question=clean(data.get('message'),1200);require(2<=len(question)<=1200,'Invalid message')
            context='\n'.join(f"{x['id']}: {x['title']['uz']} ({x['price']} USD, {x['days']} days)" for x in public_catalog()[:40])
            prompt=('You are TurAgent AI website assistant. Answer only about this website, booking process, travel packages, navigation and services. '
                'Site: TurAgent AI, offers tours, flight/hotel/visa inquiries. Prices are illustrative until staff confirm. '
                'Bookings are requests, payments are simulations and never charge real money. '
                'Google sign-in requires configuration. Do NOT invent guarantees, exact visa regulations or real availability. '
                'Answer in the language of the question (Uzbek, Russian or English), concisely. If uncertain explain and refer to contacts. '
                'Contact: 70 700 70 70, assalomualaykum@gmail.com, t.me/uzbekistan. Current catalog:\n'+context)
            payload={'systemInstruction':{'parts':[{'text':prompt}]},'contents':[{'role':'user','parts':[{'text':question}]}],'generationConfig':{'maxOutputTokens':1024,'temperature':0.25}}
            tried=[]
            for model in dict.fromkeys([GEMINI_MODEL]+GEMINI_FALLBACKS):
                url=f'https://generativelanguage.googleapis.com/v1beta/models/{urllib.parse.quote(model)}:generateContent'
                request=urllib.request.Request(url,data=json.dumps(payload).encode('utf-8'),headers={'Content-Type':'application/json','x-goog-api-key':GEMINI_API_KEY},method='POST')
                try:
                    with urllib.request.urlopen(request,timeout=30) as response:result=json.load(response)
                    answer=''.join(part.get('text','') for cand in result.get('candidates',[]) for part in cand.get('content',{}).get('parts',[]) if isinstance(part,dict))
                    if answer.strip():return self.json({'answer':answer.strip()[:3800],'model':model})
                    raise Error('AI_EMPTY_RESPONSE',502)
                except urllib.error.HTTPError as exc:
                    status=exc.code
                    # Do not ever log/expose request headers, key or Google error body.
                    print('Gemini HTTP',status,'model',model,flush=True)
                    if status in (404,400):
                        tried.append(model)
                        continue
                    if status==429:raise Error('AI_QUOTA_EXCEEDED',429)
                    if status in (401,403):raise Error('AI_KEY_OR_PERMISSION',503)
                    if status>=500:raise Error('AI_PROVIDER_TEMPORARY',503)
                    raise Error('AI_REQUEST_FAILED',502)
                except (urllib.error.URLError, TimeoutError) as exc:
                    print('Gemini network error:',type(exc).__name__,'reason:',type(getattr(exc,'reason',None)).__name__,flush=True)
                    raise Error('AI_NETWORK_ERROR',503)
            print('Gemini rejected all candidate models:',','.join(tried),flush=True)
            raise Error('AI_MODEL_UNAVAILABLE',503)
        if path=='/api/admin/bootstrap':
            require(bool(ADMIN_SETUP_TOKEN),'Setup disabled',403)
            require(hmac.compare_digest(clean(data.get('token'),256),ADMIN_SETUP_TOKEN),'Invalid setup token',403)
            require(not rows("SELECT id FROM users WHERE role='admin' LIMIT 1",one=True),'Administrator already exists',409)
            name=clean(data.get('name'),90);email=clean(data.get('email'),255).lower();pw=str(data.get('password',''))
            require(len(name)>=2 and emailok(email) and len(pw)>=12,'Name, email and password (12+ characters) required')
            salt,ph=passmake(pw);uid=uuid.uuid4().hex
            rows('INSERT INTO users(id,name,email,password_salt,password_hash,role,created_at) VALUES(?,?,?,?,?,?,?)',(uid,name,email,salt,ph,'admin',utcnow()))
            return self.json({'ok':True},201)
        if path.startswith('/api/admin/'):
            self.admin(user)
            if path=='/api/admin/tours':
                tid=clean(data.get('id'),80)
                require(bool(re.fullmatch(r'[a-z0-9][a-z0-9-]{1,78}',tid)),'Use a URL-friendly tour ID')
                require(isinstance(data.get('title'),dict) and all(data['title'].get(k) for k in ('uz','en','ru')),'Provide titles in UZ, EN and RU')
                require(isinstance(data.get('city'),dict) and isinstance(data.get('desc'),dict),'Provide city and description translations')
                for k in ('uz','en','ru'):require(bool(data['city'].get(k)) and bool(data['desc'].get(k)),'Missing translation: '+k)
                try:price=int(data.get('price'));days=int(data.get('days'))
                except Exception:raise Error('Invalid price/days')
                require(1<=price<=1000000 and 1<=days<=100,'Invalid price/days')
                require(data.get('destination') in {d['id'] for d in SEED['destinations']},'Invalid destination')
                require(isinstance(data.get('image'),str) and data['image'].startswith(('/assets/','https://images.unsplash.com/')),'Image must be a local asset or approved photo URL')
                payload={k:v for k,v in data.items() if k in {'id','title','city','desc','price','days','destination','type','image','rating','reviews','featured','discount','itinerary'}}
                payload['price']=price;payload['days']=days
                payload['rating']=min(5,max(0,float(payload.get('rating') or 4.7)));payload['reviews']=int(payload.get('reviews') or 0)
                payload['featured']=bool(payload.get('featured'));payload['discount']=min(90,max(0,int(payload.get('discount') or 0)))
                active=1 if data.get('active',True) else 0
                rows('INSERT INTO tours(id,data,active,created_at) VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data,active=excluded.active',(tid,json.dumps(payload,ensure_ascii=False),active,utcnow()))
                return self.json({'ok':True})
            if path=='/api/admin/tours/toggle':
                tid=clean(data.get('id'),80);get_tour(tid,True)
                rows('UPDATE tours SET active=? WHERE id=?',(int(bool(data.get('active'))),tid))
                return self.json({'ok':True})
            if path=='/api/admin/posts':
                pid=clean(data.get('id'),80)
                require(bool(re.fullmatch(r'[a-z0-9-]{2,80}',pid)),'Invalid post ID')
                require(all(isinstance(data.get(k),dict) and all(data[k].get(l) for l in ('uz','en','ru')) for k in ('title','summary','body')),'Fill in every language')
                payload={k:data.get(k) for k in ('id','title','summary','body','image','date','read')}
                rows('INSERT INTO posts(id,data,active) VALUES(?,?,1) ON CONFLICT(id) DO UPDATE SET data=excluded.data',(pid,json.dumps(payload,ensure_ascii=False)))
                return self.json({'ok':True})
            if path=='/api/admin/bookings/status':
                bid=clean(data.get('id'),80);status=clean(data.get('status'),25)
                require(status in ('pending','confirmed','cancelled','completed'),'Invalid status')
                require(rows('SELECT id FROM bookings WHERE id=?',(bid,),one=True),'Booking missing',404)
                rows('UPDATE bookings SET status=? WHERE id=?',(status,bid))
                return self.json({'ok':True})
            raise Error('Not found',404)
        raise Error('Not found',404)
    def admin(self,user):require(user and user['role']=='admin','Admin access required',403)
    def google_start(self):
        require(GOOGLE_ID and GOOGLE_SECRET,'Google sign-in is not configured',503)
        state=secrets.token_urlsafe(32);rows('INSERT INTO oauth_states(state_hash,expires) VALUES(?,?)',(hashval(state),int(time.time())+600))
        redirect_uri=PUBLIC_URL+'/auth/google/callback'
        query=urllib.parse.urlencode({'client_id':GOOGLE_ID,'redirect_uri':redirect_uri,'response_type':'code','scope':'openid email profile','state':state,'prompt':'select_account'})
        secure='; Secure' if SECURE else ''
        self.redirect('https://accounts.google.com/o/oauth2/v2/auth?'+query,extra_cookie=f'ta_oauth_state={state}; Path=/auth/google; HttpOnly; SameSite=Lax; Max-Age=600{secure}')
    def google_finish(self):
        require(GOOGLE_ID and GOOGLE_SECRET,'Google not configured',503)
        params=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
        state=params.get('state',[''])[0];code=params.get('code',[''])[0]
        cookies=http.cookies.SimpleCookie()
        try:cookies.load(self.headers.get('Cookie',''))
        except http.cookies.CookieError:raise Error('Invalid OAuth state',403)
        oauth_cookie=cookies.get('ta_oauth_state')
        require(oauth_cookie is not None and hmac.compare_digest(oauth_cookie.value,state),'Invalid OAuth browser state',403)
        old=rows('SELECT expires FROM oauth_states WHERE state_hash=?',(hashval(state),),one=True)
        require(old and old['expires']>time.time() and code,'OAuth session expired',400)
        rows('DELETE FROM oauth_states WHERE state_hash=?',(hashval(state),))
        payload=urllib.parse.urlencode({'client_id':GOOGLE_ID,'client_secret':GOOGLE_SECRET,'code':code,'grant_type':'authorization_code','redirect_uri':PUBLIC_URL+'/auth/google/callback'}).encode()
        try:
            req=urllib.request.Request('https://oauth2.googleapis.com/token',data=payload)
            with urllib.request.urlopen(req,timeout=12) as r:tokens=json.load(r)
            id_token=tokens['id_token']
            with urllib.request.urlopen('https://oauth2.googleapis.com/tokeninfo?id_token='+urllib.parse.quote(id_token),timeout=12) as r:profile=json.load(r)
        except Exception:raise Error('Google login could not be verified',502)
        require(profile.get('aud')==GOOGLE_ID and profile.get('iss') in ('https://accounts.google.com','accounts.google.com') and str(profile.get('email_verified')).lower()=='true','Invalid Google identity',403)
        sub=clean(profile.get('sub'),200);email=clean(profile.get('email'),255).lower();name=clean(profile.get('name') or email.split('@')[0],90)
        require(sub and emailok(email),'Invalid Google profile',403)
        found=rows('SELECT id FROM users WHERE google_sub=?',(sub,),one=True)
        if not found:
            found=rows('SELECT id,google_sub FROM users WHERE email=?',(email,),one=True)
            if found:
                require(not found.get('google_sub') or found.get('google_sub')==sub,'Account already associated with a different Google identity',409)
                rows('UPDATE users SET google_sub=? WHERE id=?',(sub,found['id']))
            else:
                uid=uuid.uuid4().hex
                rows('INSERT INTO users(id,name,email,google_sub,created_at) VALUES(?,?,?,?,?)',(uid,name,email,sub,utcnow()))
                found={'id':uid}
        token,_=make_session(found['id'])
        self.redirect('/#/account',self.sendcookie(token),extra_cookie='ta_oauth_state=; Path=/auth/google; HttpOnly; SameSite=Lax; Max-Age=0')

class ThreadedServer(ThreadingMixIn,http.server.HTTPServer):daemon_threads=True;allow_reuse_address=True

def run():
    init_db();server=ThreadedServer((HOST,PORT),Handler)
    print(f'TurAgent AI http://{HOST}:{PORT} | db={"sqlite-dev" if SQLITE else "postgresql"}',flush=True)
    server.serve_forever()
if __name__=='__main__':run()
