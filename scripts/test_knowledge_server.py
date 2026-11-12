import http.client
import json
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer
import knowledge_server as server

class LocalApiTests(unittest.TestCase):
    def setUp(self):
        self.httpd=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        self.thread=threading.Thread(target=self.httpd.serve_forever,daemon=True); self.thread.start()
        self.origin='http://127.0.0.1:%s'%self.httpd.server_port
    def tearDown(self): self.httpd.shutdown(); self.httpd.server_close(); self.thread.join()
    def request(self, origin, body):
        conn=http.client.HTTPConnection('127.0.0.1',self.httpd.server_port,timeout=3)
        conn.request('POST','/api/analyze',json.dumps(body),{'Origin':origin,'Content-Type':'application/json'})
        r=conn.getresponse(); payload=json.loads(r.read()); conn.close(); return r.status,payload
    def test_analysis_returns_source_and_result(self):
        article={'title':'文章','text':'内容','truncated':True}
        with patch.object(server,'get_article',return_value=article),patch.object(server,'analyze',return_value={'markdown':'整理结果','usage':{}}):
            status,out=self.request(self.origin,{'url':'https://example.com','apiKey':'sk-example'})
        self.assertEqual(status,200); self.assertEqual(out['analysis']['markdown'],'整理结果'); self.assertTrue(out['truncated'])
    def test_review_uses_existing_and_new_content(self):
        with patch.object(server,'analyze',return_value={'markdown':'合并稿'}) as ai:
            conn=http.client.HTTPConnection('127.0.0.1',self.httpd.server_port,timeout=3)
            conn.request('POST','/api/review',json.dumps({'apiKey':'sk-example','existing':'旧文档','incoming':'新资料'}),{'Origin':self.origin,'Content-Type':'application/json'})
            response=conn.getresponse(); out=json.loads(response.read()); conn.close()
        self.assertEqual(response.status,200); self.assertEqual(out['analysis']['markdown'],'合并稿')
        self.assertTrue(ai.call_args.kwargs['review']); self.assertIn('旧文档',ai.call_args.args[1]['text'])
    def test_cross_origin_cannot_call_api(self):
        status,out=self.request('https://evil.example',{'url':'https://example.com','apiKey':'sk-example'})
        self.assertEqual(status,403); self.assertFalse(out['ok'])
    def test_invalid_key_does_not_fetch(self):
        with patch.object(server,'get_article') as fetch:
            status,out=self.request(self.origin,{'url':'https://example.com','apiKey':'wrong'})
        self.assertEqual(status,400); fetch.assert_not_called()
    def test_private_addresses_rejected(self):
        with patch.object(server.socket,'getaddrinfo',return_value=[(2,1,6,'',('127.0.0.1',443))]):
            with self.assertRaisesRegex(ValueError,'公开网页'): server.validate_url('https://example.com')
if __name__=='__main__': unittest.main()
