import unittest
import textwrap
import tempfile
import io
import yaml

from os import path
from beancount.ingest import rule


class TestRuler(unittest.TestCase):
    def load_yaml(self, ss):
        f = io.StringIO(ss)
        return yaml.load(f, Loader=yaml.FullLoader)

    def test_yaml_load_order(self):
        text =  textwrap.dedent("""
        default_method_account: Assets:FIXME
        default_target_account: Expenses:FIXME
        rules:
            - type: /
              txType: 零钱提现
              targetAccount: Assets:Wechat:Cash
              commissionAccount: Expenses:Wechat:Commission

            - type: 支出
              txType: 商户消费
              targetAccount: Expenses:Misc

            - bbb: bbb

            - aaa: aaa
              targetAccount: Expenses:Misc

            - ddd: 支出
              txType: 转账
              targetAccount: Expenses:FIXME
              methodAccount: Assets:Wechat:Cash
        """)
        d = self.load_yaml(text)
        self.assertTrue("rules" in d)
        for i in range(1, 10):
            c = self.load_yaml(text)
            self.assertTrue("rules" in c)
            self.assertEqual(d["rules"], c["rules"])
    
    def test_load_yaml(self):
        text =  textwrap.dedent("""
        default_method_account: Assets:FIXME
        default_target_account: Expenses:FIXME
        rules:
            - type: /
              method_account:
                - a 
                - b

            - type: test
              method_account: a

            - type: 支出
              txType: 商户消费
        """)
        d = self.load_yaml(text)
        print(d)

    def test_ruler_match(self):
        text = textwrap.dedent("""
        default_method_account: Assets:FIXME
        default_target_account: Expenses:FIXME
        rules:
            - payee: mike
            - payee: jim
              method_account: "Assets:Bank:CCB"
              target_account: "Assets:Wechat"
        """)
        with tempfile.TemporaryDirectory() as d:
            p = path.join(d, 'config.yaml')
            with open(p, 'w') as f:
                f.write(text + "\n")
            
            r = rule.Ruler(p)
            matched = r.match({"payee" : 'jim'})
            self.assertEqual(matched.method_account, "Assets:Bank:CCB")
            self.assertEqual(matched.target_account, "Assets:Wechat")


