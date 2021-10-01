from matplotlib.pyplot import vlines
import yaml

from beancount.core import data
from os import path

RULE_PAYEE = "payee"
RULE_ITEM = "item"
RULE_TXN_TYPE = "txn_type"
RULE_TXN_METHOD = "txn_method"
# for raw file has a column named 收/支, use this to match
RULE_TXN_INOUT = "txn_inout"
# for raw file has a column named 收入, use this to match
RULE_TXN_INPUT = "txn_input"
# for raw file has a column named 支出, use this to match
RULE_TXN_OUTPUT = "txn_output"
RULE_TXN_STATUS = "txn_status"
RULE_TXN_META = "txn_meta"
RULE_TXN_MASK = "txn_mask"
RULE_TXN_EXCLUDE = "txn_exclude"
RULE_START_TIME = "start_time"
RULE_END_TIME = "end_time"
RULE_MINUS_ACCOUNT = "method_account"
RULE_PLUS_ACCOUNT = "target_account"
RULE_SEPERATOR = "seperator"

class RuleMeta(object):

    def __init__(self) -> None:
        super().__init__()
        self.payee = None
        self.item = None
        self.seperator = None
        self.txn_type = None
        self.txn_method = None
        self.txn_inout = None
        self.txn_status = None
        self.start_time = None
        self.end_time = None
        self.method_account = None
        self.target_account = None
        self.txn_meta = None
        self.txn_input = None
        self.txn_output = None
        self.is_mask = None
        self.txn_mask = None
        self.txn_exclude = None

    def get_fields(self):
        return [
            RULE_PAYEE, RULE_ITEM, RULE_TXN_TYPE, RULE_TXN_METHOD,
            RULE_TXN_INOUT, RULE_START_TIME, RULE_END_TIME, RULE_MINUS_ACCOUNT,
            RULE_PLUS_ACCOUNT, RULE_SEPERATOR, RULE_TXN_STATUS, RULE_TXN_META,
            RULE_TXN_INPUT, RULE_TXN_OUTPUT, RULE_TXN_MASK, RULE_TXN_EXCLUDE
        ]

    def is_txn_method(self):
        ans = 0
        for k in self.get_fields():
            if getattr(self, k):
                if k == RULE_TXN_METHOD or k == RULE_MINUS_ACCOUNT:
                    ans += 1
                else:
                    return False
        return ans == 2

    def check(self):
        c = 0
        for k in self.get_fields():
            if k == RULE_PLUS_ACCOUNT or k == RULE_MINUS_ACCOUNT:
                continue
            elif getattr(self, k) is None:
                c += 1

        if c == len(self.get_fields()) - 2:
            # All fileds are none
            return False
        else:
            return True

    def print(self):
        for k in self.get_fields():
            print("{} ==> {}".format(k, getattr(self, k)))

_DEFAULT_MINUS = "default_method_account"
_DEFAULT_PLUS = "default_target_account"

