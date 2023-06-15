import datetime
import kyber_prices
import shutil
import glob
import compound_parser
import stability_report
import numpy as np
import utils
import time
import pandas as pd
import os
import json
import aggregator
import sliipage_utils
import traceback
import copy
import base_runner
import sys
import private_config


def overwrite_dex_prices():
    oracle_price_file = "webserver" + os.path.sep + SITE_ID + os.path.sep + "oracles.json"
    oracle_data = json.load(open(oracle_price_file))
    dex_price_file = ".." + os.path.sep + "meld" + os.path.sep + "liquidity" + os.path.sep + "dex_price.json"
    dex_price_data = json.load(open(dex_price_file))
    for p in oracle_data:
        if p != "json_time":
            oracle_data[p]["dex_price"] = dex_price_data[p]["priceUSD"]

    fp = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "oracles.json", "w")
    json.dump(oracle_data, fp)
    fp.close()

def prepare_date_file():
    files = glob.glob(".." + os.path.sep + "meld" + os.path.sep + "history-src" + os.path.sep + "*.*")
    for file in files:
        df = pd.read_csv(file)
        price_field_name = [x for x in df.columns if "price" in x][0]
        new_df = []
        last_block_number = df["Block number"].min()
        last_timestamp_x = 0
        last_bid_price = 0
        last_ask_price = 0

        for index, row in df.iterrows():
            while row["Block number"] > last_block_number:
                new_row = {}
                new_row["timestamp_x"] = last_timestamp_x
                new_row["Block number"] = last_block_number
                new_row["bid_price"] = last_bid_price
                new_row["ask_price"] = last_ask_price
                new_df.append(new_row)
                last_block_number += 1

            last_timestamp_x = row["timestamp"]
            last_bid_price = row[price_field_name]
            last_ask_price = row[price_field_name]

        df = pd.DataFrame(new_df)
        print(os.path.basename(file), datetime.date.fromtimestamp(df["timestamp_x"].min()),
              datetime.date.fromtimestamp(df["timestamp_x"].max()))
        df.to_csv("data" + os.path.sep + "data_unified_" + os.path.basename(file).split("-")[0] + "ADA.csv")


def calc_series_std_ratio(base, quote, source):
    print(base, quote)
    if base == "ADA":
        test = pd.read_csv("data" + os.path.sep + "data_unified_" + quote + "ADA.csv")
        test["price"] = 1 / ((test["bid_price"] + test["ask_price"]) * 0.5)
    elif quote == "ADA":
        test = pd.read_csv("data" + os.path.sep + "data_unified_" + base + "ADA.csv")
        test["price"] = (test["bid_price"] + test["ask_price"]) * 0.5
    else:
        test1 = pd.read_csv("data" + os.path.sep + "data_unified_" + base + "ADA.csv")
        test1["price"] = (test1["bid_price"] + test1["ask_price"]) * 0.5

        test2 = pd.read_csv("data" + os.path.sep + "data_unified_" + quote + "ADA.csv")
        test2["price"] = (test2["bid_price"] + test2["ask_price"]) * 0.5
        test = test1.merge(test2, how='inner', left_on=['Block number'], right_on=['Block number'])
        print(len(test1), len(test2), len(test))
        test["price"] = test["price_x"] / test["price_y"]

    source_rolling_std = np.average(
        source["price"].rolling(5 * 30).std().dropna() / source["price"].rolling(5 * 30).mean().dropna())

    test_rolling_std = np.average(
        test["price"].rolling(5 * 30).std().dropna() / test["price"].rolling(5 * 30).mean().dropna())

    source_std = np.std(source["price"]) / np.average(source["price"])
    test_std = np.std(test["price"]) / np.average(test["price"])

    print("source_avg", np.average(source["price"]))
    print("source_min", np.min(source["price"]))
    print("source_std", source_std)
    print("source_rolling_std", source_rolling_std)

    print("test_avg", np.average(test["price"]))
    print("test_min", np.min(test["price"]))
    print("test_std", test_std)
    print("test_rolling_std", test_rolling_std)

    print("30M Rolling STD Ratio", round(test_rolling_std / source_rolling_std, 2))
    print("STD Ratio", round(test_std / source_std, 2))
    print()
    return test_rolling_std / source_rolling_std


