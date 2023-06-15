import json
import pandas as pd
import numpy as np


class CompoundParser:
    names = None
    inv_names = None
    decimals = None
    collateral_factors = None
    borrow_caps = None
    collateral_caps = None
    prices = None
    underlying = None
    inv_underlying = None
    liquidation_incentive = None
    totalAssetBorrow = None
    totalAssetCollateral = None

    def __init__(self):
        pass

    def get_total_bad_debt(self, users, asset, price_factor):
        total_bad_debt = 0
        assets_total_bad_debt = {}
        for user in users:
            user_collateral = 0
            user_debt = 0
            user_assets_debt = {}

            collateral_balances = users[user]["collateralBalances"]
            for asset_id in collateral_balances:
                c = int(collateral_balances[asset_id] * self.prices[asset_id]
                        * float(self.collateral_factors[asset_id]))
                if asset == self.names[asset_id]:
                    c *= price_factor
                user_collateral += c

            borrow_balances = users[user]["borrowBalances"]
            for asset_id in borrow_balances:
                c = int(borrow_balances[asset_id] * self.prices[asset_id])
                if asset == self.names[asset_id]:
                    c *= price_factor
                user_debt += c
                user_assets_debt[asset_id] = c

            if user_debt > user_collateral:
                total_bad_debt += user_debt
                for asset_id in user_assets_debt:
                    if asset_id not in assets_total_bad_debt:
                        assets_total_bad_debt[asset_id] = 0
                    assets_total_bad_debt[asset_id] += user_assets_debt[asset_id]

        return total_bad_debt, assets_total_bad_debt

    def parse(self, data, is_stable=False):

        last_update_time = data["lastUpdateTime"]
        self.names = eval(str(data["names"]))
        self.inv_names = {v: k for k, v in self.names.items()}
        self.decimals = eval(str(data["decimals"]))
        for x in self.decimals:
            self.decimals[x] = int(self.decimals[x])
        self.collateral_factors = eval(str(data["collateralFactors"]))
        self.borrow_caps = eval(str(data["borrowCaps"]))
        self.collateral_caps = eval(str(data["collateralCaps"]))
        self.prices = eval(str(data["prices"]))
        self.underlying = eval(str(data["underlying"]))
        self.inv_underlying = {v: k for k, v in self.underlying.items()}
        self.liquidation_incentive = eval(str(data["liquidationIncentive"]))

        self.totalAssetBorrow = eval(str(data["totalBorrows"]))
        self.totalAssetCollateral = eval(str(data["totalCollateral"]))

        for i_d in self.prices:
            self.prices[i_d] = int(self.prices[i_d], 16) / 10 ** (36 - self.decimals[i_d])

        for i_d in self.collateral_caps:
            self.collateral_caps[i_d] = self.prices[i_d] * int(self.collateral_caps[i_d], 16) / 10 ** (self.decimals[i_d])
        if not is_stable:
            for i_d in self.borrow_caps:
                self.borrow_caps[i_d] = self.prices[i_d] * int(self.borrow_caps[i_d], 16) / 10 ** (self.decimals[i_d])
        else:
            for i_d in self.borrow_caps:
                self.borrow_caps[i_d] = int(self.borrow_caps[i_d], 16) / 10 ** (self.decimals[self.inv_names["VST"]])

        for i_d in self.totalAssetCollateral:
            self.totalAssetCollateral[i_d] = self.prices[i_d] * int(self.totalAssetCollateral[i_d], 16) / 10 ** (self.decimals[i_d])

        for i_d in self.totalAssetBorrow:
            self.totalAssetBorrow[i_d] = self.prices[i_d] * int(self.totalAssetBorrow[i_d], 16) / 10 ** (self.decimals[i_d])

        users = str(data["users"])
        users = users.replace("true", "True")
        users = users.replace("false", "False")
        users = eval(str(users))
        users_data = []
        orig_user_data = []
        for user in users:
            user_collateral = 0
            uset_no_cf_collateral = 0
            user_debt = 0
            user_data = {"user": user}
            collateral_balances = users[user]["collateralBalances"]
            for asset_id in collateral_balances:
                collateral_balances[asset_id] = int(collateral_balances[asset_id], 16) / 10 ** self.decimals[asset_id]
                user_collateral += collateral_balances[asset_id] * self.prices[asset_id] * float(self.collateral_factors[asset_id])

                uset_no_cf_collateral += collateral_balances[asset_id] * self.prices[asset_id]
                user_data["COLLATERAL_" + self.names[asset_id]] = collateral_balances[asset_id] * self.prices[asset_id] * float(self.collateral_factors[asset_id])
                user_data["NO_CF_COLLATERAL_" + self.names[asset_id]] = collateral_balances[asset_id] * self.prices[asset_id]

            user_data["user_collateral"] = user_collateral
            user_data["user_no_cf_collateral"] = uset_no_cf_collateral

            borrow_balances = users[user]["borrowBalances"]
            for asset_id in borrow_balances:
                borrow_balances[asset_id] = int(borrow_balances[asset_id], 16) / 10 ** self.decimals[asset_id]
                user_debt += borrow_balances[asset_id] * self.prices[asset_id]
                user_data["DEBT_" + self.names[asset_id]] = borrow_balances[asset_id] * self.prices[asset_id]

            user_data["user_debt"] = user_debt

            users_data.append(user_data)
        assets_liquidation_data = {}
        assets_to_check = self.names.values()
        for asset in assets_to_check:
            results = {}
            asset_price = self.prices[self.inv_names[asset]]
            for i in reversed(np.arange(0, 5, 0.1)):
                users_total_bad_debt, users_assets_total_bad_debt = self.get_total_bad_debt(users, asset, i)
                key = asset_price * i
                for asset_id in users_assets_total_bad_debt:
                    asset_name = self.names[asset_id]
                    if asset_name != asset:
                        if asset_name not in results:
                            results[asset_name] = {}
                        results[asset_name][key] = users_assets_total_bad_debt[asset_id]

            assets_liquidation_data[self.inv_names[asset]] = results

            users_data = pd.DataFrame(users_data)
            orig_user_data = pd.DataFrame(orig_user_data)

        return users_data, assets_liquidation_data, last_update_time, self.names, self.inv_names, self.decimals,\
            self.collateral_factors, self.borrow_caps, self.collateral_caps, self.prices, self.underlying, \
            self.inv_underlying, self.liquidation_incentive, orig_user_data, self.totalAssetCollateral, self.totalAssetBorrow
