import json
import math
import time
import numpy as np
import os
import copy
import kyber_prices
import cex_prices
import pandas as pd
import utils
#import download_datasets
from joblib import Parallel, delayed
import shutil
import stability_report
import stability_report_badger
import glob
import sliipage_utils
import traceback


def create_overview(SITE_ID, users_data, totalAssetCollateral, totalAssetBorrow):
    print("create_overview")
    data = {"json_time": time.time()}

    data["total_collateral"] = sum([x for x in totalAssetCollateral.values()])
    if data["total_collateral"] == 0:
        data["total_collateral"] = str(users_data["user_no_cf_collateral"].sum())
    data["median_collateral"] = str(
        np.median(users_data.loc[users_data["user_no_cf_collateral"] > 0]["user_no_cf_collateral"]))
    data["top_1_collateral"] = str(users_data["user_no_cf_collateral"].max())
    data["top_10_collateral"] = str(
        users_data.sort_values("user_no_cf_collateral", ascending=False).head(10)["user_no_cf_collateral"].sum())

    data["total_debt"] = sum([x for x in totalAssetBorrow.values()])
    if data["total_debt"] == 0:
        data["total_debt"] = str(users_data["user_debt"].sum())
    data["median_debt"] = str(np.median(users_data.loc[users_data["user_debt"] > 0]["user_debt"]))
    data["top_1_debt"] = str(users_data["user_debt"].max())
    data["top_10_debt"] = str(users_data.sort_values("user_debt", ascending=False).head(10)["user_debt"].sum())

    if "nl_user_collateral" in users_data.columns:
        data["nl_total_collateral"] = str(users_data["nl_user_collateral"].sum())
        data["nl_median_collateral"] = str(
            np.median(users_data.loc[users_data["nl_user_collateral"] > 0]["nl_user_collateral"]))
        data["nl_top_1_collateral"] = str(users_data["nl_user_collateral"].max())
        data["nl_top_10_collateral"] = str(
            users_data.sort_values("nl_user_collateral", ascending=False).head(10)["nl_user_collateral"].sum())

        data["nl_total_debt"] = str(users_data["nl_user_debt"].sum())
        data["nl_median_debt"] = str(np.median(users_data.loc[users_data["nl_user_debt"] > 0]["nl_user_debt"]))
        data["nl_top_1_debt"] = str(users_data["nl_user_debt"].max())
        data["nl_top_10_debt"] = str(
            users_data.sort_values("nl_user_debt", ascending=False).head(10)["nl_user_debt"].sum())

    fp = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "overview.json", "w")
    json.dump(data, fp)
    fp.close()


def create_lending_platform_current_information(SITE_ID, last_update_time, names, inv_names, decimals, prices,
                                                collateral_factors, collateral_caps, borrow_caps, underlying):
    data = {"json_time": time.time()}
    data["last_update_time"] = last_update_time
    data["names"] = inv_names
    data["decimals"] = dict((names[key], value) for (key, value) in decimals.items())
    data["collateral_factors"] = dict((names[key], value) for (key, value) in collateral_factors.items())
    data["collateral_caps"] = dict((names[key], value) for (key, value) in collateral_caps.items())
    data["borrow_caps"] = dict((names[key], value) for (key, value) in borrow_caps.items())
    data["prices"] = dict((names[key], value) for (key, value) in prices.items())
    data["underlying"] = dict((names[key], value) for (key, value) in underlying.items())

    fp = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "lending_platform_current.json", "w")
    json.dump(data, fp)
    fp.close()