def create_assets_std_ratio_information(SITE_ID, assets):
    print("create_assets_std_ratio_information")
    data = {"json_time": time.time()}
    dates = ["2022_09", "2022_10", "2022_11"]
    df1 = pd.concat((pd.read_csv("data" + os.path.sep + "data_unified_" + f + "_ETHUSDT.csv") for f in dates), ignore_index=True)
    df1 = df1.sort_values("timestamp_x")
    df1["price"] = (df1["bid_price"] + df1["ask_price"]) * 0.5
    for base in assets:
        for quote in assets:
            if base != quote:
                if base not in data:
                    data[base] = {}
                std = calc_series_std_ratio(base, quote, df1)
                data[base][quote] = std

    fp = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "assets_std_ratio.json", "w")
    json.dump(data, fp)
    fp.close()

def create_simulation_config(SITE_ID, c, ETH_PRICE, assets_to_simulate, assets_aliases, liquidation_incentive, inv_names):
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

                new_c['price_recovery_times'] = [2]
                if base_to_simulation in ["ADA", "iUSD", "iBTC"] and quote_to_simulation in ["ADA", "iUSD", "iBTC"]:
                    new_c['price_recovery_times'] = [0]
                elif base_to_simulation in ["ADA", "iUSD", "iBTC"]:
                    new_c["volume_for_slippage_10_percents_price_drop"] = jj1["ADA"][quote_to_simulation]["volume"] / ETH_PRICE
                elif quote_to_simulation in ["ADA", "iUSD", "iBTC"]:
                    new_c["volume_for_slippage_10_percents_price_drop"] = jj1[base_to_simulation]["ADA"]["volume"] / ETH_PRICE

                new_c["collaterals"] = [5_0000 / ETH_PRICE, 10_000 / ETH_PRICE, 20_000 / ETH_PRICE,
                                        30_000 / ETH_PRICE, 40_000 / ETH_PRICE,
                                        50_000 / ETH_PRICE, 60_000 / ETH_PRICE, 70_000 / ETH_PRICE,
                                        80_000 / ETH_PRICE, 90_000 / ETH_PRICE,
                                        100_000 / ETH_PRICE, 250_000 / ETH_PRICE, 500_000 / ETH_PRICE,
                                        750_000 / ETH_PRICE, 1_000_000 / ETH_PRICE, 5_000_000 / ETH_PRICE,
                                        10_000_000 / ETH_PRICE, 15_000_000 / ETH_PRICE, 20_000_000 / ETH_PRICE]

                # if base_to_simulation in ["ADA", "iUSD"] and quote_to_simulation in ["ADA", "iUSD"]:
                #     new_c['price_recovery_times'] = [0]
                # else:
                #     new_c['price_recovery_times'] = [2]

                current_debt = 0
                for index, row in users_data.iterrows():
                    current_debt += float(row["DEBT_" + base_to_simulation])

                new_c["current_debt"] = current_debt / ETH_PRICE
                print(new_c["current_debt"])

                data[key] = new_c

    fp = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "simulation_configs.json", "w")
    json.dump(data, fp)


def fix_lending_platform_current_information(protocolFees, magicNumber, liquidationDelay, liquidationIncentive):
    file = open("webserver" + os.sep + SITE_ID + os.sep + "lending_platform_current.json")
    data = json.load(file)
    data["protocolFees"] = float(protocolFees)
    data["magicNumber"] = float(magicNumber)
    data["liquidationDelay"] = liquidationDelay
    data["liquidationIncentive"] = float(liquidationIncentive)
    file.close()
    fp = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "lending_platform_current.json", "w")
    json.dump(data, fp)
    fp.close()

