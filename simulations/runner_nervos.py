import glob
import json
import math
import time
import os
import sys
import compound_parser
import base_runner
import copy
import aggregator
import shutil
import datetime
import private_config
import utils


def create_dex_information():
    print("create_dex_information")
    data = {"json_time": time.time()}
    for market in assets_to_simulate:
        data[market] = {"count": 0, "total": 0, "avg": 0, "med": 0,
                        "top_10": 0,
                        "top_5": 0, "top_1": 0, "users": []}

    fp = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "dex_liquidity.json", "w")
    json.dump(data, fp)


def create_simulation_config(SITE_ID, c, ETH_PRICE, assets_to_simulate, assets_aliases, liquidation_incentive,
                             inv_names):
    print("create_simulation_config")
    f1 = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "usd_volume_for_slippage.json")
    jj1 = json.load(f1)

    f2 = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "assets_std_ratio.json")
    jj2 = json.load(f2)
    data = {"json_time": time.time()}
    now_time = time.time()
    for base_to_simulation in assets_to_simulate:
        for quote_to_simulation in jj1[base_to_simulation]:
            print(base_to_simulation, quote_to_simulation)
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

                current_debt = 0
                current_collateral = 0
                for index, row in users_data.iterrows():
                    current_debt += float(row["DEBT_" + base_to_simulation])
                    current_collateral += float(row["COLLATERAL_" + base_to_simulation])
                new_c["current_debt"] = current_debt / ETH_PRICE
                data[key] = new_c

    fp = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "simulation_configs.json", "w")
    json.dump(data, fp)


def get_alert_params():
    alert_params = []
    
    # RISK DAO CHANNEL: send all alerts to risk_dao_channel
    alert_params.append({
        "is_default": True, # is default mean it's the risk dao general channel where all msg are sent
        "tg_bot_id": private_config.risk_dao_bot,
        "tg_channel_id": private_config.risk_dao_channel,
        "oracle_threshold": 3, # oracle threshold is always in absolute
        "slippage_threshold": 10, # liquidity threshold before sending alert
        "only_negative": False, # only send liquidity alert if the new volume < old volume
    })

    # REAL NERVOS ALERT CHANNEL: send only oracle > 3% and liquidity alerts where <-10%
    alert_params.append({
        "is_default": False, # is default mean it's the risk dao general channel where all msg are sent
        "tg_bot_id": private_config.risk_dao_bot,
        "tg_channel_id": private_config.nervos_channel,
        "oracle_threshold": 3, # oracle threshold is always in absolute
        "slippage_threshold": 10, # liquidity threshold before sending alert
        "only_negative": True, # only send liquidity alert if the new volume < old volume
    })

    return alert_params

lending_platform_json_file = ".." + os.path.sep + "Hadouken" + os.path.sep + "data.json"
oracle_json_file = ".." + os.path.sep + "Hadouken" + os.path.sep + "oracle.json"
# aggregator_path = ".." + os.path.sep + "yokaiswap" + os.path.sep + "data.json"
aggregator_path = ".." + os.path.sep + "Hadouken" + os.path.sep + "aggregated_liquidity.json"

assets_to_simulate = ["ETH", "BNB|bsc", "WBTC|eth", "pCKB", "USDC", "USDT"]
assets_aliases = {"ETH": "ETH", "BNB|bsc": "BNB", "WBTC|eth": "BTC", "pCKB": "CKB", "USDC": "USDC", "USDT": "USDC"}
cex_aliases = copy.copy(assets_aliases)

ETH_PRICE = 1600
SITE_ID = "1"
chain_id = "yokaiswap"
platform_prefix = ""
print_time_series = False
total_jobs = 5

alert_mode = False
bot_id = "5789083655:AAH25Cl4ZZ5aGL3PEq0LJlNOvDR8k4a1cK4"
chat_id = "-1001804080202"
send_alerts = False

c = {
    "series_std_ratio": 0,
    'volume_for_slippage_10_percentss': [],
    'trade_every': 1800,
    "collaterals": [1_000_000 / ETH_PRICE, 2_000_000 / ETH_PRICE, 3_000_000 / ETH_PRICE,
                    4_000_000 / ETH_PRICE, 5_000_000 / ETH_PRICE, 6_000_000 / ETH_PRICE,
                    10_000_000 / ETH_PRICE, 15_000_000 / ETH_PRICE, 20_000_000 / ETH_PRICE],
    'liquidation_incentives': [],
    "stability_pool_initial_balances": [0],
    'share_institutionals': [0],
    'recovery_halflife_retails': [0],
    "price_recovery_times": [0],
    "l_factors": [0.25, 0.5, 1, 1.5, 2]
}
l_factors = [0.25, 0.5, 1, 1.5, 2]
old_alerts = {}

