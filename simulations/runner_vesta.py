import json
import math
import time
import os
import sys
import compound_parser
import base_runner
import copy
import kyber_prices
import utils
import shutil


def create_dex_information(SITE_ID):
    src = 'webserver' + os.path.sep + '2' + os.path.sep + 'dex_liquidity.json'
    dst = SITE_ID
    print(src, dst)
    shutil.copyfile(src, 'webserver' + os.path.sep + dst + os.path.sep + 'dex_liquidity.json')


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
            # new_c["collaterals"] = [6_000_000 / ETH_PRICE, 8_000_000 / ETH_PRICE, 10_000_000 / ETH_PRICE, 12_000_000 / ETH_PRICE]
            new_c["current_debt"] = current_debt / ETH_PRICE
            data[key] = new_c

            stability_pool_initial_balance = stabilityPoolVstBalance[base_id_to_simulation]
            new_c["stability_pool_initial_balances"] = [
                (1 * stability_pool_initial_balance) / current_debt,
                (0.5 * stability_pool_initial_balance) / current_debt,
                (2 * stability_pool_initial_balance) / current_debt]
            # new_c["stability_pool_initial_balances"] = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1]

            share_institutional = (bprotocolVstBalance[base_id_to_simulation] + bprotocolGemBalance[
                base_id_to_simulation]) / stability_pool_initial_balance

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
    new_json = {"json_time": data["json_time"]}
    if "VST" not in data:
        return
    for d in data["VST"]:
        new_json[d] = {}
        new_json[d]["VST"] = data["VST"][d]
    file.close()
    fp = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "usd_volume_for_slippage.json", "w")
    json.dump(new_json, fp)
    fp.close()


def fix_risk_params():
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


def get_vst_price():
    inv_names1 = copy.deepcopy(inv_names)
    underlying1 = copy.deepcopy(underlying)
    decimals1 = copy.deepcopy(decimals)
    inv_names1["USDC"] = '0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8'
    underlying1['0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8'] = '0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8'
    decimals1['0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8'] = 6
    kp = kyber_prices.KyberPrices("42161", inv_names1, underlying1, decimals1)
    vst_price = kp.get_price("USDC", "VST", 100)
    print("vst_price", vst_price)
    return vst_price



lending_platform_json_file = ".." + os.path.sep + "vesta" + os.path.sep + "data.json"
assets_to_simulate = ["ETH", "renBTC", "gOHM", "DPX", "GMX", "VST", "sGLP"]
assets_aliases = {"ETH": "ETH", "renBTC": "BTC", "gOHM": "OHM", "DPX": "DPX", "GMX": "GMX", "VST": "VST", "sGLP": "GLP"}

ETH_PRICE = 1600
SITE_ID = "2"
chain_id = "arbitrum"
platform_prefix = ""
VST = "0x64343594Ab9b56e99087BfA6F2335Db24c2d1F17"
print_time_series = False
total_jobs = 10
l_factors = [0.25, 0.5, 1, 1.5, 2]

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
    SITE_ID = utils.get_site_id(SITE_ID)
    file = open(lending_platform_json_file)
    data = json.load(file)
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

    prices[inv_names["VST"]] = get_vst_price()
    kp = kyber_prices.KyberPrices("42161", inv_names, underlying, decimals)

    base_runner.create_overview(SITE_ID, users_data, totalAssetCollateral, totalAssetBorrow)
    base_runner.create_lending_platform_current_information(SITE_ID, last_update_time, names, inv_names, decimals,
                                                            prices, collateral_factors, collateral_caps, borrow_caps,
                                                            underlying)
    fix_lending_platform_current_information(curveFraxBalance, curveVstBalance)
    base_runner.create_account_information(SITE_ID, users_data, totalAssetCollateral, totalAssetBorrow, inv_names,
                                           assets_liquidation_data, True)
    create_dex_information(SITE_ID)
    create_stability_pool_information(SITE_ID, stabilityPoolVstBalance, stabilityPoolGemBalance, bprotocolVstBalance,
                                      bprotocolGemBalance)
    base_runner.create_oracle_information(SITE_ID, prices, chain_id, names, assets_aliases, kp.get_price)
    base_runner.create_whale_accounts_information(SITE_ID, users_data, assets_to_simulate, True)
    base_runner.create_open_liquidations_information(SITE_ID, users_data, assets_to_simulate)
    base_runner.create_usd_volumes_for_slippage(SITE_ID, chain_id, inv_names, liquidation_incentive, kp.get_price, True)
    fix_usd_volume_for_slippage()
    base_runner.create_assets_std_ratio_information(SITE_ID, ["BTC", "ETH", "OHM", "DPX", "GMX", "USDT", "GLP"],
                                                    [("04", "2022"), ("05", "2022"), ("06", "2022")], True)

    create_simulation_config(SITE_ID, c, ETH_PRICE, assets_to_simulate, assets_aliases, liquidation_incentive,
                             inv_names)
    base_runner.create_simulation_results(SITE_ID, ETH_PRICE, total_jobs, collateral_factors, inv_names,
                                          print_time_series, fast_mode)
    base_runner.create_risk_params(SITE_ID, ETH_PRICE, total_jobs, l_factors, print_time_series)
    fix_risk_params()

    base_runner.create_current_simulation_risk(SITE_ID, ETH_PRICE, users_data, assets_to_simulate, assets_aliases,
                                               collateral_factors, inv_names, liquidation_incentive, total_jobs, True)

    create_glp_data(glp_data)
    utils.update_time_stamps(SITE_ID, last_update_time)
    utils.publish_results(SITE_ID)