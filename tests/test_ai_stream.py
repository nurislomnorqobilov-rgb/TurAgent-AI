"""Local streaming integration tests: fake Gemini upstream, no external API key."""
import http.client, io, json, os, pathlib, sys, tempfile, threading, unittest
from unittest.mock import patch
from urllib.error import HTTPError
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'server'))
os.environ['TURAGENT_LOCAL_SQLITE']='1'
import app

class FakeGeminiStream:
    def __init__(self,words):
        self.lines=[('data: '+json.dumps({'candidates':[{'content':{'parts':[{'text':word}]}}]})+'\n\n').encode() for word in words]
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def __iter__(self):return iter(self.lines)

class StreamTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        os.environ['LOCAL_SQLITE_PATH']=str(pathlib.Path(cls.tmp.name)/'stream.sqlite3')
        app.SQLITE=True
        app.GEMINI_API_KEY='fake-key-used-only-in-tests'
        app.init_db()
        cls.srv=app.ThreadedServer(('127.0.0.1',0),app.Handler)
        cls.port=cls.srv.server_address[1]
        cls.thread=threading.Thread(target=cls.srv.serve_forever,daemon=True)
        cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown();cls.srv.server_close();cls.thread.join(4);cls.tmp.cleanup()
    def request(self):
        con=http.client.HTTPConnection('127.0.0.1',self.port,timeout=7)
        body=json.dumps({'message':'TurAgent AI xizmatlarini aytib bering'}).encode()
        con.request('POST','/api/ai/stream',body,headers={'Content-Type':'application/json','X-Turagent-Request':'1','Accept':'text/event-stream'})
        res=con.getresponse();status=res.status;data=res.read().decode();con.close()
        return status,data
    def test_true_chunked_sse_response(self):
        paths=[]
        def fake(req,timeout=26):
            paths.append(req.full_url)
            self.assertNotIn(app.GEMINI_API_KEY,req.full_url)
            return FakeGeminiStream(['Assalomu ','alaykum. ','Sayohat turlari mavjud.'])
        with patch.object(app.urllib.request,'urlopen',fake):
            status,raw=self.request()
        self.assertEqual(status,200)
        self.assertIn('streamGenerateContent?alt=sse',paths[0])
        chunks=[json.loads(line.removeprefix('data: ')) for line in raw.splitlines() if line.startswith('data: ')]
        self.assertEqual(''.join(x.get('delta','') for x in chunks),'Assalomu alaykum. Sayohat turlari mavjud.')
        self.assertTrue(chunks[-1]['done'])
    def test_missing_model_falls_back(self):
        called=[]
        def fake(req,timeout=26):
            called.append(req.full_url)
            if len(called)==1:raise HTTPError(req.full_url,404,'missing',{},io.BytesIO(b'{}'))
            return FakeGeminiStream(['Fallback ishladi'])
        with patch.object(app.urllib.request,'urlopen',fake):
            status,raw=self.request()
        self.assertEqual(status,200)
        self.assertEqual(len(called),2)
        self.assertIn('Fallback ishladi',raw)

if __name__=='__main__':unittest.main()