if __name__ == '__main__':
    fast_mode = len(sys.argv) > 1
    print("FAST MODE", fast_mode)
    alert_mode = len(sys.argv) > 2
    print("ALERT MODE", alert_mode)
    send_alerts = len(sys.argv) > 3
    print("SEND ALERTS", send_alerts)

    try:
        while True:
            startDate = round(datetime.datetime.now().timestamp())
            if alert_mode:
                # if in alert mode, record monitoring data
                utils.record_monitoring_data({
                    "name": 'Nervos',
                    "status": "running",
                    "lastStart": startDate,
                    'runEvery': 30 * 60
                })

            if os.path.sep in SITE_ID:
                SITE_ID = SITE_ID.split(os.path.sep)[0]

            SITE_ID = utils.get_site_id(SITE_ID)
            file = open(lending_platform_json_file)
            data = json.load(file)

            if os.path.exists(oracle_json_file):
                file = open(oracle_json_file)
                oracle = json.load(file)
                data["prices"] = copy.deepcopy(oracle["prices"])
                print("FAST ORACLE")

            data["totalBorrows"] = "{}"
            data["totalCollateral"] = "{}"

            cp_parser = compound_parser.CompoundParser()
            users_data, assets_liquidation_data, \
            last_update_time, names, inv_names, decimals, collateral_factors, borrow_caps, collateral_caps, prices, \
            underlying, inv_underlying, liquidation_incentive, orig_user_data, totalAssetCollateral, totalAssetBorrow = cp_parser.parse(
                data, False)

            for x in liquidation_incentive:
                liquidation_incentive[x] = 1.1

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

            ETH = "0x9E858A7aAEDf9FDB1026Ab1f77f627be2791e98A"
            BNB = "0xBAdb9b25150Ee75bb794198658A4D0448e43E528"
            USDC = "0x186181e225dc1Ad85a4A94164232bD261e351C33"
            WCKB = "0xC296F806D15e97243A08334256C705bA5C5754CD"
            USDT = "0x8E019acb11C7d17c26D334901fA2ac41C1f44d50"
            BTC = "0x82455018F2c32943b3f12F4e59D0DA2FAf2257Ef"
            CKB = "0x7538C85caE4E4673253fFd2568c1F1b48A71558a"
            
            allTokens = [ETH, BNB, USDC, WCKB, USDT, BTC, CKB]
            ap = aggregator.AggregatorPrices(aggregator_path, inv_names, underlying, inv_underlying, decimals, allTokens)
            base_runner.create_overview(SITE_ID, users_data, totalAssetCollateral, totalAssetBorrow)
            base_runner.create_lending_platform_current_information(SITE_ID, last_update_time, names, inv_names, decimals,
                                                                    prices, collateral_factors, collateral_caps,
                                                                    borrow_caps, underlying)
            base_runner.create_account_information(SITE_ID, users_data, totalAssetCollateral, totalAssetBorrow, inv_names,
                                                assets_liquidation_data)
            base_runner.create_oracle_information(SITE_ID, prices, chain_id, names, cex_aliases, ap.get_price)
            create_dex_information()
            base_runner.create_whale_accounts_information(SITE_ID, users_data, assets_to_simulate)
            base_runner.create_open_liquidations_information(SITE_ID, users_data, assets_to_simulate)
            base_runner.create_usd_volumes_for_slippage(SITE_ID, chain_id, inv_names, liquidation_incentive, ap.get_price)

            if alert_mode:
                d1 = utils.get_file_time(oracle_json_file)
                d1 = min(last_update_time, d1)
                
                alert_params = get_alert_params()
                print('alert_params', alert_params)
                old_alerts = utils.compare_to_prod_and_send_alerts(old_alerts, d1, "nervos", "1", SITE_ID, alert_params, send_alerts)
                endDate =  round(datetime.datetime.now().timestamp())
                utils.record_monitoring_data({
                    "name": 'Nervos',
                    "status": "success",
                    "lastEnd": endDate,
                    "lastDuration": endDate - startDate,
                })
                print("Alert Mode.Sleeping For 30 Minutes")
                time.sleep(30 * 60)
            else:
                base_runner.create_assets_std_ratio_information(SITE_ID, ["ETH", "BNB", "BTC", "CKB", "USDC"],
                                                                [("04", "2022"), ("05", "2022"), ("06", "2022")])
                create_simulation_config(SITE_ID, c, ETH_PRICE, assets_to_simulate, assets_aliases, liquidation_incentive,
                                        inv_names)
                base_runner.create_simulation_results(SITE_ID, ETH_PRICE, total_jobs, collateral_factors, inv_names,
                                                    print_time_series, fast_mode)
                base_runner.create_risk_params(SITE_ID, ETH_PRICE, total_jobs, l_factors, print_time_series)
                base_runner.create_current_simulation_risk(SITE_ID, ETH_PRICE, users_data, assets_to_simulate,
                                                        assets_aliases,
                                                        collateral_factors, inv_names, liquidation_incentive, total_jobs,
                                                        False)

                n = datetime.datetime.now().timestamp()
                d1 = utils.get_file_time(oracle_json_file)
                d0 = min(last_update_time, d1)
                utils.update_time_stamps(SITE_ID, d0)
                utils.publish_results(SITE_ID)
                utils.compare_to_prod_and_send_alerts(old_alerts, d0, "nervos", "1", SITE_ID, "", 10, False)
                if d1 < float('inf'):
                    print("oracle_json_file", round((n - d1) / 60), "Minutes")
                if last_update_time < float('inf'):
                    print("last_update_time", round((n - last_update_time) / 60), "Minutes")
                print("Simulation Ended")
                exit()
    except Exception as error:
        err_msg = 'An exception occurred: {}'.format(error)
        print(err_msg)
        utils.record_monitoring_data({
                    "name": 'Nervos',
                    "status": "error",
                    "error": err_msg
        })