def create_oracle_information(SITE_ID, prices, chain_id, names, assets_cex_aliases, dex_get_price_function):
    print("create_oracle_information")
    # kp = kyber_prices.KyberPrices(lending_platform_json_file, chain_id)
    cp = cex_prices.CCXTClient()
    data = {"json_time": time.time()}
    asset_name_ignore_list = ["auSTNEAR"]
    cex_ignore_list = ["DPX", "GMX", "OHM", "GLP", "wstETH"]
    if chain_id == "cardano": 
        # ignored tokens for MELD protocol on cardano
        cex_ignore_list =  ["iUSD", "MIN", "COPI", "C3", "iBTC"]

    dex_ignore_list = ["sGLP"]
    for asset_id in prices:
        asset_name = names[asset_id]
        cex_name = assets_cex_aliases[asset_name]
        cex_price = 1
        if chain_id == "cardano":
            exchange = 'binance' # default to binance
            if cex_name in ["MELD", "HOSKY", "WRT"]:
                exchange = "mexc"
            elif cex_name in ["WMT"]:
                exchange = "huobi"

            cex_price = cp.get_price(exchange, cex_name, "USDT") if (cex_name not in cex_ignore_list and asset_name not in asset_name_ignore_list) else 'NaN'
        else:
            if cex_name != "USDC" and cex_name != "USDT" and cex_name != "DAI" and cex_name != "VST":
                exchange = "binance" if cex_name != "FOX" else "coinbasepro"
                cex_price = cp.get_price(exchange, cex_name, "USDT") if (cex_name not in cex_ignore_list and asset_name not in asset_name_ignore_list) else 'NaN'

        dex_price = 1
        if chain_id == "cardano":
            # do not fetch dex price for cardano using this function
            dex_price = 'NaN'
        else:
            if chain_id == "aurora":
                if asset_name != "auUSDC":
                    dex_price = dex_get_price_function("auUSDC", asset_name, 1000) if asset_name not in dex_ignore_list else 'NaN'
            elif chain_id == "arbitrum":
                if asset_name != "VST":
                    dex_price = dex_get_price_function("VST", asset_name, 1000) if asset_name not in dex_ignore_list else 'NaN'
            elif chain_id == "yokaiswap" or chain_id == "og":
                if asset_name != "USDC":
                    dex_price = dex_get_price_function("USDC", asset_name, 1000) if asset_name not in dex_ignore_list else 'NaN'
        
        print('dex price:', asset_name, dex_price)

        data[asset_name] = {"oracle": prices[asset_id], "cex_price": cex_price, "dex_price": dex_price}

    fp = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "oracles.json", "w")
    print(data)
    json.dump(data, fp)
    fp.close()


