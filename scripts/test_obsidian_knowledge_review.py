import importlib.util
import unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location("triage",Path(__file__).with_name("obsidian_knowledge_review.py"))
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class ReviewTests(unittest.TestCase):
    def test_vivo_blocked(self):
        e=dict(id="x",path="TaskArchive公开/学习.md",title="用户研究方法",body="vivo项目用户研究方法"+"这是通用知识"*20,hash="a")
        self.assertEqual(mod.assess(e,[])["status"],"blocked")
    def test_todo_blocked(self):
        e=dict(id="x",path="TaskArchive公开/知识.md",title="用户研究方法",body="- [ ] 今天完成问卷\n"+"产品方法论"*30,hash="a")
        self.assertEqual(mod.assess(e,[])["status"],"blocked")
    def test_match_is_review_only(self):
        e=dict(id="x",path="TaskArchive公开/知识.md",title="用户研究方法",body="用户研究方法论：访谈、问卷、观察、验证、研究设计。"*12,hash="a")
        x=mod.assess(e,[dict(id="existing",title="用户研究方法",summary="访谈问卷",body="用户研究方法论")])
        self.assertEqual(x["status"],"review")
        self.assertEqual(x["suggested_action"],"review_merge")
if __name__=="__main__":unittest.main()
