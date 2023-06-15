import glob
import numpy as np
import copy
import pandas as pd
import requests
import time
import compound_parser
import datetime
import json
import matplotlib.pyplot as plt
from pathlib import Path
import os
from github import Github
import matplotlib.dates as mdates
import prettytable as pt
import math
import private_config
from sklearn.linear_model import LinearRegression
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeRegressor
from sklearn.model_selection import cross_val_score
from sklearn.neural_network import MLPRegressor


def get_gmx_price():
    file = open("data\\gmx_price.json")
    gmx_price = json.load(file)
    plt.plot([float(x["aumInUsdg"]) / float(x["glpSupply"]) for x in gmx_price["data"]["glpStats"]])
    plt.show()
    # ts = gmx_price.keys()
    # print(ts)


def calc_series_std_ratio(source_base, source_quote, test_base, test_quote, market_data1):
    print("calc_series_std_ratio", source_base, source_quote, " To", test_base, test_quote)
    market_data = copy.deepcopy(market_data1)
    source = market_data[source_base]
    source["price"] = (source["bid_price"] + source["ask_price"]) * 0.5
    test = None
    if source_quote == test_quote or (source_quote == "USDT" and test_quote == "USDC"):
        test = market_data[test_base]
        test["price"] = (test["bid_price"] + test["ask_price"]) * 0.5
    else:
        test1 = market_data[test_base]
        test1["price"] = (test1["bid_price"] + test1["ask_price"]) * 0.5
        test1["timestamp_x"] /= 1000 * 1000 * 60
        test1["timestamp_x"] = test1["timestamp_x"].astype(int)

        test2 = market_data[test_quote]
        test2["price"] = (test2["bid_price"] + test2["ask_price"]) * 0.5
        test2["timestamp_x"] /= 1000 * 1000 * 60
        test2["timestamp_x"] = test2["timestamp_x"].astype(int)
        test = test1.merge(test2, how='inner', left_on=['timestamp_x'], right_on=['timestamp_x'])
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

    print("30M Rolling STD Ratio", round(test_rolling_std / source_rolling_std,2))
    print("STD Ratio", round(test_std / source_std,2))
    print()
    return test_rolling_std / source_rolling_std


def find_worth_month(name):
    files = glob.glob("simulation_results\\" + name + "\\*.csv")
    xx = ["series_std_ratio", "liquidation_incentive", "price_recovery_time", "volume_for_slippage_10_percents",
          "cycle_trade_volume", "collateral", "recovery_halflife_retail", "share_institutional",
          "stability_pool_initial_balance_ratio", "stability_pool_initial_balance", "collateral_liquidation_factor"]

    results = {}
    for f in files:
        name = f.split(".")[1].split("_")[1]
        df = pd.read_csv(f)
        uniques = df.groupby(xx).size().reset_index().rename(columns={0: 'count'})
        date = f.split("_")[4] + "-" + f.split("_")[5]
        if len(uniques) == 180:
            print(f, len(uniques))
            for index, row in uniques.iterrows():
                batch_df = copy.deepcopy(df)
                name_1 = name
                for x in xx:
                    name_1 += "_" + str(row[x])
                    batch_df = batch_df.loc[batch_df[x] == row[x]]
                max_drop = np.max(batch_df["max_drop"])
                if name_1 not in results or results[name_1]["max_drop"] < max_drop:
                    results[name_1] = {"date": date, "max_drop": max_drop}
    dates = {}
    for r in results:
        d = results[r]["date"]
        if d not in dates:
            dates[d] = 0
        dates[d] += 1
    print(dates)


def find_total_liquidations_for_price_drop(lending_platform_json_file, drop):
    file = open(lending_platform_json_file)
    data = json.load(file)
    cp_parser = compound_parser.CompoundParser()
    users_data, assets_liquidation_data, \
    last_update_time, names, inv_names, decimals, collateral_factors, borrow_caps, collateral_caps, prices, \
    underlying, inv_underlying, liquidation_incentive, orig_user_data, totalAssetCollateral, totalAssetBorrow = cp_parser.parse(
        data)

    report = {}
    for a in assets_liquidation_data:
        price = float(prices[a])
        if "USDT" not in names[a] and "USDC" not in names[a]:
            report[names[a]] = 0
            for asset in assets_liquidation_data[a]:
                for x in assets_liquidation_data[a][asset]:
                    if float(x) < price * (1 - drop):
                        print(names[a], asset, price * (1 - drop), assets_liquidation_data[a][asset][x])
                        report[names[a]] += round(float(assets_liquidation_data[a][asset][x]), 0)
                        break
    print(drop, report)


def find_worst_day():
    files = glob.glob("data\\data_unified_*_ETHUSDT.csv")
    all_df = None
    for file in files:
        df = pd.read_csv(file)
        df["index"] = pd.to_datetime(df["timestamp_x"] / 1_000_000, unit='s')
        all_df = pd.concat(
            [all_df, df.groupby(pd.Grouper(key="index", freq='24h'))["ask_price"].agg(["first", "last"])])
    all_df["drop"] = all_df["last"] / all_df["first"]
    print(all_df.sort_values("drop"))


