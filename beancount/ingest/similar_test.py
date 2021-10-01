__copyright__ = "Copyright (C) 2016  Martin Blais"
__license__ = "GNU GPLv2"

import datetime
import unittest

from beancount.core.number import D
from beancount.core import data
from beancount.parser import cmptest
from beancount.parser import parser
from beancount import loader
from beancount.ingest import similar


class TestDups(cmptest.TestCase):

    @loader.load_doc()
    def test_find_similar_entries(self, entries, _, __):
        """
            plugin "beancount.plugins.auto_accounts"

            2016-01-03 *
              Expenses:Tips         1.03 USD
              Assets:Other

            2016-01-04 *
              Expenses:Coffee       1.04 USD
              Assets:Other

            2016-01-05 *
              Expenses:Restaurant   1.05 USD
              Assets:Other

            2016-01-06 *
              Expenses:Groceries    1.06 USD
              Assets:Other

            2016-01-07 *
              Expenses:Alcohol      1.07 USD
              Assets:Other

            2016-01-08 *
              Expenses:Smoking      1.08 USD
              Assets:Other

            2016-01-09 *
              Expenses:Taxi         1.09 USD
              Assets:Other
        """
        new_entries, _, __ = loader.load_string("""
            plugin "beancount.plugins.auto_accounts"

            2016-01-06 *
              Expenses:Groceries    1.06 USD
              Assets:Other
        """)
        for days, num_comparisons in [(0, 1), (1, 1), (2, 1)]:
            duplicates = similar.find_similar_entries(new_entries, entries,
                                                      lambda e1, e2: True,
                                                      window_days=days)
            self.assertEqual(num_comparisons, len(duplicates))

            duplicates = similar.find_similar_entries(new_entries, entries,
                                                      lambda e1, e2: False,
                                                      window_days=days)
            self.assertEqual(0, len(duplicates))

    @loader.load_doc()
    def test_find_similar_entries__multiple_matches(self, entries, _, __):
        """
            plugin "beancount.plugins.auto_accounts"

            2016-02-01 * "A"
              Assets:Account1    10.00 USD
              Assets:Account2   -10.00 USD

            2016-02-02 * "B"
              Assets:Account1    10.00 USD
              Assets:Account2   -10.00 USD

            2016-02-03 * "C"
              Assets:Account1    10.00 USD
              Assets:Account2   -10.00 USD

            2016-02-04 * "D"
              Assets:Account1    10.00 USD
              Assets:Account2   -10.00 USD

            2016-02-05 * "D"
              Assets:Account1    10.00 USD
              Assets:Account2   -10.00 USD
        """
        # Test it with a single entry.
        new_entries = list(data.filter_txns(entries))[2:3]
        duplicates = similar.find_similar_entries(new_entries, entries, window_days=1)
        self.assertEqual(1, len(duplicates))
        self.assertEqual(new_entries[0], duplicates[0][0])

        # Test it with multiple duplicate entries.
        new_entries = list(data.filter_txns(entries))[1:4]
        duplicates = similar.find_similar_entries(new_entries, entries, window_days=1)
        self.assertEqual(len(new_entries), len(duplicates))

    @parser.parse_doc(allow_incomplete=True)
    def test_amounts_map(self, entries, _, __):
        """
            plugin "beancount.plugins.auto_accounts"

            2016-01-03 *
              Expenses:Alcohol     20.00 USD
              Expenses:Tips         1.03 USD
              Assets:Other

            2016-01-03 *
              Expenses:Tips         1.01 USD
              Expenses:Tips         1.02 USD
              Assets:Other
        """
        txns = list(data.filter_txns(entries))
        amap = similar.amounts_map(txns[0])
        self.assertEqual({('Expenses:Tips', 'USD'): D('1.03'),
                          ('Expenses:Alcohol', 'USD'): D('20.00')}, amap)

        amap = similar.amounts_map(txns[1])
        self.assertEqual({('Expenses:Tips', 'USD'): D('2.03')}, amap)


class TestSimilarityComparator(cmptest.TestCase):

    def setUp(self):
        self.comparator = similar.SimilarityComparator(datetime.timedelta(days=2))

    @loader.load_doc()
    def test_simple(self, entries, _, __):
        """
            plugin "beancount.plugins.auto_accounts"

            2016-01-03 * "Base reservation" ^base
              Expenses:Alcohol     20.00 USD
              Expenses:Tips         1.03 USD
              Assets:Other

            2016-01-03 * "Similar amount within bounds" ^in-bounds
              Expenses:Alcohol     20.99 USD
              Assets:Other
            2016-01-03 * "Similar amount out of bounds" ^out-bounds
              Expenses:Alcohol     21.00 USD
              Assets:Other

            2016-01-06 * "Date too far" ^too-late
              Expenses:Alcohol     20.00 USD
              Expenses:Tips         1.03 USD
              Assets:Other

            2016-01-03 * "Non-overlapping accounts" ^non-accounts
              Expenses:Alcohol     20.00 USD
              Expenses:Tips         1.03 USD
              Assets:SomethingElse
        """
        txns = list(data.filter_txns(entries))

        def compare(expected, link1, link2):
            self.assertEqual(expected, self.comparator(
                next(txn for txn in txns if link1 in txn.links),
                next(txn for txn in txns if link2 in txn.links)))

        compare(True, 'base', 'base')
        compare(True, 'base', 'in-bounds')
        compare(False, 'base', 'out-bounds')
        compare(False, 'base', 'too-late')
        compare(False, 'base', 'non-accounts')

class TestNaiveComparator(cmptest.TestCase):

    def setUp(self):
        self.comparator = similar.NaiveComparator()

    @loader.load_doc()
    def test_simple(self, entries, _, __):
        """
            plugin "beancount.plugins.auto_accounts"

            2021-03-06 * "天弘基金管理有限公司"
              meta_0: "收/支: 其他"
              meta_1: "交易对方: 天弘基金管理有限公司"
              meta_2: "对方账号: fun***@thfund.com.cn"
              meta_3: "商品说明: 余额宝-单次转入"
              meta_4: "收/付款方式: 中国建设银行储蓄卡(4492)"
              meta_5: "交易状态: 交易成功"
              meta_6: "交易分类: 投资理财"
              meta_7: "交易订单号: 20210306210500100010320072259675"
              meta_8: "商家订单号: LC2021030614383020882123564203245529"
              meta_9: "交易时间: 2021-03-06 14:38:30"
              Assets:Bank:CN:CCB-4492  -10000.00 CNY
              Assets:Alipay:YuEBao      10000.00 CNY
            
            2021-03-06 * "支付宝-天弘基金管理有限公司"
              meta_0: "记账日: 20210306"
              meta_1: "交易日期: 20210306"
              meta_2: "交易时间: 14:38:37"
              meta_3: "账户余额: 87474.1"
              meta_4: "币种: 人民币"
              meta_5: "摘要: 消费"
              meta_6: "对方账号: 105331*****0875"
              meta_7: "对方户名: 支付宝-天弘基金管理有限公司"
              meta_8: "交易地点: 支付宝-天弘基金管理有限公司"
              Assets:Bank:CN:CCB-4492  -10000.00 CNY
              Assets:Alipay:YuEBao      10000.00 CNY
        """
        txns = list(data.filter_txns(entries))
        self.assertTrue(self.comparator(txns[0], txns[1]))

if __name__ == '__main__':
    unittest.main()
