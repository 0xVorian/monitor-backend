import json
import math
import time
import os
import sys
import compound_parser
import base_runner
import copy
import kyber_prices
import private_config
import utils
import shutil
import datetime

def create_dex_information(SITE_ID):
    print("create_dex_information")
    data = {"json_time": time.time()}
    for market in assets_to_simulate:
        data[market] = {"count": 0, "total": 0, "avg": 0, "med": 0,
                        "top_10": 0,
                        "top_5": 0, "top_1": 0, "users": []}

    fp = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "dex_liquidity.json", "w")
    json.dump(data, fp)


def create_usd_volumes_for_slippage(SITE_ID):
    src = 'webserver' + os.path.sep + '2' + os.path.sep + 'usd_volume_for_slippage.json'
    dst = SITE_ID
    print(src, dst)
    shutil.copyfile(src, 'webserver' + os.path.sep + dst + os.path.sep + 'usd_volume_for_slippage.json')


def create_stability_pool_information(SITE_ID, stabilityPoolVstBalance, stabilityPoolGemBalance, bprotocolVstBalance,
                                      bprotocolGemBalance):
    data = {"json_time": time.time()}
    data["stabilityPoolVstBalance"] = {names[x]: stabilityPoolVstBalance[x] for x in stabilityPoolVstBalance}
    data["stabilityPoolGemBalance"] = {names[x]: stabilityPoolGemBalance[x] for x in stabilityPoolGemBalance}
    data["bprotocolBalance"] = {names[x]: bprotocolVstBalance[x] for x in bprotocolVstBalance}
    data["bprotocolGemBalance"] = {names[x]: bprotocolGemBalance[x] for x in bprotocolGemBalance}
    fp = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "stability_pool.json", "w")

    json.dump(data, fp)
    fp.close()


def create_simulation_config(SITE_ID, c, ETH_PRICE, assets_to_simulate, assets_aliases, liquidation_incentive,
                             inv_names):
    print("create_simulation_config")
    f1 = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "usd_volume_for_slippage.json")
    jj1 = json.load(f1)

    f2 = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "assets_std_ratio.json")
    jj2 = json.load(f2)
    data = {"json_time": time.time()}
    now_time = time.time()

    # assets_to_simulate = ["gOHM"]
    for base_to_simulation in assets_to_simulate:
        if base_to_simulation != "VST":
            quote_to_simulation = "VST"
            key = base_to_simulation + "-" + quote_to_simulation
            new_c = copy.deepcopy(c)
            if assets_aliases[base_to_simulation] in jj2 and \
                    assets_aliases[quote_to_simulation] in jj2[assets_aliases[base_to_simulation]]:
                std_ratio = jj2[assets_aliases[base_to_simulation]][assets_aliases[quote_to_simulation]]
            else:
                std_ratio = jj2[assets_aliases[quote_to_simulation]][assets_aliases[base_to_simulation]]
            print(base_to_simulation, quote_to_simulation)
            slippage = jj1[base_to_simulation][quote_to_simulation]["volume"] / ETH_PRICE
            li = float(liquidation_incentive[inv_names[base_to_simulation]])
            li = li if li < 1 else li - 1
            new_c["liquidation_incentives"] = [li]
            new_c["series_std_ratio"] = std_ratio
            new_c["volume_for_slippage_10_percentss"] = [slippage]
            new_c["json_time"] = now_time

            new_c["recovery_halflife_retails"] = [80 / 24]
            if base_to_simulation == "DPX":
                new_c["price_recovery_times"] = [2]

            base_id_to_simulation = inv_names[base_to_simulation]

            current_debt = 0
            for index, row in users_data.iterrows():
                if row["COLLATERAL_" + base_to_simulation] > 0:
                    cc = row["DEBT_VST"]
                    if not math.isnan(cc):
                        current_debt += cc

            max_debt = borrow_caps[base_id_to_simulation] * 5
            step_size = (max_debt - current_debt) / 30
            new_c["collaterals"] = [int((current_debt + step_size * i) / ETH_PRICE) for i in range(30)]
            new_c["collaterals"].append(borrow_caps[base_id_to_simulation] / ETH_PRICE)
            if 0 in new_c["collaterals"]:
                new_c["collaterals"].remove(0)
                print("REMOVED")
            # new_c["collaterals"] = [6_000_000 / ETH_PRICE, 8_000_000 / ETH_PRICE, 10_000_000 / ETH_PRICE, 12_000_000 / ETH_PRICE]
            new_c["current_debt"] = current_debt / ETH_PRICE
            data[key] = new_c

            stability_pool_initial_balance = stabilityPoolVstBalance[base_id_to_simulation]
            if current_debt > 0:
                new_c["stability_pool_initial_balances"] = [
                    (1 * stability_pool_initial_balance) / current_debt,
                    (0.5 * stability_pool_initial_balance) / current_debt,
                    (2 * stability_pool_initial_balance) / current_debt]
                # new_c["stability_pool_initial_balances"] = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1]

            print(
                bprotocolVstBalance[base_id_to_simulation],
                bprotocolGemBalance[base_id_to_simulation],
                stability_pool_initial_balance)

            if stability_pool_initial_balance > 0:
                share_institutional = (bprotocolVstBalance[base_id_to_simulation] + bprotocolGemBalance[
                    base_id_to_simulation]) / stability_pool_initial_balance
            else:
                share_institutional = 0

            new_c["share_institutionals"] = [
                1 * share_institutional,
                0.5 * share_institutional,
                min(1, 2 * share_institutional),
                1]
            # new_c["share_institutionals"] = [0]

    fp = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "simulation_configs.json", "w")
    json.dump(data, fp)
    fp.close()