def copy_day_to_worst_day(date1, date2):
    date1 = datetime.datetime.strptime(date1, '%Y-%m-%d')
    date2 = datetime.datetime.strptime(date2, '%Y-%m-%d')

    file_name = "data\\data_unified_" + str(date1.year) + "_" + str(date1.month).rjust(2, '0') + "_ETHUSDT.csv"
    df = pd.read_csv(file_name)
    df["index"] = pd.to_datetime(df["timestamp_x"] / 1_000_000, unit='s')
    df = df.loc[(df["index"].dt.day == date1.day) | (df["index"].dt.day == date2.day)]
    df.to_csv(file_name.replace("data\\", "data_worst_day\\"))


def get_file_time(file_name):
    print(file_name)
    if not os.path.exists(file_name):
        return float('inf')
    file = open(file_name)
    liquidityJson = json.load(file)
    if not "lastUpdateTime" in liquidityJson:
        return float('inf')
    return liquidityJson["lastUpdateTime"]


def update_time_stamps(SITE_ID, last_update_time):
    print('update_time_stamps')
    path = "webserver" + os.path.sep + SITE_ID + os.path.sep
    files = glob.glob(path + "*.*")
    print(files)
    for file_name in files:
        try:
            file = open(file_name)
            data = json.load(file)
            file.close()
            old_json_time = data["json_time"]
            data["json_time"] = last_update_time
            print(file_name, "old time", int(old_json_time), "new time", int(last_update_time), "diff",
                  int((old_json_time - last_update_time) / 60), "Minutes")
            fp = open(file_name, "w")
            json.dump(data, fp)
            fp.close()
        except Exception as e:
            print(e)


def print_account_information_graph(json_file):
    file = open(json_file)
    data = json.load(file)
    for asset in [x for x in data if x != "json_time"]:
        plt.cla()
        plt.suptitle(asset)
        for quote in data[asset]["graph_data"]:
            xy = data[asset]["graph_data"][quote]
            new_xy = {}
            for x in xy:
                new_xy[float(x)] = float(xy[x])
            new_xy = sorted(new_xy.items())
            plt.plot([x[0] for x in new_xy], [x[1] for x in new_xy], label=asset + "/" + quote)
        plt.show()


def get_site_id(SITE_ID):
    if str(os.path.sep) in SITE_ID:
        SITE_ID = SITE_ID.split(str(os.path.sep))[0]
    n = datetime.datetime.now()
    d = str(n.year) + "-" + str(n.month) + "-" + str(n.day) + "-" + str(n.hour) + "-" + str(n.minute)
    SITE_ID = SITE_ID + os.path.sep + d
    os.makedirs("webserver" + os.path.sep + SITE_ID, exist_ok=True)
    return SITE_ID


def get_latest_folder_name(SITE_ID):
    # print(private_config.git_version_token)
    gh = Github(login_or_token=private_config.git_version_token, base_url='https://api.github.com')
    repo_name = "Risk-DAO/simulation-results"
    repo = gh.get_repo(repo_name)
    folders = repo.get_contents("./" + SITE_ID)
    max_folder_date = datetime.datetime(2000, 1, 1, 1, 1)
    max_folder_name = ""
    for folder in folders:
        try:
            fields = folder.name.split("-")
            folder_date = datetime.datetime(int(fields[0]), int(fields[1]), int(fields[2]), int(fields[3]), int(fields[4]))
            if max_folder_date < folder_date:
                max_folder_date = folder_date
                max_folder_name = folder.name
        except Exception as e:
            print(f"Error in {folder}, {e}")
    return max_folder_name, max_folder_date


def get_all_sub_folders(path, json_name):
    print(private_config.git_version_token)
    gh = Github(login_or_token=private_config.git_version_token, base_url='https://api.github.com')
    repo_name = "Risk-DAO/simulation-results"
    repo = gh.get_repo(repo_name)
    folders = repo.get_contents("./" + path)
    results = {}
    for folder in folders:
        print(folder)
        try:
            contents = repo.get_contents("/" + path + "/" + str(folder.name) + "/" + json_name)
            j = json.loads(contents.decoded_content)
            results[j["json_time"]] = j
        except Exception as e:
            print("Exception in folder", folder.name)

    return results


def convert_liquitiy_json_to_slippage(file):
    new_file = {}
    for j in file:
        for x in j["slippage"]:
            if x == 'json_time':
                new_file[x] = j["slippage"][x]
            else:
                if x in new_file:
                    for y in j["slippage"][x]:
                        new_file[x][y] = j["slippage"][x][y]
                else:
                    new_file[x] = j["slippage"][x]
    return new_file


