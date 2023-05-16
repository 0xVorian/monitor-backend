import numpy as np

import base_runner
import utils
import os
import json
import time
import copy


def create_simulation_config(SITE_ID, c):
    fp = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "simulation_configs.json", "w")
    print("create_simulation_config")
    data = {"json_time": time.time()}
    for trade_every in trade_everys:
        key = "BTC-" + str(trade_every)
        new_c = copy.deepcopy(c)
        new_c["trade_every"] = int(trade_every)
        new_c["json_time"] = time.time()
        data[key] = new_c
    json.dump(data, fp)


print_time_series = True
fast_mode = False
ETH_PRICE = 1600
total_jobs = 6

trade_everys = [1800, 1800 * 2, 1800 * 5, 1800 * 10]
series_std_ratios = [0.76]
volume_for_slippage_10_percentss = [i / ETH_PRICE for i in np.arange(100_000, 20_000_000 , 100_000)]
l_factors =  [1]
c = {
    "series_std_ratio": 0.76,
    'volume_for_slippage_10_percentss': volume_for_slippage_10_percentss,
    "collaterals": [100_000_000 / ETH_PRICE],
    'trade_every': 0,
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

assets_to_simulate = ['BTC', 'USDT']

for a in assets_to_simulate:
    inv_names[a] = a
    liquidation_incentive[a] = 1
    inv_underlying[a] = a
    underlying[a] = a
    decimals[a] = 0
    assets_aliases[a] = a
    collateral_factors[a] = 1

SITE_ID = "flare"
SITE_ID = utils.get_site_id(SITE_ID)

create_simulation_config(SITE_ID, c)
base_runner.create_simulation_results(SITE_ID, ETH_PRICE, total_jobs, collateral_factors, inv_names, print_time_series, fast_mode)
base_runner.create_risk_params(SITE_ID, ETH_PRICE, total_jobs, l_factors, print_time_series)