def fix_lending_platform_current_information(curveFraxBalance, curveVstBalance):
    file = open("webserver" + os.sep + SITE_ID + os.sep + "lending_platform_current.json")
    data = json.load(file)
    data["curveFraxBalance"] = curveFraxBalance
    data["curveVstBalance"] = curveVstBalance
    file.close()
    fp = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "lending_platform_current.json", "w")
    json.dump(data, fp)
    fp.close()


def fix_usd_volume_for_slippage():
    file = open("webserver" + os.sep + SITE_ID + os.sep + "usd_volume_for_slippage.json")
    data = json.load(file)
    file.close()
    new_json = {"json_time": data["json_time"]}
    if "VST" not in data:
        return
    for d in data["VST"]:
        new_json[d] = {}
        new_json[d]["VST"] = data["VST"][d]

    new_json["sGLP"] = {}
    new_json["sGLP"]["VST"] = data["VST"]["wBTC"]
    del new_json["wBTC"]
    fp = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "usd_volume_for_slippage.json", "w")
    json.dump(new_json, fp)
    fp.close()


def fix_risk_params():
    print("fix_risk_params")
    file = open("webserver" + os.sep + SITE_ID + os.sep + "risk_params.json")
    data = json.load(file)
    new_json = {"json_time": data["json_time"]}
    for key1 in data:
        if key1 != "json_time":
            new_json[key1] = {"key": []}
            for key2 in data[key1]:
                # "hm-prc-0.0-vfs10p-2715.31583160162-rhr-3.333333333333333-spibr-0.2985054202706127-si-0.2337509781682822"
                params = key2.split("^")
                spibr = float(params[8])
                si = float(params[10])
                for key3 in data[key1][key2]:
                    key3["spibr"] = spibr
                    key3["si"] = si
                    new_json[key1]["key"].append(
                        {"spibr": spibr,
                         "si": si,
                         "dc": key3["dc"],
                         "lf": key3["lf"],
                         "md": key3["md"],
                         "li": key3["li"]})

    file.close()
    fp = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "risk_params.json", "w")
    json.dump(new_json, fp)
    fp.close()