def get_formatted_number_clean(volume):
    if volume >= 1e9:
        return str(round(volume / 1e9, 2)) + 'B'
    elif volume >= 1e6:
        return str(round(volume / 1e6, 2)) + 'M'
    elif volume >= 1e3:
        return str(round(volume / 1e3, 2)) + 'K'


def convert_tokens_json_to_oracle(file):
    new_file = {}
    for j in file:
        symbol = j["symbol"]
        new_file[symbol] = {}
        new_file[symbol]["oracle"] = float(j["priceUSD18Decimals"]) / pow(10, 18)
        new_file[symbol]["cex_price"] = float(j["cexPriceUSD18Decimals"]) / pow(10, 18)
        new_file[symbol]["dex_price"] = float(j["dexPriceUSD18Decimals"]) / pow(10, 18)
    return new_file


def send_telegram_table(bot_id, chat_id, headers, rows):
    table = pt.PrettyTable(headers)

    for row in rows:
        table.add_row(row)

    # send the message as markdown
    send_telegram_alert(bot_id, chat_id, f'```{table}```', is_markdown=True)


def compare_to_prod_and_send_alerts(old_alerts, data_time, name, base_SITE_ID, current_SITE_ID, alert_params, send_alerts=False, ignore_list=[], current_supply_borrow=None):
    print("comparing to prod", name)
    prod_version = get_prod_version(name)
    print('retrieved prod_version:', prod_version)
    prod_version = prod_version.strip('\n')
    print('stripped prod_version:', prod_version)
    prod_file = json.loads(get_git_json_file(base_SITE_ID, prod_version, "usd_volume_for_slippage.json"))
    file = open("webserver" + os.path.sep + current_SITE_ID + os.path.sep + "usd_volume_for_slippage.json")
    last_file = json.load(file)

    time_from_now = datetime.datetime.now().timestamp() - data_time
    time_from_now /= 60
    time_from_now = str(round(time_from_now, 2)) + " Minutes (from last update)"

    time_from_prod = last_file["json_time"] - prod_file["json_time"]
    time_from_prod /= (60 * 60)
    time_from_prod = str(round(time_from_prod, 2)) + " Hours (from publication)"

    time_alert = time_from_now + "\n" + time_from_prod

    alert_sent = False
    if send_alerts:
        for alert_param in alert_params:
            if alert_param['is_default']:
                msg = "-------------------------------------------------"
                send_telegram_alert(alert_param['tg_bot_id'], alert_param['tg_channel_id'], msg)
    
    for key1 in prod_file:
        if key1 == "json_time": continue
        if key1 in ignore_list: continue

        for key2 in prod_file[key1]:
            print(key1, key2)
            if key2 in ignore_list: continue

            last_volume = last_file[key1][key2]["volume"]
            prod_volume = prod_file[key1][key2]["volume"]
            change = 100 * (round((last_volume / prod_volume) - 1, 2))

            # alert_params is an array of: 
            # {
            #     "is_default": boolean, # is default mean it's the risk dao general channel where all msg are sent
            #     "tg_bot_id": string,
            #     "tg_channel_id": string,
            #     "oracle_threshold": number, # oracle threshold is always in absolute
            #     "slippage_threshold": number, # liquidity threshold before sending alert
            #     "only_negative": boolean, # only send liquidity alert if the new volume < old volume
            # }
            for alert_param in alert_params:
                # send alert only if change > slippage threshold or if, when param only_negative == true, and change is negative and abs(change) > param.slippage_threshold
                must_send_alert = (not alert_param['only_negative'] and abs(change) > alert_param['slippage_threshold']) \
                                    or \
                                    (alert_param['only_negative'] and change < 0 and abs(change) > alert_param['slippage_threshold'])
                if must_send_alert:
                    # last_volume = "{:,}".format(round(last_volume, 0))
                    # prod_volume = "{:,}".format(round(prod_volume, 0))
                    message = f"{name} " \
                            f"\n{time_alert}" \
                            f"\n{key1}.{key2}" \
                            f"\nLiquidity Change by {round(change, 2)}% " \
                            f"\nCurrent Volume: {last_volume}" \
                            f"\nLast Simulation Volume: {prod_volume}"
                    print(message)
                    alert_sent = True
                    if send_alerts:
                        # for default channel, send alert every time
                        if alert_param['is_default']:
                            print("Sending To TG")
                            send_telegram_alert(alert_param['tg_bot_id'], alert_param['tg_channel_id'], message)

                        # for non-default channels, check and record alerts
                        # to not send alerts at each runs
                        else:
                            message_key = f'{alert_param["tg_channel_id"]}.{name}.slippage.{key1}.{key2}'
                            last_value = 0 if message_key not in old_alerts else old_alerts[message_key]
                            if message_key not in old_alerts or abs(change) - abs(old_alerts[message_key]) > 10  \
                                    or np.sign(old_alerts[message_key]) != np.sign(change):
                                print("Sensing To TG to client", message_key)
                                send_telegram_alert(alert_param['tg_bot_id'], alert_param['tg_channel_id'],
                                                    message + "\nLast value:" + str(round(last_value, 2)))
                                if message_key not in old_alerts:
                                    old_alerts[message_key] = 0
                                old_alerts[message_key] = change

    # if no alerts sent, send "slippage is fine" to the default alert_param
    if not alert_sent:
        for alert_param in alert_params:
            if alert_param['is_default']:
                message = f"{name}" \
                        f"\n{time_alert}" \
                        f"\nSlippage is fine."
                print(message)
                if send_alerts:
                    print("Sending To TG")
                    send_telegram_alert(alert_param['tg_bot_id'], alert_param['tg_channel_id'], message)
    
    alert_sent = False

    oracle_file = open("webserver" + os.path.sep + current_SITE_ID + os.path.sep + "oracles.json")
    oracle_file = json.load(oracle_file)

    for market in oracle_file:
        if market == "json_time": continue
        if market in ignore_list: continue

        oracle = float(oracle_file[market]["oracle"])
        # if oracle is 0 (or less?), don't need to check
        if oracle <= 0: continue

        cex = float(oracle_file[market]["cex_price"])
        dex = float(oracle_file[market]["dex_price"])
        dexDiff = (100 * ((oracle / dex) - 1))
        for alert_param in alert_params:
            oracleThreshold = alert_param['oracle_threshold']
            if market in ignore_list:
                print('changing oracleThreshold to 20 for', market, 'because it is in the ignore list')
                oracleThreshold = 20
            
            if abs(dexDiff) > oracleThreshold:
                message = f"{name}" \
                        f"\n{time_alert}" \
                        f"\n{market}" \
                        f"\nOracle<>Dex Price is off by: {round(dexDiff, 2)}%" \
                        f"\nOracle Price: {oracle} " \
                        f"\nDex Price: {dex}"
                print(message)
                alert_sent = True
                if send_alerts:
                    # for default channel, send alert
                    if alert_param['is_default']:
                        print("Sending to default TG")
                        send_telegram_alert(alert_param['tg_bot_id'], alert_param['tg_channel_id'], message)
                        
                    # for non-default channels, check and record alerts
                    # to not send alerts at each runs
                    else:
                        message_key = f'{alert_param["tg_channel_id"]}.{name}.oracle.dex.diff.{market}'
                        last_value = 0 if message_key not in old_alerts else old_alerts[message_key]
                        if message_key not in old_alerts or abs(old_alerts[message_key]) * 1.1 < abs(dexDiff) \
                                or np.sign(old_alerts[message_key]) != np.sign(dexDiff):
                            print(f"Sending to {alert_param['tg_channel_id']} TG", message_key)
                            send_telegram_alert(alert_param['tg_bot_id'], alert_param['tg_channel_id'],
                                                message + "\nLast value:" + str(round(last_value, 2)))
                            if message_key not in old_alerts:
                                old_alerts[message_key] = 0
                            old_alerts[message_key] = dexDiff

                if cex > 0:
                    cexDiff = (100 * ((oracle / cex) - 1))
                    if abs(cexDiff) > oracleThreshold:
                        message = f"{name}" \
                                f"\n{time_alert}" \
                                f"\n{market} " \
                                f"\nOracle<>Cex Price is off by: {round(cexDiff, 2)}%" \
                                f"\nOracle Price: {oracle} " \
                                f"\nCex Price: {cex}"
                        print(message)
                        alert_sent = True
                        if send_alerts:
                            if alert_param['is_default']:
                                print("Sending to Default TG")
                                send_telegram_alert(alert_param['tg_bot_id'], alert_param['tg_channel_id'], message)
                            else:
                                message_key = f'{alert_param["tg_channel_id"]}.{name}.oracle.cex.diff.{market}'
                                last_value = 0 if message_key not in old_alerts else old_alerts[message_key]
                                if message_key not in old_alerts or abs(old_alerts[message_key]) * 1.1 < abs(cexDiff) \
                                        or np.sign(old_alerts[message_key]) != np.sign(cexDiff):
                                    print(f"Sending to {alert_param['tg_channel_id']} TG", message_key)
                                    send_telegram_alert(alert_param['tg_bot_id'], alert_param['tg_channel_id'],
                                                        message + "\nLast value:" + str(round(last_value, 2)))
                                    if message_key not in old_alerts:
                                        old_alerts[message_key] = 0
                                    old_alerts[message_key] = cexDiff
    
    if not alert_sent:
        for alert_param in alert_params:
            if alert_param['is_default']:
                message = f"{name}" \
                        f"\n{time_alert}" \
                        f"\nOracle is fine."
                print(message)
                if send_alerts:
                    print("Sending To TG")
                    send_telegram_alert(alert_param['tg_bot_id'], alert_param['tg_channel_id'], message)

    alert_sent = False
    if current_supply_borrow != None:
        print('starting supply / borrow comparison')
        prod_supply_borrow = get_prod_supply_borrow(base_SITE_ID, prod_version)
        
        # compare supply
        for token_symbol in current_supply_borrow['currentSupply']:
            if token_symbol in ignore_list: continue
            current_supply_in_token = current_supply_borrow['currentSupply'][token_symbol]
            oracle_price_for_token = float(oracle_file[token_symbol]["oracle"])
            prod_supply_in_token = prod_supply_borrow['supply'][token_symbol] / oracle_price_for_token
            if prod_supply_in_token == 0:
                continue # avoid division per 0
            
            diff_in_usd = abs(prod_supply_in_token - current_supply_in_token) * oracle_price_for_token
            if diff_in_usd < 100000:
                continue # do not send alert if diff is less than $100k

            pct_diff = (current_supply_in_token - prod_supply_in_token) / prod_supply_in_token
            print(token_symbol, 'current supply:', current_supply_in_token, 'prod supply:', prod_supply_in_token)
            print(token_symbol, 'diff:', pct_diff)
            
            diff_compare_threshold = abs(pct_diff) * 100
            for alert_param in alert_params:
                threshold = alert_param['supply_borrow_threshold']
                if diff_compare_threshold > threshold:
                    alert_sent = True
                    message = f"{name}" \
                            f"\n{time_alert}" \
                            f"\n{token_symbol}" \
                            f"\nLast simulation supply: {prod_supply_in_token}" \
                            f"\nCurrent supply: {current_supply_in_token}" \
                            f"\ndiff: {round(pct_diff*100.0, 2)}%"
                        
                    print(message)
                    if send_alerts:
                        if alert_param['is_default']:
                            print("Sending to Default TG")
                            send_telegram_alert(alert_param['tg_bot_id'], alert_param['tg_channel_id'], message)
                        else:
                            message_key = f'{alert_param["tg_channel_id"]}.{name}.supply.diff.{token_symbol}'
                            last_value = 0 if message_key not in old_alerts else old_alerts[message_key]
                            if message_key not in old_alerts or abs(old_alerts[message_key]) * 2 < abs(pct_diff) \
                                    or np.sign(old_alerts[message_key]) != np.sign(pct_diff):
                                print(f"Sending to {alert_param['tg_channel_id']} TG", message_key)
                                send_telegram_alert(alert_param['tg_bot_id'], alert_param['tg_channel_id'], message)
                                if message_key not in old_alerts:
                                    old_alerts[message_key] = 0
                                old_alerts[message_key] = pct_diff

        # compare borrow
        for token_symbol in current_supply_borrow['currentBorrow']:
            if token_symbol in ignore_list: continue
            current_borrow_in_token = current_supply_borrow['currentBorrow'][token_symbol]
            oracle_price_for_token = float(oracle_file[token_symbol]["oracle"])
            prod_borrow_in_token = prod_supply_borrow['borrow'][token_symbol] / oracle_price_for_token
            if prod_borrow_in_token == 0:
                continue # avoid division per 0
            
            diff_in_usd = abs(prod_borrow_in_token - current_borrow_in_token) * oracle_price_for_token
            if diff_in_usd < 100000:
                continue # do not send alert if diff is less than $100k

            pct_diff = (current_borrow_in_token - prod_borrow_in_token) / prod_borrow_in_token
            print(token_symbol, 'current borrow:', current_borrow_in_token, 'prod borrow:', prod_borrow_in_token)
            print(token_symbol, 'diff:', pct_diff)
            
            diff_compare_threshold = abs(pct_diff) * 100
            for alert_param in alert_params:
                threshold = alert_param['supply_borrow_threshold']
                if diff_compare_threshold > threshold:
                    alert_sent = True
                    message = f"{name}" \
                            f"\n{time_alert}" \
                            f"\n{token_symbol}" \
                            f"\nLast simulation borrow: {prod_borrow_in_token}" \
                            f"\nCurrent borrow: {current_borrow_in_token}" \
                            f"\ndiff: {round(pct_diff*100.0, 2)}%"
                        
                    print(message)
                    
                    if send_alerts:
                        if alert_param['is_default']:
                            print("Sending to Default TG")
                            send_telegram_alert(alert_param['tg_bot_id'], alert_param['tg_channel_id'], message)
                        else:
                            message_key = f'{alert_param["tg_channel_id"]}.{name}.borrow.diff.{token_symbol}'
                            last_value = 0 if message_key not in old_alerts else old_alerts[message_key]
                            if message_key not in old_alerts or abs(old_alerts[message_key]) * 2 < abs(pct_diff) \
                                    or np.sign(old_alerts[message_key]) != np.sign(pct_diff):
                                print(f"Sending to {alert_param['tg_channel_id']} TG", message_key)
                                send_telegram_alert(alert_param['tg_bot_id'], alert_param['tg_channel_id'], message)
                                if message_key not in old_alerts:
                                    old_alerts[message_key] = 0
                                old_alerts[message_key] = pct_diff

        if not alert_sent:
            for alert_param in alert_params:
                if alert_param['is_default']:
                    message = f"{name}" \
                            f"\n{time_alert}" \
                            f"\nSupply/Borrow are fine."
                    print(message)
                    if send_alerts:
                        print("Sending To TG")
                        send_telegram_alert(alert_param['tg_bot_id'], alert_param['tg_channel_id'], message)

    return old_alerts