class Ruler(object):

    def __init__(self, filename: str) -> None:
        super().__init__()
        if not path.exists(filename):
            raise Exception("File {} does not exist.".format(filename))

        with open(filename, "r") as f:
            self.config = yaml.load(f, Loader=yaml.FullLoader)
            self.rules = self._convert_to_rules(self.config, filename)
            for rule in self.rules:
                assert rule.check(), rule.print()

    def garther_accounts(self):
        ans = set([self.config[_DEFAULT_MINUS], self.config[_DEFAULT_PLUS]])
        for rule in self.rules:
            minus = getattr(rule, RULE_MINUS_ACCOUNT)
            plus = getattr(rule, RULE_PLUS_ACCOUNT)
            if minus and minus not in ans:
                ans.add(minus)
            if plus and plus not in ans:
                ans.add(plus)
        ans = list(ans)
        ans.sort()
        return ans

    # def add_accounts(self, account_name):
    #     r = RuleMeta()
    #     r.target_account = account_name
    #     self.rules.append(r)


    def _convert_to_rules(self, yaml_config: dict, filename: str):
        if "rules" not in yaml_config:
            raise Exception("No rules exists in {}.".format(filename))

        rules = []
        for config in yaml_config["rules"]:
            rule = RuleMeta()
            for f in rule.get_fields():
                assert isinstance(f, str)
                if f in config:
                    setattr(rule, f, config[f])
            rule.check()
            rules.append(rule)
        return rules

    def _match(self, rule : RuleMeta, meta : data.Meta, func_map=None) -> RuleMeta:
        for k in rule.get_fields():
            # NOTE: all fields defined in a rule need to pass checks to make
            # this rule as a match.
            if k == RULE_MINUS_ACCOUNT: continue
            if k == RULE_PLUS_ACCOUNT: continue
            if k == RULE_SEPERATOR: continue
            if k == RULE_TXN_EXCLUDE: continue

            values = getattr(rule, k)
            if values is None: continue

            if rule.seperator:
                values = [x.strip() for x in values.split(rule.seperator)]
            else:
                values = [values]

            field_check = False
            if k == RULE_TXN_META or k == RULE_TXN_MASK:
                for _, v in meta.items():
                    for val in values:
                        if isinstance(v, str) and isinstance(val, str) and val in v:
                            field_check = True
                            if k == RULE_TXN_MASK:
                                exclude = getattr(rule, RULE_TXN_EXCLUDE)
                                if exclude and exclude in v:
                                    rule.is_mask = False
                                else:
                                    rule.is_mask = True
            else:
                for v in values:
                    if func_map and func_map(k) and v == meta[func_map(k)]:
                        field_check = True
                        break

            if not field_check:
                # If any filed failed to pass the check
                return False

        # All fields passed
        return True

    def match(self, meta: data.Meta, func_map=None) -> RuleMeta:
        # TODO(zhangqiang): support multiple accounts in ont transaction, e.g
        #
        # salary --> checking
        #        --> tax
        #        --> wechat
        # so here we useone minus account, and three plus accounts
        #
        # the syntax for wtring this in yaml would look like this:
        #   - target_account:
        #       - checking
        #       - tax
        #       - wechat
        # It should just work out of box, might need to change the improter a
        # little to make this work
        #
        if func_map is None:
            def f(x): return x
            func_map = f

        ans = RuleMeta()
        ans.method_account = self.config[_DEFAULT_MINUS]
        ans.target_account = self.config[_DEFAULT_PLUS]

        assert ans.method_account
        assert ans.target_account

        # First match only using the txn method
        for rule in self.rules:
            assert isinstance(rule, RuleMeta)
            assert rule.check(), rule.print()
            if rule.is_txn_method():
                key = RULE_TXN_METHOD
                method = getattr(rule, key)
                if func_map and func_map(key) and method == meta[func_map(key)]:
                    ans.method_account = getattr(rule, RULE_MINUS_ACCOUNT)

        assert ans.method_account
        assert ans.target_account

        for rule in self.rules:
            assert isinstance(rule, RuleMeta)
            if rule.is_txn_method(): continue

            assert rule.check(), rule.print()

            # rule.print()
            if self._match(rule, meta, func_map):
                # print("\n\n=============matched===================")
                # rule.print()
                # print(meta)

                # NOTE: stop immediately if the mask rule applied, otherwise keep
                # going down the rule list
                ans.is_mask = rule.is_mask
                if ans.is_mask:
                    break

                method_account = getattr(rule, RULE_MINUS_ACCOUNT)
                target_account = getattr(rule, RULE_PLUS_ACCOUNT)

                if method_account:
                    ans.method_account = method_account

                if target_account:
                    ans.target_account = target_account


                for k in rule.get_fields():
                    if k == RULE_MINUS_ACCOUNT: continue
                    if k == RULE_PLUS_ACCOUNT: continue
                    setattr(ans, k, getattr(rule, k))

                # if ("FIXME" not in ans.method_account and
                #     "FIXME" not in ans.target_account):
                #     break

        assert ans.method_account
        assert ans.target_account
        return ans
