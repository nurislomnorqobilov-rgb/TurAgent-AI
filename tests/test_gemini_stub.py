"""Simulates Google API responses locally: no real Google key or network required."""
import http.client,io,json,os,pathlib,socket,sys,tempfile,threading,time,unittest
from unittest.mock import patch
from urllib.error import HTTPError
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'server'))
os.environ['TURAGENT_LOCAL_SQLITE']='1'
import app

class FakeHTTP:
 def __init__(self,data):self.payload=json.dumps(data).encode()
 def __enter__(self):return self
 def __exit__(self,*args):pass
 def read(self,amount=-1):return self.payload if amount<0 else self.payload[:amount]

class GeminiStubTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory()
  app.SQLITE=True
  os.environ['LOCAL_SQLITE_PATH']=str(pathlib.Path(cls.tmp.name)/'ai.sqlite')
  app.init_db()
  cls.server=app.ThreadedServer(('127.0.0.1',0),app.Handler)
  cls.port=cls.server.server_address[1]
  cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
  cls.thread.start()
  app.GEMINI_API_KEY='local-unit-test-key'
 @classmethod
 def tearDownClass(cls):
  cls.server.shutdown();cls.server.server_close();cls.thread.join(timeout=5);cls.tmp.cleanup()
 def post_ai(self):
  c=http.client.HTTPConnection('127.0.0.1',self.port,timeout=10)
  body=json.dumps({'message':'TurAgent AI xizmatlari haqida ayting'}).encode()
  c.request('POST','/api/ai/chat',body,headers={'Content-Type':'application/json','X-Turagent-Request':'1','Content-Length':str(len(body))})
  response=c.getresponse();status=response.status;out=json.loads(response.read());c.close()
  return status,out
 def test_success_from_gemini_stub(self):
  urls=[]
  def fake_open(req,timeout=30):
   urls.append(req.full_url)
   self.assertNotIn('local-unit-test-key',req.full_url)
   return FakeHTTP({'candidates':[{'content':{'parts':[{'text':'Assalomu alaykum! Tur paketlari va bron mavjud.'}]}}]})
  with patch.object(app.urllib.request,'urlopen',fake_open):
   code,x=self.post_ai()
  self.assertEqual(code,200,x)
  self.assertIn('Tur paketlari',x['answer'])
  self.assertEqual(len(urls),1)
 def test_bad_model_falls_back(self):
  called=[]
  def fake_open(req,timeout=30):
   called.append(req.full_url)
   if len(called)==1:raise HTTPError(req.full_url,404,'model missing',{},io.BytesIO(b'{}'))
   return FakeHTTP({'candidates':[{'content':{'parts':[{'text':'Fallback model works'}]}}]})
  with patch.object(app.urllib.request,'urlopen',fake_open):
   code,x=self.post_ai()
  self.assertEqual(code,200,x);self.assertEqual(len(called),2);self.assertEqual(x['answer'],'Fallback model works')
 def test_api_quota_is_visible(self):
  def fake_open(req,timeout=30):raise HTTPError(req.full_url,429,'quota',{},io.BytesIO(b'{}'))
  with patch.object(app.urllib.request,'urlopen',fake_open):
   code,x=self.post_ai()
  self.assertEqual(code,429,x);self.assertEqual(x['error'],'AI_QUOTA_EXCEEDED')
if __name__=='__main__':unittest.main()
