import base_runner
import numpy as np
import pandas as pd

import utils
import os
import json
import time
import copy


def find_std_ratio(base, quote):
    df1 = pd.read_csv(f"data\\{base.lower()}-usdt.csv")
    df2 = pd.read_csv(f"data\\{quote.lower()}-usdt.csv")
    df4 = pd.read_csv(f"data\\eth-usdt.csv")
    df1 = df1.fillna(method='ffill')
    df2 = df2.fillna(method='ffill')
    df4 = df4.fillna(method='ffill')
    df3 = pd.merge(df1, df2, on="timestamp")
    df4["price"] = df4["open"]
    df3["price"] = df3["open_x"] / df3["open_y"]

    eth_rolling_std = np.average(
        df4["price"].rolling(5 * 30).std().dropna() / df4["price"].rolling(5 * 30).mean().dropna())

    test_rolling_std = np.average(
        df3["price"].rolling(5 * 30).std().dropna() / df3["price"].rolling(5 * 30).mean().dropna())

    print("-----------------------------------------------------")
    print(base, quote)
    print("eth_avg", np.average(df4["price"]))
    print("eth_min", np.min(df4["price"]))
    print("eth_std", np.std(df4["price"]) / np.average(df4["price"]))
    print("test_avg", np.average(df3["price"]))
    print("test_min", np.min(df3["price"]))
    print("test_std", np.std(df3["price"]) / np.average(df3["price"]))
    print("30M Rolling STD Ratio", test_rolling_std / eth_rolling_std)

    return test_rolling_std / eth_rolling_std


def create_simulation_config(SITE_ID, c):
    fp = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "simulation_configs.json", "w")
    print("create_simulation_config")
    data = {"json_time": time.time()}
    for base in assets_to_simulate:
        for quote in assets_to_simulate:
            if quote == base: continue
            key = base + "-" + quote
            new_c = copy.deepcopy(c)
            new_c["series_std_ratio"] = find_std_ratio(base, quote)
            if base == "MELD" or quote == "MELD":
                new_c["price_recovery_times"] = [2]
            new_c["json_time"] = time.time()
            data[key] = new_c
    json.dump(data, fp)


print_time_series = False
fast_mode = False
ETH_PRICE = 1600
total_jobs = 6


# ADA, AVAX, ETH, MATIC, BNB, BTC, MELD
# slippage for all 10% = $2m (both sides)
# caps = $5m, $20m, $100m
# half life for meld = 1 week


volume_for_slippage_10_percentss = [2_000_000 / ETH_PRICE]
l_factors = [0.25, 0.5, 1, 1.5, 2]

c = {
    "series_std_ratio": [],
    'volume_for_slippage_10_percentss': volume_for_slippage_10_percentss,
    "collaterals": [5_000_000 / ETH_PRICE, 20_000_000 / ETH_PRICE, 100_000_000 / ETH_PRICE],
    'trade_every': 1800,
    'liquidation_incentives': [0],
    "stability_pool_initial_balances": [0],
    'share_institutionals': [0],
    'recovery_halflife_retails': [0],
    "price_recovery_times": [0],
    "l_factors": l_factors,
    "collateral_factor": 0,
    "delays_in_minutes": [0]
}
inv_names = {}
liquidation_incentive = {}
inv_underlying = {}
underlying = {}
decimals = {}
assets_aliases = {}
collateral_factors = {}

assets_to_simulate = ['ADA', 'AVAX', 'ETH', 'MATIC', 'BNB', 'BTC', 'MELD']

for a in assets_to_simulate:
    inv_names[a] = a
    liquidation_incentive[a] = 1
    inv_underlying[a] = a
    underlying[a] = a
    decimals[a] = 0
    assets_aliases[a] = a
    collateral_factors[a] = 1

SITE_ID = "meld_2"
SITE_ID = utils.get_site_id(SITE_ID)

create_simulation_config(SITE_ID, c)
base_runner.create_simulation_results(SITE_ID, ETH_PRICE, total_jobs, collateral_factors, inv_names, print_time_series, fast_mode)
base_runner.create_risk_params(SITE_ID, ETH_PRICE, total_jobs, l_factors, print_time_series)