# get last simulation supply/borrow, in usd
def get_prod_supply_borrow(site_id, prod_version):
    prod_supply_borrow = {
        'supply': {},
        'borrow': {}
    }
    accounts_file = json.loads(get_git_json_file(site_id, prod_version, "accounts.json"))
    for token in accounts_file:
        if token == 'json_time': 
            continue
        
        token_collateral = accounts_file[token]['total_collateral']
        token_debt = accounts_file[token]['total_debt']
        print(token, 'total collateral:', token_collateral)
        print(token, 'total debt', token_debt)
        prod_supply_borrow['supply'][token] = float(token_collateral)
        prod_supply_borrow['borrow'][token] = float(token_debt)

    return prod_supply_borrow

def get_prod_version(name):
    gh = Github(login_or_token=private_config.git_version_token, base_url='https://api.github.com')
    repo_name = "Risk-DAO/version-control"
    repo = gh.get_repo(repo_name)
    contents = repo.get_contents("/" + name)
    return str(contents.decoded_content).replace('b', '').replace("'", '')


def get_git_json_file(name, key, json_name):
    gh = Github(login_or_token=private_config.git_version_token, base_url='https://api.github.com')
    repo_name = "Risk-DAO/simulation-results"
    repo = gh.get_repo(repo_name)
    file_path = name + "/" + key + "/" + json_name
    contents = repo.get_contents(file_path)
    return contents.decoded_content