def create_glp_data(glp_data):
    data = {"json_time": time.time()}
    data["glp_data"] = glp_data
    fp = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "glp_data.json", "w")
    json.dump(data, fp)
    fp.close()


def get_frax_price():
    inv_names1 = copy.deepcopy(inv_names)
    underlying1 = copy.deepcopy(underlying)
    decimals1 = copy.deepcopy(decimals)

    inv_names1["USDC"] = '0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8'
    underlying1['0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8'] = '0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8'
    decimals1['0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8'] = 6

    inv_names1["FRAX"] = '0x17FC002b466eEc40DaE837Fc4bE5c67993ddBd6F'
    underlying1['0x17FC002b466eEc40DaE837Fc4bE5c67993ddBd6F'] = '0x17FC002b466eEc40DaE837Fc4bE5c67993ddBd6F'
    decimals1['0x17FC002b466eEc40DaE837Fc4bE5c67993ddBd6F'] = 18

    kp = kyber_prices.KyberPrices("42161", inv_names1, underlying1, decimals1)
    vst_price = kp.get_price("USDC", "FRAX", 10)
    print("frax price", vst_price)
    return vst_price

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

    # REAL VESTA ALERT CHANNEL: send only oracle > 3% and liquidity alerts where <-10%
    alert_params.append({
        "is_default": False, # is default mean it's the risk dao general channel where all msg are sent
        "tg_bot_id": private_config.risk_dao_bot,
        "tg_channel_id": private_config.vesta_channel,
        "oracle_threshold": 3, # oracle threshold is always in absolute
        "slippage_threshold": 10, # liquidity threshold before sending alert
        "only_negative": True, # only send liquidity alert if the new volume < old volume
    })

    return alert_params

lending_platform_json_file = ".." + os.path.sep + "vesta" + os.path.sep + "data.json"
oracle_json_file = ".." + os.path.sep + "vesta" + os.path.sep + "oracle.json"

assets_to_simulate = ["ETH", "gOHM", "DPX", "GMX", "VST", "sGLP"]
assets_aliases = {"ETH": "ETH", "gOHM": "OHM", "DPX": "DPX", "GMX": "GMX", "VST": "VST", "sGLP": "GLP"}

ETH_PRICE = 1600
SITE_ID = "2"
chain_id = "arbitrum"
platform_prefix = ""
VST = "0x64343594Ab9b56e99087BfA6F2335Db24c2d1F17"
print_time_series = False
total_jobs = 8
l_factors = [0.25, 0.5, 1, 1.5, 2]

alert_mode = True
send_alerts = False
old_alerts = {}

c = {
    "series_std_ratio": 0,
    'volume_for_slippage_10_percentss': [],
    'trade_every': 1800,
    "collaterals": [],
    'liquidation_incentives': [],
    "stability_pool_initial_balances": [0],
    'share_institutionals': [0],
    'recovery_halflife_retails': [0],
    "price_recovery_times": [0],
    "l_factors": [0.25, 0.5, 1, 1.5, 2]
}