def create_account_information(SITE_ID, users_data, totalAssetCollateral, totalAssetBorrow, inv_names,
                               assets_liquidation_data, only_usdt=False):
    print("create_account_information")
    data = {"json_time": time.time()}
    for asset in inv_names:
        data[asset] = {}
        data[asset]["total_collateral"] = 0
        if inv_names[asset] in totalAssetCollateral:
            data[asset]["total_collateral"] = totalAssetCollateral[inv_names[asset]]
        if data[asset]["total_collateral"] == 0:
            data[asset]["total_collateral"] = str(users_data["NO_CF_COLLATERAL_" + asset].sum())

        data[asset]["median_collateral"] = str(
            np.median(users_data.loc[users_data["NO_CF_COLLATERAL_" + asset] > 0]["NO_CF_COLLATERAL_" + asset]))
        data[asset]["top_1_collateral"] = str(users_data["NO_CF_COLLATERAL_" + asset].max())
        data[asset]["top_10_collateral"] = str(
            users_data.sort_values("NO_CF_COLLATERAL_" + asset, ascending=False).head(10)[
                "NO_CF_COLLATERAL_" + asset].sum())

        data[asset]["total_debt"] = 0
        if not only_usdt:
            if inv_names[asset] in totalAssetBorrow:
                data[asset]["total_debt"] = totalAssetBorrow[inv_names[asset]]
            if data[asset]["total_debt"] == 0:
                data[asset]["total_debt"] = str(users_data["DEBT_" + asset].sum())
            data[asset]["median_debt"] = str(
                np.median(users_data.loc[users_data["DEBT_" + asset] > 0]["DEBT_" + asset]))
            data[asset]["top_1_debt"] = str(users_data["DEBT_" + asset].max())
            data[asset]["top_10_debt"] = str(
                users_data.sort_values("DEBT_" + asset, ascending=False).head(10)["DEBT_" + asset].sum())
        else:
            users_data1 = users_data.loc[users_data["NO_CF_COLLATERAL_" + asset] > 0]
            data[asset]["total_debt"] = str(users_data1["DEBT_VST"].sum())
            data[asset]["median_debt"] = str(np.median(users_data1.loc[users_data["DEBT_VST"] > 0]["DEBT_VST"]))
            data[asset]["top_1_debt"] = str(users_data1["DEBT_VST"].max())
            data[asset]["top_10_debt"] = str(
                users_data1.sort_values("DEBT_VST", ascending=False).head(10)["DEBT_VST"].sum())

        if "nl_user_collateral" in users_data.columns:
            data[asset]["nl_total_collateral"] = str(users_data["NL_COLLATERAL_" + asset].sum())
            data[asset]["nl_median_collateral"] = str(
                np.median(users_data.loc[users_data["COLLATERAL_" + asset] > 0]["NL_COLLATERAL_" + asset]))
            data[asset]["nl_top_1_collateral"] = str(users_data["NL_COLLATERAL_" + asset].max())
            data[asset]["nl_top_10_collateral"] = str(
                users_data.sort_values("NL_COLLATERAL_" + asset, ascending=False).head(10)[
                    "NL_COLLATERAL_" + asset].sum())

            data[asset]["nl_total_debt"] = str(users_data["NL_DEBT_" + asset].sum())
            data[asset]["nl_median_debt"] = str(
                np.median(users_data.loc[users_data["NL_DEBT_" + asset] > 0]["NL_DEBT_" + asset]))
            data[asset]["nl_top_1_debt"] = str(users_data["NL_DEBT_" + asset].max())
            data[asset]["nl_top_10_debt"] = str(
                users_data.sort_values("NL_DEBT_" + asset, ascending=False).head(10)["NL_DEBT_" + asset].sum())

        data[asset]["graph_data"] = assets_liquidation_data[inv_names[asset]]

    fp = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "accounts.json", "w")
    json.dump(data, fp)
    fp.close()

def create_usd_volumes_for_slippage(SITE_ID, chain_id, inv_names, liquidation_incentive, get_price_function,
                                    only_usdt=False, near_to_stnear_volume=0, stnear_to_near_volume=0,):

    try:
        print("create_usd_volumes_for_slippage")
        data = sliipage_utils.get_usd_volumes_for_slippage(chain_id, inv_names, liquidation_incentive, get_price_function,
                                                           only_usdt, near_to_stnear_volume, stnear_to_near_volume)
        data["json_time"] = time.time()
        fp = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "usd_volume_for_slippage.json", "w")
        json.dump(data, fp)
        fp.close()
    except Exception as e:
        traceback.print_exc()
        print(e)


def create_open_liquidations_information(SITE_ID, users_data, assets_to_simulate):
    data = {"json_time": time.time(), "data": []}
    my_user_data = copy.deepcopy(users_data)
    my_user_data["user_collateral_wo_looping"] = 0
    my_user_data["user_debt_wo_looping"] = 0

    for base_to_simulation in assets_to_simulate:
        my_user_data["MIN_" + base_to_simulation] = my_user_data[
            ["COLLATERAL_" + base_to_simulation, "DEBT_" + base_to_simulation]].min(axis=1)
        my_user_data["COLLATERAL_" + base_to_simulation] -= my_user_data["MIN_" + base_to_simulation]
        my_user_data["DEBT_" + base_to_simulation] -= my_user_data["MIN_" + base_to_simulation]

        my_user_data["user_collateral_wo_looping"] += my_user_data["COLLATERAL_" + base_to_simulation]
        my_user_data["user_debt_wo_looping"] += my_user_data["DEBT_" + base_to_simulation]

    for index, row in my_user_data.iterrows():
        if row["user_collateral_wo_looping"] < row["user_debt_wo_looping"]:
            data["data"].append({
                "account": row["user"],
                "user_collateral_wo_looping": row["user_collateral_wo_looping"],
                "user_debt_wo_looping": row["user_debt_wo_looping"]
            })

    fp = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "open_liquidations.json", "w")
    json.dump(data, fp)
    fp.close()