def move_to_prod(name, key):
    print(private_config.git_version_token)
    gh = Github(login_or_token=private_config.git_version_token, base_url='https://api.github.com')
    repo_name = "Risk-DAO/version-control"
    repo = gh.get_repo(repo_name)
    contents = repo.get_contents("/" + name)
    repo.update_file(contents.path, "more tests", key, contents.sha)


def publish_results(SITE_ID, target=None, new_only=False):
    print("publish_results")
    if private_config.git_token == "":
        print("Git Upload Failed. no Token")
        exit()

    if target is None:
        target = SITE_ID
    target = target.replace('\\', '/')
    gh = Github(login_or_token=private_config.git_token, base_url='https://api.github.com', timeout= 60)
    repo_name = "Risk-DAO/simulation-results"
    repo = gh.get_repo(repo_name)
    print("webserver" + os.path.sep + SITE_ID + os.path.sep + "*")
    files = glob.glob("webserver" + os.path.sep + SITE_ID + os.path.sep + "*")
    print(files)
    for f in files:
        while True:
            try:
                if  "jpg" in f:
                    file = open(f, mode='rb')
                else:
                    file = open(f)

                git_file = target + "/" + os.path.basename(f)
                print(git_file)
                sha = None
                try:
                    oldFile = repo.get_contents(git_file)
                    sha = oldFile.sha
                    print('will update old file: ', oldFile)
                except Exception as e:
                    print('old file not found, will create new file: ', git_file)

                if sha != None:
                    if not new_only:
                        repo.update_file(git_file, 'Commit Comments', file.read(), sha)
                    else:
                        print("Skip. File alredy there")
                else:
                    repo.create_file(git_file, "Commit Comments", file.read())
                break
            except Exception as e:
                print("Error in upload", e)
                time.sleep(10)