ETH_PRICE = 1600
chain_id = "cardano"
ADA_TO_USD = 3
c = {
    "series_std_ratio": 1,
    'volume_for_slippage_10_percentss': [],
    'trade_every': 1800,
    "collaterals": [],
    'liquidation_incentives': [0.1],
    "stability_pool_initial_balances": [0],
    'share_institutionals': [0],
    'recovery_halflife_retails': [0],
    "price_recovery_times": [2],
    "delays_in_minutes": [5],
    "l_factors": [0.25, 0.5, 1, 1.5, 2],
    "collateral_factor": 0
}
l_factors = [0.25, 0.5, 1, 1.5, 2]
if __name__ == '__main__':
    fast_mode = len(sys.argv) > 1
    print("FAST MODE", fast_mode)
    alert_mode = len(sys.argv) > 2
    print("ALERT MODE", alert_mode)
    send_alerts = len(sys.argv) > 3
    print("SEND ALERTS", send_alerts)

    print_time_series = False
    skip = False
    calc_pnl = False
    SITE_ID = "5"
    SITE_ID = utils.get_site_id(SITE_ID)

    assets_to_simulate = ["ADA", "WRT", "MIN", "MELD", "iUSD", "INDY", "HOSKY", "COPI", "C3", "WMT"]
    ETH_PRICE = 1600
    total_jobs = 5
    assets_aliases = {}

    for a in assets_to_simulate:
        assets_aliases[a] = a

    # get slippage data from meld directory
    shutil.copyfile(".." + os.path.sep + "meld" + os.path.sep + "liquidity" + os.path.sep + "usd_volume_for_slippage.json",
                     "webserver" + os.path.sep + SITE_ID + os.path.sep + 'usd_volume_for_slippage.json')

    lending_platform_json_file = ".." + os.path.sep + "meld" + os.path.sep + "user-data" + os.path.sep + "data.json"
    file = open(lending_platform_json_file)
    data = json.load(file)
    file.close()

    protocol_fees = data['protocolFees']
    magic_number = private_config.meld_magic_number

    # substract protocol fees for each liquidation incentives
    source_liquidation_incentive = 0
    for a in data["liquidationIncentive"]:
        source_liquidation_incentive = data["liquidationIncentive"][a]
        data["liquidationIncentive"][a] = float(data["liquidationIncentive"][a]) - magic_number
        print('liquidation incentives change from', source_liquidation_incentive, 'to', data["liquidationIncentive"][a], 'for asset', a, 'using protocol fees:', protocol_fees)

    cp_parser = compound_parser.CompoundParser()
    users_data, assets_liquidation_data, \
    last_update_time, names, inv_names, decimals, collateral_factors, borrow_caps, collateral_caps, prices, \
    underlying, inv_underlying, liquidation_incentive, orig_user_data, totalAssetCollateral, totalAssetBorrow = cp_parser.parse(
        data)

    users_data["nl_user_collateral"] = 0
    users_data["nl_user_debt"] = 0

    for base_to_simulation in assets_to_simulate:
        users_data["NL_COLLATERAL_" + base_to_simulation] = users_data["NO_CF_COLLATERAL_" + base_to_simulation]
        users_data["NL_DEBT_" + base_to_simulation] = users_data["DEBT_" + base_to_simulation]
        users_data["MIN_" + base_to_simulation] = users_data[
            ["NO_CF_COLLATERAL_" + base_to_simulation, "DEBT_" + base_to_simulation]].min(axis=1)

        users_data["NL_COLLATERAL_" + base_to_simulation] -= users_data["MIN_" + base_to_simulation]
        users_data["NL_DEBT_" + base_to_simulation] -= users_data["MIN_" + base_to_simulation]
        users_data["nl_user_collateral"] += users_data["NL_COLLATERAL_" + base_to_simulation]
        users_data["nl_user_debt"] += users_data["NL_DEBT_" + base_to_simulation]


    prepare_date_file()
    
    base_runner.create_overview(SITE_ID, users_data, totalAssetCollateral, totalAssetBorrow)
    base_runner.create_lending_platform_current_information(SITE_ID, last_update_time, names, inv_names, decimals,
                                                                prices, collateral_factors, collateral_caps, borrow_caps,
                                                                underlying)
    
    fix_lending_platform_current_information(protocol_fees, magic_number, c["delays_in_minutes"], source_liquidation_incentive)
    base_runner.create_account_information(SITE_ID, users_data, totalAssetCollateral, totalAssetBorrow, inv_names, assets_liquidation_data, False)
    
    base_runner.create_oracle_information(SITE_ID, prices, chain_id, names, assets_aliases, None)
    # must overwrite dex prices with the data from the file generated by the js scripts
    overwrite_dex_prices()

    base_runner.create_whale_accounts_information(SITE_ID, users_data, assets_to_simulate)
    base_runner.create_open_liquidations_information(SITE_ID, users_data, assets_to_simulate)
    

    create_assets_std_ratio_information(SITE_ID, assets_to_simulate)

    create_simulation_config(SITE_ID, c, ETH_PRICE, assets_to_simulate, assets_aliases, liquidation_incentive, inv_names)
    
    base_runner.create_simulation_results(SITE_ID, ETH_PRICE, total_jobs, collateral_factors, inv_names, print_time_series, fast_mode)
    base_runner.create_risk_params(SITE_ID, ETH_PRICE, total_jobs, l_factors, print_time_series)
    
    base_runner.create_current_simulation_risk(SITE_ID, ETH_PRICE, users_data, assets_to_simulate, assets_aliases, collateral_factors, inv_names, liquidation_incentive, total_jobs, False)
    
    utils.publish_results(SITE_ID, '5/staging')