def create_whale_accounts_information(SITE_ID, users_data, assets_to_simulate, only_usdt=False):
    data = {"json_time": time.time()}
    my_user_data = copy.deepcopy(users_data)
    # for base_to_simulation in assets_to_simulate:
    #     my_user_data["MIN_" + base_to_simulation] = my_user_data[
    #         ["COLLATERAL_" + base_to_simulation, "DEBT_" + base_to_simulation]].min(axis=1)
    #     my_user_data["COLLATERAL_" + base_to_simulation] -= my_user_data["MIN_" + base_to_simulation]
    #     my_user_data["DEBT_" + base_to_simulation] -= my_user_data["MIN_" + base_to_simulation]

    for base_to_simulation in assets_to_simulate:
        total_collateral = my_user_data["NO_CF_COLLATERAL_" + base_to_simulation].sum()
        total_debt = my_user_data["DEBT_" + base_to_simulation].sum()
        data[base_to_simulation] = {"total_collateral": str(total_collateral),
                                    "total_debt": str(total_debt),
                                    "big_collateral": [],
                                    "big_debt": []}

        big_collateral_users = my_user_data.loc[
            my_user_data["NO_CF_COLLATERAL_" + base_to_simulation] > 0.1 * total_collateral]
        for index, row in my_user_data.sort_values("NO_CF_COLLATERAL_" + base_to_simulation, ascending=False).head(
                10).iterrows():
            is_whale = 1 if len(big_collateral_users.loc[big_collateral_users["user"] == row["user"]]) > 0 else 0
            size = row["NO_CF_COLLATERAL_" + base_to_simulation]
            size = size if not math.isnan(size) else 0
            data[base_to_simulation]["big_collateral"].append(
                {"id": row["user"], "size": size, "whale_flag": is_whale})

        if not only_usdt:
            big_debt_users = my_user_data.loc[my_user_data["DEBT_" + base_to_simulation] > 0.1 * total_debt]
            for index, row in my_user_data.sort_values("DEBT_" + base_to_simulation, ascending=False).head(
                    10).iterrows():
                is_whale = 1 if len(big_debt_users.loc[big_debt_users["user"] == row["user"]]) > 0 else 0
                size = row["DEBT_" + base_to_simulation]
                size = size if not math.isnan(size) else 0
                data[base_to_simulation]["big_debt"].append(
                    {"id": row["user"], "size": size, "whale_flag": is_whale})
        else:
            my_user_data1 = my_user_data.loc[my_user_data["NO_CF_COLLATERAL_" + base_to_simulation] > 0]
            my_user_data1 = my_user_data1.reset_index(drop=True)
            total_debt = my_user_data1["DEBT_VST"].sum()
            data[base_to_simulation]["total_debt"] = total_debt
            big_debt_users = my_user_data1.loc[my_user_data1["DEBT_VST"] > 0.1 * total_debt]
            for index, row in my_user_data1.sort_values("DEBT_VST", ascending=False).head(
                    10).iterrows():
                is_whale = 1 if len(big_debt_users.loc[big_debt_users["user"] == row["user"]]) > 0 else 0
                data[base_to_simulation]["big_debt"].append(
                    {"id": row["user"], "size": row["DEBT_VST"], "whale_flag": is_whale})

    fp = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "whale_accounts.json", "w")
    json.dump(data, fp)
    fp.close()

