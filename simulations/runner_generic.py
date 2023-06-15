import base_runner
import stability_report
import base_runner
import utils
import os
import json
import time
import copy


def create_simulation_config(SITE_ID, c, ETH_PRICE, assets_to_simulate, assets_aliases, liquidation_incentive,
                             inv_names):
    fp = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "simulation_configs.json", "w")
    print("create_simulation_config")
    f1 = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "usd_volume_for_slippage.json")
    jj1 = json.load(f1)

    f2 = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "assets_std_ratio.json")
    jj2 = json.load(f2)
    data = {"json_time": time.time()}
    now_time = time.time()
    for base_to_simulation in assets_to_simulate:
        for quote_to_simulation in jj1[base_to_simulation]:
            if assets_aliases[base_to_simulation] != assets_aliases[quote_to_simulation]:
                key = base_to_simulation + "-" + quote_to_simulation
                new_c = copy.deepcopy(c)
                if assets_aliases[base_to_simulation] in jj2 and \
                        assets_aliases[quote_to_simulation] in jj2[assets_aliases[base_to_simulation]]:
                    std_ratio = jj2[assets_aliases[base_to_simulation]][assets_aliases[quote_to_simulation]]
                else:
                    std_ratio = jj2[assets_aliases[quote_to_simulation]][assets_aliases[base_to_simulation]]

                slippage = jj1[base_to_simulation][quote_to_simulation]["volume"] / ETH_PRICE
                li = float(liquidation_incentive[inv_names[base_to_simulation]])
                li = li if li < 1 else li - 1
                new_c["liquidation_incentives"] = [li]
                new_c["series_std_ratio"] = std_ratio
                new_c["volume_for_slippage_10_percentss"] = [slippage]
                new_c["json_time"] = now_time
                new_c["collaterals"] = [1_000_000 / ETH_PRICE, 5_000_000 / ETH_PRICE, 10_000_000 / ETH_PRICE,
                                        15_000_000 / ETH_PRICE, 20_000_000 / ETH_PRICE]

                data[key] = new_c
    json.dump(data, fp)


def create_usd_volumes_for_slippage(SITE_ID, network):
    print("create_usd_volumes_for_slippage")
    data = {}
    for key in network:
        print(key)
        a = key.split("->")
        base = a[0]
        quote = a[1]
        if base not in data:
            data[base] = {}
        data[base][quote] = {"volume":network[key]}

    for base in data.keys():
        m1 = max([data[base][x]["volume"] for x in data[base]])
        m2 = min([data[base][x]["volume"] for x in data[base]])
        data[base]["ADA"] = {"volume": m1}
        data[base]["AVAX"] = {"volume": m2}

    data["ADA"] = {}
    data["ADA"]["BTC"] = {"volume": max([data["USDC"]["BTC"]["volume"], data["ETH"]["BTC"]["volume"]])}
    data["ADA"]["ETH"] = {"volume": max([data["USDC"]["ETH"]["volume"], data["BTC"]["ETH"]["volume"]])}
    data["ADA"]["USDC"] = {"volume": max([data["ETH"]["USDC"]["volume"], data["BTC"]["USDC"]["volume"]])}

    data["AVAX"] = {}
    data["AVAX"]["BTC"] = {"volume": min([data["USDC"]["BTC"]["volume"], data["ETH"]["BTC"]["volume"]])}
    data["AVAX"]["ETH"] = {"volume": min([data["USDC"]["ETH"]["volume"], data["BTC"]["ETH"]["volume"]])}
    data["AVAX"]["USDC"] = {"volume": min([data["ETH"]["USDC"]["volume"], data["BTC"]["USDC"]["volume"]])}

    data["ADA"]["AVAX"] = {"volume": min([data["ADA"][x]["volume"] for x in data["ADA"]])}
    data["AVAX"]["ADA"] = {"volume": min([data["AVAX"][x]["volume"] for x in data["AVAX"]])}

    fp = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "usd_volume_for_slippage.json", "w")
    json.dump(data, fp)
    fp.close()


arbitrum = {
    "ETH->USDC": 10000000,
    "ETH->BTC": 2000000,
    "BTC->ETH": 10000000,
    "BTC->USDC": 3000000,
    "USDC->ETH": 5000000,
    "USDC->BTC": 2200000
}
aurora = {
    "USDC->ETH": 23400,
    "ETH->USDC": 23400,
    "USDC->BTC": 10000,
    "BTC->USDC": 12000,
    "ETH->BTC": 12000,
    "BTC->ETH": 12000}

gnosis = {
    "USDC->BTC": 33901,
    "BTC->USDC": 67280,
    "USDC->ETH": 67280,
    "ETH->USDC": 67280,
    "BTC->ETH": 130222,
    "ETH->BTC": 65372}

fantom = {
    "ETH->USDC": 280000,
    "USDC->ETH": 300000,
    "BTC->USDC": 208000,
    "USDC->BTC": 230000,
    "ETH->BTC": 280000,
    "BTC->ETH": 300000,
}

print_time_series = False
liquidation_df = None
skip = False
calc_pnl = False
network = arbitrum
assets_to_simulate = ["ADA", "BTC", "ETH", "AVAX", "USDC"]
ETH_PRICE = 1600
total_jobs = 5
inv_names = {}
liquidation_incentive = {}
inv_underlying = {}
underlying = {}
decimals = {}
assets_aliases = {}
collateral_factors = {}
fast_mode = False
c = {
    "series_std_ratio": 1,
    'volume_for_slippage_10_percentss': [],
    'trade_every': 1800,
    "collaterals": [],
    'liquidation_incentives': [0.1],
    "stability_pool_initial_balances": [0],
    'share_institutionals': [0],
    'recovery_halflife_retails': [0],
    "price_recovery_times": [0],
    "l_factors": [0.25, 0.5, 1, 1.5, 2],
    "collateral_factor": 0
}

l_factors = [0.25, 0.5, 1, 1.5, 2]
for a in assets_to_simulate:
    inv_names[a] = a
    liquidation_incentive[a] = 1.1
    inv_underlying[a] = a
    underlying[a] = a
    decimals[a] = 0
    assets_aliases[a] = a
    collateral_factors[a] = 1

SITE_ID = "5"
SITE_ID = utils.get_site_id(SITE_ID)

base_runner.create_assets_std_ratio_information(SITE_ID, assets_to_simulate,
                                               [("09", "2022"), ("10", "2022"), ("11", "2022")])
create_usd_volumes_for_slippage(SITE_ID, network)
create_simulation_config(SITE_ID, c, ETH_PRICE, assets_to_simulate, assets_aliases, liquidation_incentive,
                         inv_names)
base_runner.create_simulation_results(SITE_ID, ETH_PRICE, total_jobs, collateral_factors, inv_names, print_time_series,
                                      fast_mode)
base_runner.create_risk_params(SITE_ID, ETH_PRICE, total_jobs, l_factors, print_time_series)
utils.publish_results(SITE_ID)