lastTGCallDate = None

def send_telegram_alert(bot_id, chat_id, message, is_markdown=False):
    callData = {
        "chat_id": chat_id,
        "text": message,
    }

    if is_markdown:
        callData['parse_mode'] = 'MarkdownV2'
    callDataJson = json.dumps(callData)

    global lastTGCallDate
    if lastTGCallDate == None:
        lastTGCallDate = datetime.datetime.now()

    # print('lastTGCallDate', lastTGCallDate)
    url = f'https://api.telegram.org/bot{bot_id}/sendMessage'
    headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}

    now = datetime.datetime.now()
    secToWait = 3 - (now - lastTGCallDate).total_seconds()  # wait 3 seconds between each calls
    if secToWait > 0:
        print('Sleeping', secToWait, 'seconds before calling telegram')
        time.sleep(secToWait)

    mustResend = True
    cptSleep = 1
    while mustResend:
        mustResend = False
        lastTGCallDate = datetime.datetime.now()
        # print('new lastTGCallDate', lastTGCallDate)
        tgResponse = requests.post(url, data=callDataJson, headers=headers)
        if tgResponse.status_code < 400:
            mustResend = False
        elif tgResponse.status_code == 429:
            mustResend = True
            print('Sleeping', cptSleep, 'seconds before re calling tg')
            time.sleep(cptSleep)
            cptSleep += cptSleep  # exponential backoff
        else:
            print('error when sending tg alert', tgResponse.status_code, tgResponse.reason)