def create_assets_std_ratio_information(SITE_ID, assets, dates, only_usdt=False):
    print("create_assets_std_ratio_information")
    data = {"json_time": time.time()}
    markets_data = {}
    for asset in assets:
        if asset != "USDT" and asset != "USDC":
            df = pd.DataFrame()
            for date in dates:
                file_name = "data" + os.path.sep + "data_unified_" + str(date[1]) + "_" + str(
                    date[0]) + "_" + asset + "USDT.csv"
                d = pd.read_csv(file_name)
                if len(df) == 0:
                    df = d
                else:
                    df = pd.concat([df, d], ignore_index=True, sort=False)
            markets_data[asset] = df.sort_values("timestamp_x")
            markets_data[asset] = markets_data[asset][["timestamp_x", "ask_price", "bid_price"]]

    for base in assets:
        if base != "USDT" and base != "USDC":
            data[base] = {}
            for quote in assets:
                if base != quote and (not only_usdt or quote == "USDT"):
                    std = utils.calc_series_std_ratio("ETH", "USDT", base, quote, markets_data)
                    if not only_usdt:
                        data[base][quote] = std
                    else:
                        data[base]["VST"] = std

    fp = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "assets_std_ratio.json", "w")
    json.dump(data, fp)
    fp.close()


def create_simulation_results(SITE_ID, ETH_PRICE, total_jobs, collateral_factors, inv_names, print_time_series, fast_mode):
    output_folder = "simulation_results" + os.path.sep + SITE_ID
    #shutil.rmtree(output_folder)
    os.makedirs(output_folder)

    file = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "simulation_configs.json", "r")
    jj = json.load(file)
    try:
        Parallel(n_jobs=total_jobs)(
            delayed(run_simulation_on_dir)(ETH_PRICE, ("data_worst_day" if fast_mode else "data_worst") + os.path.sep + "*ETH*", output_folder,
                                           collateral_factors, inv_names, j, jj[j], print_time_series,
                                           None, False, False)
            for j in jj if j != "json_time")

    except Exception as e:
        print("Exception !!!!!!!!!!!!!!!", str(e))
        traceback.print_exc()


def run_simulation_on_dir(ETH_PRICE, source_data, output_folder, collateral_factors, inv_names, name, config,
                          print_time_series, liquidation_df, skip, calc_pnl):
    files = glob.glob(source_data)
    print(source_data)
    print("run_simulation_on_dir")
    for file in files:
        try:
            n = name.split('-')[0] if len(name.split('-')) == 2 else name.split('-')[0] + "-" + name.split('-')[1]
            config["collateral_factor"] = collateral_factors[inv_names[n]]
            if not "badger" in output_folder:
                sr = stability_report.stability_report()
                sr.ETH_PRICE = ETH_PRICE
                sr.run_simulation(output_folder, file, name, config, print_time_series, liquidation_df, skip, calc_pnl)
            else:
                sr = stability_report_badger.stability_report()
                sr.ETH_PRICE = ETH_PRICE
                sr.run_simulation(output_folder, file, name, config, print_time_series, liquidation_df, skip, calc_pnl)

        except Exception as e:
            print("Exception !!!!!!!!!!!!!!!", str(e))
            traceback.print_exc()


def create_risk_params(SITE_ID, ETH_PRICE, total_jobs, l_factors, print_time_series):
    file = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "simulation_configs.json", "r")
    data = {"json_time": time.time()}
    jj = json.load(file)
    try:
        to_returns = Parallel(n_jobs=total_jobs)(
            delayed(plot_for_html)("simulation_results" + os.path.sep + SITE_ID + os.path.sep, j, print_time_series,
                                   ETH_PRICE, jj[j]["liquidation_incentives"][0]) for j
            in jj if j != "json_time")

        for to_return in to_returns:
            for x in to_return:
                df = x[0]
                simulation_name = x[1]
                j = x[2]
                li = x[3]
                df = copy.deepcopy(df)
                if j not in data:
                    data[j] = {}
                df.reset_index(inplace=True)
                data[j][simulation_name] = []
                for l_factor in l_factors:
                    data[j][simulation_name].append({'dc': 0, 'lf': l_factor, 'md': 0, "li": li})

                for index, row in df.iterrows():
                    data[j][simulation_name].append(
                        {'dc': round(row['Total Debt (M)'], 2),
                         'lf': row['Stress Factor'],
                         'md': round(row["max_drop"], 3),
                         "li": li})

    except Exception as e:
        print("Exception", e)
        traceback.print_exc()

    fp = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "risk_params.json", "w")
    json.dump(data, fp)
    fp.close()