if __name__ == '__main__':
    fast_mode = len(sys.argv) > 1
    print("FAST MODE", fast_mode)
    alert_mode = len(sys.argv) > 2
    print("ALERT MODE", alert_mode)
    send_alerts = len(sys.argv) > 3
    print("SEND ALERTS", send_alerts)
    
    while True:
        startDate = round(datetime.datetime.now().timestamp())
        if alert_mode:
            # if in alert mode, record monitoring data
            utils.record_monitoring_data({
                "name": 'Vesta',
                "status": "running",
                "lastStart": startDate,
                'runEvery': 30 * 60
            })
        if os.path.sep in SITE_ID:
            SITE_ID = SITE_ID.split(os.path.sep)[0]

        SITE_ID = utils.get_site_id(SITE_ID)
        file = open(lending_platform_json_file)
        data = json.load(file)

        # base_runner.create_assets_std_ratio_information(SITE_ID, ["ETH", "OHM", "DPX", "GMX", "USDT", "GLP"],
        #                                                 [("09", "2022"), ("10", "2022"), ("11", "2022")], True)
        #
        # print("CCCCCCCC")
        #
        # base_runner.create_assets_std_ratio_information(SITE_ID, ["ETH", "OHM", "DPX", "GMX", "USDT", "GLP"],
        #                                                 [("04", "2022"), ("05", "2022"), ("06", "2022")], True)

        # exit()
        if os.path.exists(oracle_json_file):
            file = open(oracle_json_file)
            oracle = json.load(file)
            data["prices"] = copy.deepcopy(oracle["prices"])
            print("FAST ORACLE")

        data["collateralFactors"] = data["collateralFactors"].replace("}",
                                                                    ",'0x64343594Ab9b56e99087BfA6F2335Db24c2d1F17':0}")
        data["totalCollateral"] = data["totalCollateral"].replace("}",
                                                                ",'0x64343594Ab9b56e99087BfA6F2335Db24c2d1F17':'0'}")
        data["totalBorrows"] = data["totalBorrows"].replace("}", ",'0x64343594Ab9b56e99087BfA6F2335Db24c2d1F17':'0'}")


        cp_parser = compound_parser.CompoundParser()
        users_data, assets_liquidation_data, \
        last_update_time, names, inv_names, decimals, collateral_factors, borrow_caps, collateral_caps, prices, \
        underlying, inv_underlying, liquidation_incentive, orig_user_data, totalAssetCollateral, totalAssetBorrow = cp_parser.parse(
            data, True)

        stabilityPoolVstBalance = eval(data["stabilityPoolVstBalance"])
        stabilityPoolGemBalance = eval(data["stabilityPoolGemBalance"])
        bprotocolVstBalance = eval(data["bprotocolVstBalance"])
        bprotocolGemBalance = eval(data["bprotocolGemBalance"])
        glp_data = eval(data["glpData"])

        for i_d in stabilityPoolVstBalance:
            stabilityPoolVstBalance[i_d] = prices[inv_names["VST"]] * int(stabilityPoolVstBalance[i_d], 16) / 10 ** (
                decimals[inv_names["VST"]])

        for i_d in stabilityPoolGemBalance:
            stabilityPoolGemBalance[i_d] = prices[i_d] * int(stabilityPoolGemBalance[i_d], 16) / 10 ** (decimals[i_d])

        for i_d in bprotocolVstBalance:
            bprotocolVstBalance[i_d] = prices[inv_names["VST"]] * int(bprotocolVstBalance[i_d], 16) / 10 ** (
                decimals[inv_names["VST"]])

        for i_d in bprotocolGemBalance:
            bprotocolGemBalance[i_d] = int(bprotocolGemBalance[i_d], 16) / 10 ** (decimals[inv_names["VST"]])


        curveFraxBalance = eval(data["curveFraxBalance"])
        curveVstBalance = eval(data["curveVstBalance"])

        prices[inv_names["VST"]] = prices[inv_names["VST"]] * get_frax_price()
        kp = kyber_prices.KyberPrices("42161", inv_names, underlying, decimals)

        base_runner.create_overview(SITE_ID, users_data, totalAssetCollateral, totalAssetBorrow)
        base_runner.create_lending_platform_current_information(SITE_ID, last_update_time, names, inv_names, decimals,
                                                                prices, collateral_factors, collateral_caps,
                                                                borrow_caps,
                                                                underlying)
        fix_lending_platform_current_information(curveFraxBalance, curveVstBalance)
        base_runner.create_account_information(SITE_ID, users_data, totalAssetCollateral, totalAssetBorrow, inv_names,
                                            assets_liquidation_data, True)
        create_dex_information(SITE_ID)
        create_stability_pool_information(SITE_ID, stabilityPoolVstBalance, stabilityPoolGemBalance,
                                        bprotocolVstBalance,
                                        bprotocolGemBalance)
        base_runner.create_oracle_information(SITE_ID, prices, chain_id, names, assets_aliases, kp.get_price)
        base_runner.create_whale_accounts_information(SITE_ID, users_data, assets_to_simulate, True)
        base_runner.create_open_liquidations_information(SITE_ID, users_data, assets_to_simulate)

        inv_names["wBTC"] = '0x2f2a2543B76A4166549F7aaB2e75Bef0aefC5B0f'
        underlying['0x2f2a2543B76A4166549F7aaB2e75Bef0aefC5B0f'] = '0x2f2a2543B76A4166549F7aaB2e75Bef0aefC5B0f'
        decimals['0x2f2a2543B76A4166549F7aaB2e75Bef0aefC5B0f'] = 8
        lic = float(liquidation_incentive[inv_names["sGLP"]])
        llc = lic if lic >= 1 else 1 + lic
        liquidation_incentive['0x2f2a2543B76A4166549F7aaB2e75Bef0aefC5B0f'] = llc

        kp.inv_names = inv_names
        kp.underlyin = underlying
        kp.decimals = decimals
        base_runner.create_usd_volumes_for_slippage(SITE_ID, chain_id, inv_names, liquidation_incentive, kp.get_price, True)
        fix_usd_volume_for_slippage()

        del underlying[inv_names["wBTC"]]
        del decimals[inv_names["wBTC"]]
        del inv_names["wBTC"]

        if alert_mode:
            d1 = utils.get_file_time(oracle_json_file)
            d1 = min(last_update_time, d1)

            alert_params = get_alert_params()
            print('alert_params', alert_params)
            old_alerts = utils.compare_to_prod_and_send_alerts(old_alerts, d1, "vesta", "2", SITE_ID, alert_params, send_alerts)
            endDate =  round(datetime.datetime.now().timestamp())
            utils.record_monitoring_data({
                "name": 'Vesta',
                "status": "success",
                "lastEnd": endDate,
                "lastDuration": endDate - startDate,
            })
            print("Alert Mode.Sleeping For 30 Minutes")
            time.sleep(30 * 60)
        else:
            base_runner.create_assets_std_ratio_information(SITE_ID, ["ETH", "OHM", "DPX", "GMX", "USDT", "GLP"],
                                                            [("09", "2022"), ("10", "2022"), ("11", "2022")], True)
            create_simulation_config(SITE_ID, c, ETH_PRICE, assets_to_simulate, assets_aliases, liquidation_incentive,
                                    inv_names)
            base_runner.create_simulation_results(SITE_ID, ETH_PRICE, total_jobs, collateral_factors, inv_names,
                                                print_time_series, fast_mode)
            base_runner.create_risk_params(SITE_ID, ETH_PRICE, total_jobs, l_factors, print_time_series)
            fix_risk_params()

            base_runner.create_current_simulation_risk(SITE_ID, ETH_PRICE, users_data, assets_to_simulate,
                                                    assets_aliases,
                                                    collateral_factors, inv_names, liquidation_incentive, total_jobs,
                                                    True)

            create_glp_data(glp_data)
            n = datetime.datetime.now().timestamp()
            d1 = utils.get_file_time(oracle_json_file)
            d0 = min(last_update_time, d1)
            utils.update_time_stamps(SITE_ID, d0)
            utils.publish_results(SITE_ID)
            # utils.compare_to_prod_and_send_alerts(old_alerts, d1, "vesta", "2", SITE_ID, "", 10, False)
            if d1 < float('inf'):
                print("oracle_json_file", round((n - d1) / 60), "Minutes")
            if last_update_time < float('inf'):
                print("last_update_time", round((n - last_update_time) / 60), "Minutes")
            print("Simulation Ended")
            exit()