def copy_site():
    assets_to_replace = {"auETH": "vETH", "auWBTC": "vrenBTC", "auWNEAR": "vgOHM", "auSTNEAR": "vDPX", "auUSDC": "vGMX",
                         "auUSDT": "vGLP"}
    SITE_ID = "2"
    files = glob.glob("webserver\\0\\*.*")
    for file in files:
        contents = Path(file).read_text()
        for a in assets_to_replace:
            contents = contents.replace(a, assets_to_replace[a])
        with open("webserver\\2\\" + os.path.basename(file), "w") as the_file:
            the_file.write(contents)

def create_production_accounts_graph(SITE_ID, field_name, lending_name, single_base=None):
    plt.cla()
    plt.close()
    json_name = "accounts.json"
    results = get_all_sub_folders(SITE_ID, json_name)
    xy = {}
    for result in results:
        try:
            x = result
            for base in results[result]:
                if base == "json_time": continue
                if base not in xy:
                    xy[base] = {}

                y = results[result][base][field_name]
                xy[base][x] = y
        except Exception as e:
            print("Error")

    for base in xy:
        if single_base and single_base != base: continue
        xx = [datetime.datetime.fromtimestamp(float(x)) for x in sorted(xy[base])]
        yy = [float(xy[base][x]) for x in sorted(xy[base])]
        y_last = yy[-1]

        if single_base:
            y_last = 1

        if y_last > 0:
            yy = [y / y_last for y in yy]
            plt.scatter(xx, yy, label=base)
            plt.plot(xx, yy, label=base)

    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%m/%d/%Y'))
    plt.gca().xaxis.set_major_locator(mdates.DayLocator())
    plt.gcf().autofmt_xdate()

    fig = plt.gcf()
    fig.set_size_inches(16.5, 8.5)

    plt.title(lending_name)
    plt.suptitle(field_name)
    plt.legend(loc="lower left")
    report_type = "all" if not single_base else single_base
    plt.savefig("results\\" + lending_name + "." + report_type + "." + field_name + ".accounts.jpg")


def create_production_slippage_graph(SITE_ID, lending_name):
    plt.cla()
    plt.close()
    json_name = "usd_volume_for_slippage.json"
    results = get_all_sub_folders(SITE_ID, json_name)
    xy = {}
    for result in results:
        print(result)
        try:
            x = datetime.datetime.fromtimestamp(float(result))
            for base in results[result]:
                if base == "json_time": continue
                for quote in results[result][base]:
                    if base not in xy:
                        xy[base] = {}
                    if quote not in xy[base]:
                        xy[base][quote] = {}
                    y = results[result][base][quote]["volume"]
                    xy[base][quote][x] = y
        except Exception as e:
            print("Error")

    for base in xy:
        for quote in xy[base]:
            xx = [x for x in sorted(xy[base][quote])]
            yy = [float(xy[base][quote][x]) for x in sorted(xy[base][quote])]
            y_last = yy[-1]
            if y_last > 0:
                yy = [y / y_last for y in yy]
                plt.scatter(xx, yy)
                plt.plot(xx, yy, label=base + "-" + quote)
            else:
                print(base, quote, "is out!!!")

    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%m/%d/%Y'))
    plt.gca().xaxis.set_major_locator(mdates.DayLocator())
    plt.gcf().autofmt_xdate()

    fig = plt.gcf()
    fig.set_size_inches(16.5, 8.5)

    plt.title(lending_name)
    plt.suptitle("Slippage")

    plt.legend(loc="lower left")
    plt.savefig("results\\" + lending_name + ".slippage.jpg")

def record_monitoring_data(monitoring_data):
    if not hasattr(private_config, 'monitoring_uri') or private_config.monitoring_uri == '':
        print('record_monitoring_data: monitoring_uri not found or empty in private_config. Will not record monitoring')
    else:
        try:
            monitoring_data['type'] = 'Liquidity Monitoring'
            monitoring_data["lastUpdate"] = round(datetime.datetime.now().timestamp())
            print('record_monitoring_data: sending monitoring data to monitoring api')
            print('record_monitoring_data:', monitoring_data)
            monitoring_response = requests.post(private_config.monitoring_uri, json=monitoring_data)
            print('record_monitoring_data: push result:', monitoring_response.status_code, monitoring_response.text)
        except Exception as error:
            err_msg = 'An exception occurred while pushing data to monitoring api: {}'.format(error)
            print(err_msg)


def convert_name(base_name):
    if base_name == "WXDAI":
        return "DAI"
    if base_name == "WETH":
        return "ETH"
    if base_name == "WBTC":
        return "BTC"
    if base_name == "EURe":
        return "EUR"

    return base_name