def plot_for_html(output_folder, j, print_time_series, ETH_PRICE, li):
    sr = stability_report.stability_report()
    sr.ETH_PRICE = ETH_PRICE
    return sr.plot_for_html(output_folder, j, print_time_series, li)


def create_current_simulation_risk(SITE_ID, ETH_PRICE, users_data, assets_to_simulate, assets_aliases,
                                   collateral_factors, inv_names, liquidation_incentive, total_jobs, only_usdt):
    output_folder = "current_risk_results" + os.path.sep + SITE_ID
    #shutil.rmtree(output_folder)
    os.makedirs(output_folder)

    f1 = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "usd_volume_for_slippage.json")
    jj1 = json.load(f1)

    file = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "simulation_configs.json", "r")
    jj = json.load(file)

    my_user_data = copy.deepcopy(users_data)
    for base_to_simulation in assets_to_simulate:
        my_user_data["MIN_" + base_to_simulation] = my_user_data[
            ["COLLATERAL_" + base_to_simulation, "DEBT_" + base_to_simulation]].min(axis=1)
        my_user_data["COLLATERAL_" + base_to_simulation] -= my_user_data["MIN_" + base_to_simulation]
        my_user_data["DEBT_" + base_to_simulation] -= my_user_data["MIN_" + base_to_simulation]
    for base_to_simulation in assets_to_simulate:
        if not only_usdt or base_to_simulation != "VST":
            for quote_to_simulation in jj1[base_to_simulation]:
                if not only_usdt or quote_to_simulation == "VST":
                    if assets_aliases[base_to_simulation] != assets_aliases[quote_to_simulation]:
                        total_user_collateral = 0
                        key = base_to_simulation + "-" + quote_to_simulation
                        result = []
                        for index, row in my_user_data.iterrows():
                            user_collateral_asset_total_collateral_usd = row["COLLATERAL_" + base_to_simulation]
                            user_debt_asset_total_debt_usd = row["DEBT_" + quote_to_simulation]

                            total_user_collateral += user_collateral_asset_total_collateral_usd
                            user_collateral_total_usd = row["user_collateral"]
                            user_debt_total_usd = row["user_debt"]
                            over_collateral = user_collateral_total_usd - user_debt_total_usd
                            if user_collateral_asset_total_collateral_usd > 0:
                                liquidation_price_change = 1 - over_collateral / user_collateral_asset_total_collateral_usd
                                result.append({
                                    "key": key,
                                    "user_id": row["user"],
                                    "liquidation_price_change": round(liquidation_price_change, 2),
                                    "liquidation_amount_usd": min(user_collateral_asset_total_collateral_usd,
                                                                  user_debt_asset_total_debt_usd)})

                        jj[key]["collaterals"] = [0]
                        jj[key]["l_factors"] = [0]
                        jj[key]["volume_for_slippage_10_percentss"] = [jj[key]["volume_for_slippage_10_percentss"][0]]
                        jj[key]["stability_pool_initial_balances"] = [jj[key]["stability_pool_initial_balances"][0]]
                        jj[key]["recovery_halflife_retails"] = [jj[key]["recovery_halflife_retails"][0]]
                        jj[key]["share_institutionals"] = [jj[key]["share_institutionals"][0]]
                        jj[key]["price_recovery_times"] = [jj[key]["price_recovery_times"][0]]

                        run_simulation_on_dir(ETH_PRICE, "data_worst_day" + os.path.sep + "*ETH*",
                                              "current_risk_results" + os.path.sep + SITE_ID,
                                              collateral_factors, inv_names,
                                              key, jj[key], True,
                                              pd.DataFrame(result), False, True)

    fp = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "current_simulation_config.json", "w")
    json.dump(jj, fp)
    fp.close()

    file = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "simulation_configs.json", "r")
    jj = json.load(file)
    file.close()
    Parallel(n_jobs=total_jobs)(
        delayed(plot_for_html)(output_folder, j, True, ETH_PRICE, jj[j]["liquidation_incentives"][0]) for j in jj if j != "json_time")

    data = {"json_time": time.time()}
    try:
        for base in jj1:
            if base == "json_time": continue
            data[base] = {}
            for quote in jj1[base]:
                files = glob.glob(
                    "current_risk_results" + os.path.sep + SITE_ID + os.path.sep + "*csv*" + base + "*" + quote + "*")
                if len(files) == 0:
                    print("skip", base, quote)
                    continue
                all_df = None
                for file in files:
                    if "liquidation_data" not in file:
                        all_df = pd.concat([all_df, pd.read_csv(file)])

                total_liquidation = float(
                    all_df.sort_values("max_drop", ascending=False).head(1)["simulation volume"]) * ETH_PRICE
                max_drop = float(all_df.sort_values("max_drop", ascending=False).head(1)["max_drop"])
                max_liquidation_size = float(
                    all_df.sort_values("max_drop", ascending=False).head(1)["max_liquidation_volume"]) * ETH_PRICE
                pnl = float(all_df.sort_values("max_drop", ascending=False).head(1)["pnl"])

                data[base][quote] = {}

                max_collateral = 1 - max_drop
                max_collateral /= float(liquidation_incentive[inv_names[base]])

                data[base][quote]["total_liquidation"] = str(total_liquidation)
                data[base][quote]["max_drop"] = str(max_drop)
                data[base][quote]["max_collateral"] = str(max_collateral)
                data[base][quote]["max_liquidation_size"] = str(max_liquidation_size)
                data[base][quote]["pnl"] = str(pnl)
                data[base][quote]["ts"] = {}

                df = pd.read_csv("current_risk_results" + os.path.sep + SITE_ID + os.path.sep + str(
                    all_df.iloc[0]["simulation_name"]) + ".csv")
                df["liquidation_volume"] = df["liquidation_volume"].rolling(30).sum() * ETH_PRICE / 1_000_000
                df = df.dropna()
                df = df.iloc[::10, :]
                for index, row in df.iterrows():
                    data[base][quote]["ts"][round(row["ts"] / (1000 * 1000))] = {
                        "a": round(row["price"]),
                        "b": round(row["max_drop"], 2),
                        "c": round(row["market_volume"] * ETH_PRICE / 1_000_000, 2),
                        "d": round(row["open_liquidations"] * ETH_PRICE / 1_000_000, 2),
                        "e": round(row["pnl"] / 1_000_000, 2),
                        "f": round(row["liquidation_volume"] * ETH_PRICE / 1_000_000, 2)
                    }

            data[base]["summary"] = {}
            data[base]["summary"]["total_liquidation"] = 0
            data[base]["summary"]["max_drop"] = 0
            data[base]["summary"]["max_collateral"] = 0
            data[base]["summary"]["pnl"] = 0
            l = len([x for x in data[base] if x != "summary"])
            if l > 0:
                try:
                    data[base]["summary"]["total_liquidation"] = sum(
                        [float(data[base][x]["total_liquidation"]) for x in data[base] if x != "summary"])

                    data[base]["summary"]["max_drop"] = np.max(
                        [float(data[base][x]["max_drop"]) for x in data[base] if x != "summary"])

                    data[base]["summary"]["max_collateral"] = np.min(
                        [float(data[base][x]["max_collateral"]) for x in data[base] if x != "summary"])

                    data[base]["summary"]["pnl"] = sum(
                        [float(data[base][x]["pnl"]) for x in data[base] if x != "summary"])

                except Exception as e:
                    print("Exception in Current Simulation Risk", e)
                    traceback.print_exc()
            else:
                print(base, " Is Empty !!!")

    except Exception as e:
        print("Exception in Current Simulation Risk", e)
        traceback.print_exc()

    fp = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "current_simulation_risk.json", "w")
    json.dump(data, fp)
    fp.close()