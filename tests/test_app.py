"""Offline HTTP integration tests with SQLite test-only mode, same handlers as PostgreSQL deployment."""
import http.cookiejar,json,os,pathlib,socket,subprocess,sys,tempfile,time,unittest,urllib.error,urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[1]
class APITests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory()
  with socket.socket() as s:s.bind(('127.0.0.1',0));cls.port=s.getsockname()[1]
  cls.base='http://127.0.0.1:'+str(cls.port)
  env=dict(os.environ,TURAGENT_LOCAL_SQLITE='1',LOCAL_SQLITE_PATH=str(pathlib.Path(cls.tmp.name)/'test.sqlite'),PORT=str(cls.port),HOST='127.0.0.1',PUBLIC_URL=cls.base,ADMIN_SETUP_TOKEN='test_012345678901234567890123456',TURAGENT_SKIP_DOTENV='1',GEMINI_API_KEY='')
  cls.proc=subprocess.Popen([sys.executable,'server/app.py'],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  for _ in range(60):
   try:
    with urllib.request.urlopen(cls.base+'/api/health',timeout=.4) as response:
     if response.status==200:break
   except Exception:time.sleep(.15)
  else:raise RuntimeError('HTTP server failed to start')
 @classmethod
 def tearDownClass(cls):
  cls.proc.terminate();cls.proc.wait(timeout=5);cls.tmp.cleanup()
 def setUp(self):
  jar=http.cookiejar.CookieJar();self.client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar));self.csrf=None
 def req(self,path,obj=None,headers=None):
  reqheaders={'Content-Type':'application/json','X-Turagent-Request':'1'}
  if self.csrf:reqheaders['X-CSRF-Token']=self.csrf
  reqheaders.update(headers or {})
  request=urllib.request.Request(self.base+path,data=json.dumps(obj).encode() if obj is not None else None,headers=reqheaders)
  try:
   with self.client.open(request,timeout=10) as response:return response.status,json.load(response)
  except urllib.error.HTTPError as e:return e.code,json.load(e)
 def sign(self,name='Test Customer',email='user@turagent.test',password='ComplexPassword123'):
  code,x=self.req('/api/register',{'name':name,'email':email,'password':password});self.assertEqual(code,201,x);self.csrf=x['csrf'];return x
 def test_public_content_and_assets(self):
  for path in ('/','/app.js','/style.css','/i18n.js','/assets/hero-poster.webp'):
   with urllib.request.urlopen(self.base+path) as r:self.assertEqual(r.status,200,path)
  _,cat=self.req('/api/catalog');self.assertGreaterEqual(len(cat['tours']),9);self.assertEqual(len(cat['destinations']),6)
  _,posts=self.req('/api/posts');self.assertGreaterEqual(len(posts['posts']),4)
  code,result=self.req('/api/config');self.assertEqual(code,200);self.assertEqual(result['payments'],'simulation')
  for path in ['/server/app.py','/.env','/../server/app.py','/local-dev.sqlite3']:
   try:urllib.request.urlopen(self.base+path)
   except urllib.error.HTTPError as e:self.assertEqual(e.code,404)
   else:self.fail('Secret accessible: '+path)
 def test_register_login_logout_and_security(self):
  self.sign(email='login1@turagent.test')
  code,session=self.req('/api/session');self.assertEqual(code,200);self.assertEqual(session['user']['email'],'login1@turagent.test')
  code,res=self.req('/api/profile',{'name':'Changed Name'},headers={'X-CSRF-Token':'WRONG'});self.assertEqual(code,403)
  code,res=self.req('/api/profile',{'name':'Changed Name'});self.assertEqual(code,200)
  code,res=self.req('/api/logout',{});self.assertEqual(code,200)
  self.csrf=None
  code,res=self.req('/api/session');self.assertIsNone(res['user'])
  code,res=self.req('/api/login',{'email':'login1@turagent.test','password':'wrong'});self.assertEqual(code,401)
  code,res=self.req('/api/login',{'email':'login1@turagent.test','password':'ComplexPassword123'});self.assertEqual(code,200);self.assertEqual(res['user']['name'],'Changed Name')
 def test_booking_payment_favorites_and_cancellation(self):
  self.sign(email='book@turagent.test')
  _,f=self.req('/api/favorites',{'tourId':'dubai'});self.assertTrue(f['favorite'])
  _,f=self.req('/api/favorites',{'tourId':'dubai'});self.assertFalse(f['favorite'])
  payload={'tourId':'istanbul','date':'2027-05-19','adults':2,'children':1,'name':'Test Customer','email':'book@turagent.test','phone':'+998901122334','method':'click','agree':True}
  code,b=self.req('/api/bookings',payload);self.assertEqual(code,201,b);self.assertEqual(b['total'],690*2+round(690*.65))
  code,p=self.req('/api/payment/simulate',{'ref':b['ref'],'outcome':'success','method':'click'});self.assertEqual(p['paymentStatus'],'demo_paid')
  code,p=self.req('/api/payment/simulate',{'ref':b['ref'],'outcome':'success'});self.assertEqual(code,409)
  code,s=self.req('/api/session');self.assertEqual(s['bookings'][0]['payment_status'],'demo_paid')
  self.assertEqual(s['bookings'][0]['method'],'click')
  code,c=self.req('/api/bookings/cancel',{'ref':b['ref']});self.assertEqual(code,200)
  bad=dict(payload,adults=900);code,r=self.req('/api/bookings',bad);self.assertEqual(code,400)
  bad=dict(payload,date='2020-01-01');code,r=self.req('/api/bookings',bad);self.assertEqual(code,400)
 def test_guest_requests_and_inquiries(self):
  _,g=self.req('/api/bookings',{'tourId':'maldives','date':'2027-11-18','adults':1,'children':0,'name':'Guest Person','email':'guest@testmail.com','phone':'998901112233','method':'payme','agree':True})
  self.assertIn('ref',g)
  code,x=self.req('/api/payment/simulate',{'ref':g['ref'],'outcome':'success'});self.assertEqual(code,403)
  code,x=self.req('/api/inquiries',{'kind':'contact','name':'Test Person','email':'hello@testmail.com','message':'Please send details of Dubai trips','service':''});self.assertEqual(code,201)
  code,x=self.req('/api/newsletter',{'email':'hello@testmail.com'});self.assertEqual(code,200)
 def test_admin_protection_bootstrap_crud(self):
  code,x=self.req('/api/admin/overview');self.assertEqual(code,403)
  code,x=self.req('/api/admin/bootstrap',{'token':'test_012345678901234567890123456','name':'Primary Admin','email':'admin@turagent.test','password':'AdminPassword123!'});self.assertEqual(code,201,x)
  code,x=self.req('/api/admin/bootstrap',{'token':'test_012345678901234567890123456','name':'Second Admin','email':'admin2@turagent.test','password':'AdminPassword123!'});self.assertEqual(code,409)
  code,a=self.req('/api/login',{'email':'admin@turagent.test','password':'AdminPassword123!'});self.assertEqual(code,200,a);self.csrf=a['csrf']
  _,stats=self.req('/api/admin/overview');self.assertGreaterEqual(stats['users'],1)
  orig=stats['tours'][0].copy();orig['title']={'uz':'Test yo‘nalish','en':'Test tour','ru':'Тестовый тур'};orig['city']={'uz':'Shahar','en':'City','ru':'Город'};orig['desc']={'uz':'Mazmun','en':'Description','ru':'Описание'};orig['image']='/assets/trip-dubai.webp'
  code,x=self.req('/api/admin/tours',orig);self.assertEqual(code,200,x)
  code,x=self.req('/api/admin/tours/toggle',{'id':orig['id'],'active':False});self.assertEqual(code,200)
  _,cat=self.req('/api/catalog');self.assertNotIn(orig['id'],[p['id'] for p in cat['tours']])
  code,x=self.req('/api/admin/tours/toggle',{'id':orig['id'],'active':True});self.assertEqual(code,200)
  post={'id':'test-post','title':{'uz':'Sinov','en':'Test','ru':'Тест'},'summary':{'uz':'Xabar','en':'News','ru':'Новость'},'body':{'uz':'Matn','en':'Text','ru':'Текст'},'image':'/assets/blog-dubai.webp','date':'2026-10-23'}
  code,x=self.req('/api/admin/posts',post);self.assertEqual(code,200,x)
  _,newposts=self.req('/api/posts');self.assertIn('test-post',[p['id'] for p in newposts['posts']])
 def test_video_source_and_guest_payment(self):
  html=(urllib.request.urlopen(self.base+'/app.js').read()).decode('utf-8')
  self.assertIn('/assets/hero-real.mp4',html)
  self.assertNotIn('hero-premium.mp4',html)
  request=urllib.request.Request(self.base+'/assets/hero-real.mp4',method='HEAD')
  # Follow redirect only manually to keep offline tests deterministic.
  class NoFollow(urllib.request.HTTPRedirectHandler):
   def redirect_request(self,req,fp,code,msg,hdrs,newurl):return None
  opener=urllib.request.build_opener(NoFollow())
  try:opener.open(request,timeout=3)
  except urllib.error.HTTPError as e:
   self.assertEqual(e.code,302)
   self.assertIn('videos.pexels.com/video-files/6554717/',e.headers['Location'])

  _,g=self.req('/api/bookings',{'tourId':'maldives','date':'2028-11-18','adults':1,'children':0,'name':'Guest Person','email':'guest@example.com','phone':'998901112233','method':'payme','agree':True})
  self.assertTrue(g['guestToken'])
  code,denied=self.req('/api/payment/simulate',{'ref':g['ref'],'outcome':'success','method':'payme','guestToken':'wrong'})
  self.assertEqual(code,403)
  code,paid=self.req('/api/payment/simulate',{'ref':g['ref'],'outcome':'success','method':'payme','guestToken':g['guestToken']})
  self.assertEqual(code,200,paid)
  self.assertEqual(paid['paymentStatus'],'demo_paid')
 def test_ai_disabled_and_invalid_inputs(self):
  code,x=self.req('/api/ai/chat',{'message':'Assalomu alaykum'});self.assertEqual(code,503)
  code,x=self.req('/api/register',{'name':'A','email':'invalid','password':'123'});self.assertEqual(code,400)
if __name__=='__main__':unittest.main()