def run_ml_on_cf_data(file_name):
    # Load the data into a pandas DataFrame
    data = pd.read_csv(file_name)
    # Split the data into features and target
    #X = data["md"] ** 0.5
    X = data[["usd_volume_for_slippage", "assets_std_ratio", "lf", "dc"]]
    y = data["md"]

    # Create a linear regression model
    model = LinearRegression()
    # model = DecisionTreeRegressor(random_state=0)
    # model =  MLPRegressor(random_state=0, max_iter=500)

    # Perform cross validation with 5 folds
    scores = cross_val_score(model, X, y, cv=10, scoring='r2')

    # Print the mean score and standard deviation
    print("Cross validation scores: ", scores)
    print("Mean score: ", scores.mean())
    print("Standard deviation: ", scores.std())

def create_cf_data_generic(SITE_ID):
    df = pd.concat([pd.read_csv(file) for file in glob.glob(SITE_ID + "\\*.csv")])
    df["volume"] = df["collateral"] / df["volume_for_slippage_10_percents"]
    df["score"] = df["volume"] * df["series_std_ratio"]
    df.to_csv("report.csv")
    files = df["file_name"].unique()
    for file in files:
        plt.cla()
        plt.close()
        data = df.loc[df["file_name"] == file]
        data.reset_index(drop=True, inplace=True)
        plt.scatter(data["score"], data["max_drop"])
        plt.show()


def merge_ada_file():
    df1 = pd.read_csv("data\\20230511 -MELD-ADA - 2M.csv").sort_values("timestamp")
    df2 = pd.read_csv("data\\ada-usdt.csv").sort_values("timestamp")

    df2["timestamp"] /= 1000

    df2["timestamp"] = df2["timestamp"].astype("int")
    df1["timestamp"] = df1["timestamp"].astype("int")
    df1 = df1.fillna(method='ffill')
    df2 = df2.fillna(method='ffill')

    df3 = pd.merge_asof(df2, df1, on="timestamp")
    df3["open"] *= df3["price (ADA/MELD)"]
    df3["close"] *= df3["price (ADA/MELD)"]
    df3["high"] *= df3["price (ADA/MELD)"]
    df3["low"] *= df3["price (ADA/MELD)"]
    df3 = df3[df2.columns]
    df3["timestamp"] = df3["timestamp"].astype("str")
    df3["timestamp"] += "000"
    df3 = df3.dropna()
    df3.to_csv("data\\meld-usdt.csv", index=False)


def create_cf_data(SITE_ID):
    print(private_config.git_version_token)
    gh = Github(login_or_token=private_config.git_version_token, base_url='https://api.github.com')
    repo_name = "Risk-DAO/simulation-results"
    repo = gh.get_repo(repo_name)
    folders = repo.get_contents("./" + SITE_ID)
    ff = [folder.path for folder in folders]
    results = []
    #folder = ff[-1]
    for folder in ff:
        print(folder)
        try:
            usd_volume_for_slippage_json = json.loads(
                repo.get_contents(folder + "/usd_volume_for_slippage.json").decoded_content.decode())
            assets_std_ratio_json = json.loads(
                repo.get_contents(folder + "/assets_std_ratio.json").decoded_content.decode())
            risk_params_json = json.loads(
                repo.get_contents(folder + "/risk_params.json").decoded_content.decode())
            for base in usd_volume_for_slippage_json:
                if base == "json_time": continue
                for quote in usd_volume_for_slippage_json[base]:
                    if quote != "WETH" or base == "LINK" or base == "FOX" or base == "USDC" or base == "USDT": continue
                    usd_volume_for_slippage = usd_volume_for_slippage_json[base][quote]["volume"]
                    base1 = convert_name(base)
                    quote1 = convert_name(quote)

                    assets_std_ratio = 0
                    if base1 in assets_std_ratio_json:
                        assets_std_ratio = assets_std_ratio_json[base1][quote1]
                    else:
                        if quote1 in assets_std_ratio_json:
                            assets_std_ratio = assets_std_ratio_json[quote1][base1]
                        else:
                            print("skipped", base1, quote1)
                            continue

                    for pp in risk_params_json[base + "-" + quote]:
                        for p in risk_params_json[base + "-" + quote][pp]:
                            dc = p["dc"]
                            md = p["md"]
                            lf = p["lf"]
                            results.append({"folder": folder,
                                            "base": base, "quote": quote,
                                            "usd_volume_for_slippage": usd_volume_for_slippage,
                                            "assets_std_ratio": assets_std_ratio, "dc": dc, "md": md, "lf": lf})

        except Exception as e:
            print("Exception in folder", str(e))
        pd.DataFrame(results).to_csv(SITE_ID + ".csv", index=False)

# move_to_prod("vesta", "2023-4-16-20-27")
# create_cf_data("4")
# run_ml_on_cf_data("4.csv")
# create_cf_data_generic("simulation_results\\generic\\2023-4-27-21-58")
# merge_ada_file()
# publish_results("flare\\2023-5-9-12-50")
