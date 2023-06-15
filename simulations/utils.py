import glob
import numpy as np
import copy
import pandas as pd
import compound_parser
import datetime
import json
import matplotlib.pyplot as plt
from matplotlib import animation
from pathlib import Path
import os
from github import Github
import private_config
import matplotlib.dates as mdates


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

    print("source_avg", np.average(source["price"]))
    print("source_min", np.min(source["price"]))
    print("source_std", np.std(source["price"]) / np.average(source["price"]))

    print("test_avg", np.average(test["price"]))
    print("test_min", np.min(test["price"]))
    print("test_std", np.std(test["price"]) / np.average(test["price"]))

    print("30M Rolling STD Ratio", test_rolling_std / source_rolling_std)
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


def check_json_file(path):
    file = open(path)
    data = json.load(file)
    decimals = eval(data["decimals"])
    names = eval(data["names"])
    collateral_factors = eval(data["collateralFactors"])
    users = data["users"]
    users = users.replace("true", "True")
    users = users.replace("false", "False")
    users = eval(users)
    prices = eval(data["prices"])

    for i_d in prices:
        prices[i_d] = int(prices[i_d], 16) / 10 ** (36 - decimals[i_d])

    for user in users:
        if user == '0x211d417B596b4FEA2a5019f7e0CE4E63dE8d149e':
            collateral_balances = users[user]["collateralBalances"]
            total_c = 0
            total_b = 0
            for asset_id in collateral_balances:
                total_c += float(prices[asset_id]) * float(collateral_factors[asset_id]) * int(
                    collateral_balances[asset_id], 16) / 10 ** decimals[asset_id]
                print("collateralBalances", names[asset_id],
                      float(prices[asset_id]) * float(collateral_factors[asset_id]) * int(collateral_balances[asset_id],
                                                                                          16) / 10 ** decimals[
                          asset_id])

            borrow_balances = users[user]["borrowBalances"]
            for asset_id in borrow_balances:
                total_b += float(prices[asset_id]) * int(borrow_balances[asset_id], 16) / 10 ** decimals[asset_id]
                print("borrowBalances", names[asset_id],
                      float(prices[asset_id]) * int(borrow_balances[asset_id], 16) / 10 ** decimals[asset_id])

            print()
            print(total_b)
            print(total_c)


def get_total_bad_debt(users, asset, price_factor, prices, collateral_factors, names):
    total_bad_debt = 0
    assets_total_bad_debt = {}
    for user in users:
        user_collateral = 0
        user_debt = 0
        user_assets_debt = {}

        collateral_balances = users[user]["collateralBalances"]

        for asset_id in collateral_balances:
            c = int(collateral_balances[asset_id] * prices[asset_id]
                    * float(collateral_factors[asset_id]))
            if asset == names[asset_id]:
                c *= price_factor
            user_collateral += c
            x1 = c

        borrow_balances = users[user]["borrowBalances"]
        for asset_id in borrow_balances:
            c = int(borrow_balances[asset_id] * prices[asset_id])
            if asset == names[asset_id]:
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


def create_liquidata_data_from_json(json_file):
    file = open(json_file)
    data = json.load(file)
    last_update_time = data["lastUpdateTime"]
    names = eval(data["names"])
    inv_names = {v: k for k, v in names.items()}
    decimals = eval(data["decimals"])
    for x in decimals:
        decimals[x] = int(decimals[x])
    collateral_factors = eval(data["collateralFactors"])
    borrow_caps = eval(data["borrowCaps"])
    collateral_caps = eval(data["collateralCaps"])
    prices = eval(data["prices"])
    underlying = eval(data["underlying"])
    inv_underlying = {v: k for k, v in underlying.items()}

    liquidation_incentive = data["liquidationIncentive"]
    totalAssetBorrow = eval(data["totalBorrows"])
    totalAssetCollateral = eval(data["totalCollateral"])

    for i_d in prices:
        prices[i_d] = int(prices[i_d], 16) / 10 ** (36 - decimals[i_d])

    for i_d in collateral_caps:
        collateral_caps[i_d] = int(collateral_caps[i_d], 16) / 10 ** (decimals[i_d])

    for i_d in borrow_caps:
        borrow_caps[i_d] = int(borrow_caps[i_d], 16) / 10 ** (decimals[i_d])

    for i_d in totalAssetCollateral:
        totalAssetCollateral[i_d] = prices[i_d] * int(totalAssetCollateral[i_d], 16) / 10 ** (
            decimals[i_d])

    for i_d in totalAssetBorrow:
        totalAssetBorrow[i_d] = prices[i_d] * int(totalAssetBorrow[i_d], 16) / 10 ** (decimals[i_d])

    users = data["users"]
    users = users.replace("true", "True")
    users = users.replace("false", "False")
    users = eval(users)
    users_data = []
    orig_user_data = []
    for user in users:
        user_collateral = 0
        uset_no_cf_collateral = 0
        user_debt = 0
        user_data = {"user": user}
        collateral_balances = users[user]["collateralBalances"]
        for asset_id in collateral_balances:
            collateral_balances[asset_id] = int(collateral_balances[asset_id], 16) / 10 ** decimals[asset_id]
            user_collateral += collateral_balances[asset_id] * prices[asset_id] * float(
                collateral_factors[asset_id])

            uset_no_cf_collateral += collateral_balances[asset_id] * prices[asset_id]
            user_data["COLLATERAL_" + names[asset_id]] = collateral_balances[asset_id] * prices[
                asset_id] * float(collateral_factors[asset_id])
            user_data["NO_CF_COLLATERAL_" + names[asset_id]] = collateral_balances[asset_id] * prices[
                asset_id]

        user_data["user_collateral"] = user_collateral
        user_data["user_no_cf_collateral"] = uset_no_cf_collateral

        borrow_balances = users[user]["borrowBalances"]
        for asset_id in borrow_balances:
            borrow_balances[asset_id] = int(borrow_balances[asset_id], 16) / 10 ** decimals[asset_id]
            debt = borrow_balances[asset_id] * prices[asset_id]
            user_data["DEBT_" + names[asset_id]] = debt
            user_debt += debt

        user_data["user_debt"] = user_debt

        users_data.append(user_data)
    assets_liquidation_data = {}
    assets_to_check = names.values()
    for asset in assets_to_check:
        results = {}
        asset_price = prices[inv_names[asset]]
        for i in reversed(np.arange(0, 5, 0.1)):
            users_total_bad_debt, users_assets_total_bad_debt = get_total_bad_debt(users, asset, i, prices,
                                                                                   collateral_factors, names)
            key = asset_price * i
            for asset_id in users_assets_total_bad_debt:
                asset_name = names[asset_id]
                if asset_name != asset:
                    if asset_name not in results:
                        results[asset_name] = {}
                    results[asset_name][i] = users_assets_total_bad_debt[asset_id]

        assets_liquidation_data[inv_names[asset]] = results

        users_data = pd.DataFrame(users_data)
        orig_user_data = pd.DataFrame(orig_user_data)

    for k1 in assets_liquidation_data.keys():
        plt.cla()
        plt.suptitle(names[k1])
        for k2 in assets_liquidation_data[k1].keys():
            plt.plot(assets_liquidation_data[k1][k2].keys(), assets_liquidation_data[k1][k2].values(),
                     label=names[k1] + "/" + k2)
        plt.legend()
        plt.plot()
        plt.show()


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


def create_current_simulation_risk(json_file):
    assets_to_simulate = ["auETH", "auWBTC", "auWNEAR", "auSTNEAR", "auUSDC", "auUSDT"]
    assets_aliases = {"auETH": "ETH", "auWBTC": "BTC", "auWNEAR": "NEAR", "auSTNEAR": "NEAR", "auUSDT": "USDT",
                      "auUSDC": "USDT"}

    file = open(json_file)
    data = json.load(file)
    last_update_time = data["lastUpdateTime"]
    names = eval(data["names"])
    inv_names = {v: k for k, v in names.items()}
    decimals = eval(data["decimals"])
    for x in decimals:
        decimals[x] = int(decimals[x])
    collateral_factors = eval(data["collateralFactors"])
    borrow_caps = eval(data["borrowCaps"])
    collateral_caps = eval(data["collateralCaps"])
    prices = eval(data["prices"])
    underlying = eval(data["underlying"])
    inv_underlying = {v: k for k, v in underlying.items()}

    liquidation_incentive = data["liquidationIncentive"]
    totalAssetBorrow = eval(data["totalBorrows"])
    totalAssetCollateral = eval(data["totalCollateral"])

    for i_d in prices:
        prices[i_d] = int(prices[i_d], 16) / 10 ** (36 - decimals[i_d])

    for i_d in collateral_caps:
        collateral_caps[i_d] = int(collateral_caps[i_d], 16) / 10 ** (decimals[i_d])

    for i_d in borrow_caps:
        borrow_caps[i_d] = int(borrow_caps[i_d], 16) / 10 ** (decimals[i_d])

    for i_d in totalAssetCollateral:
        totalAssetCollateral[i_d] = prices[i_d] * int(totalAssetCollateral[i_d], 16) / 10 ** (
            decimals[i_d])

    for i_d in totalAssetBorrow:
        totalAssetBorrow[i_d] = prices[i_d] * int(totalAssetBorrow[i_d], 16) / 10 ** (decimals[i_d])

    f1 = open("webserver" + os.path.sep + "0" + os.path.sep + "usd_volume_for_slippage.json")
    jj1 = json.load(f1)

    file = open("webserver" + os.path.sep + "0" + os.path.sep + "simulation_configs.json", "r")
    jj = json.load(file)

    users = data["users"]
    users = users.replace("true", "True")
    users = users.replace("false", "False")
    users = eval(users)
    users_data = []
    orig_user_data = []
    for user in users:
        user_collateral = 0
        uset_no_cf_collateral = 0
        user_debt = 0
        user_data = {"user": user}
        collateral_balances = users[user]["collateralBalances"]
        for asset_id in collateral_balances:
            collateral_balances[asset_id] = int(collateral_balances[asset_id], 16) / 10 ** decimals[asset_id]
            user_collateral += collateral_balances[asset_id] * prices[asset_id] * float(
                collateral_factors[asset_id])

            uset_no_cf_collateral += collateral_balances[asset_id] * prices[asset_id]
            user_data["COLLATERAL_" + names[asset_id]] = collateral_balances[asset_id] * prices[
                asset_id] * float(collateral_factors[asset_id])
            user_data["NO_CF_COLLATERAL_" + names[asset_id]] = collateral_balances[asset_id] * prices[
                asset_id]

        user_data["user_collateral"] = user_collateral
        user_data["user_no_cf_collateral"] = uset_no_cf_collateral

        borrow_balances = users[user]["borrowBalances"]
        for asset_id in borrow_balances:
            borrow_balances[asset_id] = int(borrow_balances[asset_id], 16) / 10 ** decimals[asset_id]
            user_debt += borrow_balances[asset_id] * prices[asset_id]
            user_data["DEBT_" + names[asset_id]] = borrow_balances[asset_id] * prices[asset_id]

        user_data["user_debt"] = user_debt

        users_data.append(user_data)

    my_user_data = copy.deepcopy(pd.DataFrame(users_data))

    for base_to_simulation in assets_to_simulate:
        my_user_data["MIN_" + base_to_simulation] = my_user_data[
            ["COLLATERAL_" + base_to_simulation, "DEBT_" + base_to_simulation]].min(axis=1)
        my_user_data["COLLATERAL_" + base_to_simulation] -= my_user_data["MIN_" + base_to_simulation]
        my_user_data["DEBT_" + base_to_simulation] -= my_user_data["MIN_" + base_to_simulation]

    for base_to_simulation in assets_to_simulate:
        for quote_to_simulation in jj1[base_to_simulation]:
            if assets_aliases[base_to_simulation] != assets_aliases[quote_to_simulation]:
                key = base_to_simulation + "-" + quote_to_simulation
                result = []
                for index, row in my_user_data.iterrows():
                    user_collateral_asset_total_collateral_usd = row["COLLATERAL_" + base_to_simulation]
                    user_debt_asset_total_debt_usd = row["DEBT_" + quote_to_simulation]

                    user_collateral_total_usd = row["user_collateral"]
                    user_debt_total_usd = row["user_debt"]
                    over_collateral = user_collateral_total_usd - user_debt_total_usd
                    if user_collateral_asset_total_collateral_usd > 0:
                        liquidation_price_change = 1 - over_collateral / user_collateral_asset_total_collateral_usd
                        result.append({
                            "key": key,
                            "user_id": row["user"],
                            "liquidation_price_change": round(liquidation_price_change, 2),
                            "user_collateral_total_usd": user_collateral_total_usd,
                            "user_debt_total_usd": user_debt_total_usd,
                            "over_collateral": over_collateral,
                            "user_collateral_asset_total_collateral_usd": user_collateral_asset_total_collateral_usd,
                            "liquidation_amount_usd": min(user_collateral_asset_total_collateral_usd / float(
                                collateral_factors[inv_names[base_to_simulation]]),
                                                          user_debt_asset_total_debt_usd)})

                pd.DataFrame(result).to_csv("results\\" + base_to_simulation + "_" + quote_to_simulation + ".csv")


def print_time_series(base_path, path, ETH_PRICE):
    def animate(i):
        if i <= 50:
            i = i * 10
        elif i >= 250:
            i -= 180
            i = i * 10
        else:
            i = 500 + i - 50

        ax1.cla()  # clear the previous image
        ax2.cla()
        # ax1.set_xlim([min_ts, max_ts])  # fix the x axis
        ax1.set_ylim([min_price, max_price])  # fix the y axis
        #
        # ax2.set_xlim([min_ts, max_ts])  # fix the x axis
        ax2.set_ylim([0, 2])  # fix the y axis

        ax1.plot(df.loc[:i]["ts"], df.loc[:i]["price"], 'g-', label="Price")
        ax2.plot(df.loc[:i]["ts"], df.loc[:i]["market_volume"] * ETH_PRICE / 1_000_000, 'r-', label="Market Volume")
        ax2.plot(df.loc[:i]["ts"], df.loc[:i]["stability_pool_available_volume"] * ETH_PRICE / 1_000_000, 'm-',
                 label="Stability Pool Liquidity")
        ax2.plot(df.loc[:i]["ts"], df.loc[:i]["open_liquidations"] * ETH_PRICE / 1_000_000, 'y-',
                 label="open_liquidations")
        ax2.plot(df.loc[:i]["ts"], df.loc[:i]["pnl"] / 1_000_000, 'c-', label="PNL")
        ax2.plot(df.loc[:i]["ts"], df.loc[:i]["liquidation_volume"].rolling(30).sum() * ETH_PRICE / 1_000_000, 'b-',
                 label="30 minutes Liquidation Volume")

        ax1.set_label('Time')
        ax1.set_ylabel('Price', color='g')
        md = round(df.loc[:i]["max_drop"].max(), 2)
        plt.title("Max Drop:" + str(md))
        print(i, md)
        plt.legend()

    all_df = pd.read_csv(base_path + path)

    for index, row in all_df.iterrows():
        file_name = row["simulation_name"]
        df = pd.read_csv(base_path + file_name + ".csv")
        min_price = df["price"].min()
        max_price = df["price"].max()
        fig, ax1 = plt.subplots()
        fig.set_size_inches(12.5, 8.5)
        ax2 = ax1.twinx()

        plt.plot()
        anim = animation.FuncAnimation(fig, animate, frames=int(len(df) / 10) + 1 + 200, interval=0.1, blit=False)
        anim.save('results\\' + file_name + '.gif', writer='imagemagick', fps=15)
        # plt.show()


def create_cefi_market_data():
    # download_markets = [("binance-futures", "BTCUSDT"), ("binance-futures", "ETHUSDT"), ("binance-futures", "NEARUSDT")]
    # download_dates = [("06", "2022"), ("05", "2022"), ("04", "2022"), ("03", "2022"), ("02", "2022"), ("01", "2022")]
    download_markets = [("binance-spot", "ETHUSDT")]
    download_dates = [("01", "2020"), ("02", "2020"), ("03", "2020"), ("01", "2021"), ("02", "2021"), ("03", "2021")]
    dd = download_datasets.CefiDataDownloader()
    for download_market in download_markets:
        for download_date in download_dates:
            dd.create_one_minute_liquidation_data(download_date[0], download_date[1], download_market[0],
                                                  download_market[1])


def get_site_id(SITE_ID):
    if str(os.path.sep) in SITE_ID:
        SITE_ID = SITE_ID.split(str(os.path.sep))[0]
    n = datetime.datetime.now()
    d = str(n.year) + "-" + str(n.month) + "-" + str(n.day) + "-" + str(n.hour) + "-" + str(n.minute)
    SITE_ID = SITE_ID + os.path.sep + d
    os.makedirs("webserver" + os.path.sep + SITE_ID, exist_ok=True)
    return SITE_ID


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


def move_to_prod(name, key):
    print(private_config.git_version_token)
    gh = Github(login_or_token=private_config.git_version_token, base_url='https://api.github.com')
    repo_name = "Risk-DAO/version-control"
    repo = gh.get_repo(repo_name)
    contents = repo.get_contents("/" + name)
    repo.update_file(contents.path, "more tests", key, contents.sha)


def publish_results(SITE_ID):
    print("publish_results")
    if private_config.git_token == "":
        print("Git Upload Failed. no Token")
        exit()

    SITE_ID = SITE_ID.replace('\\', '/')
    gh = Github(login_or_token=private_config.git_token, base_url='https://api.github.com')
    repo_name = "Risk-DAO/simulation-results"
    repo = gh.get_repo(repo_name)
    files = glob.glob("webserver" + os.path.sep + SITE_ID + os.path.sep + "*.json")
    print(files)
    for f in files:
        file = open(f)
        git_file = SITE_ID + "/" + os.path.basename(f)
        print(git_file)
        repo.create_file(git_file, "Commit Comments", file.read())


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


def create_price_file(path, pair_name, target_month, decimals=1, eth_usdt_file=None):
    total_days = 90
    df = pd.read_csv(path)
    if eth_usdt_file:
        df1 = pd.read_csv(eth_usdt_file)
        df = pd.merge(df, df1, on="block number")
        df[" price"] = df[" price_x"] / df[" price_y"]
    rows_for_minute = len(df) / (total_days * 24 * 60)
    df = df.iloc[::int(rows_for_minute), :]
    print(df.columns)
    df.reset_index(drop=True, inplace=True)
    df["timestamp_x"] = datetime.datetime.now()
    df["ask_price"] = df[" price"] / decimals
    df["bid_price"] = df[" price"] / decimals
    df = df[["timestamp_x", "bid_price", "ask_price"]]
    l = len(df)
    rows_for_month = int(l / total_days) * 30
    index = 0
    for i in target_month:
        df1 = df.iloc[index * rows_for_month:(index + 1) * rows_for_month]
        df1.reset_index(drop=True, inplace=True)
        start_date = datetime.datetime(int(i[1]), int(i[0]), 1).timestamp()
        df1["timestamp_x"] = (start_date + df1.index * 60) * (1000 * 1000)
        df1.to_csv("data\\data_unified_" + i[1] + "_" + i[0] + "_" + pair_name + ".csv", index=False)
        index += 1


def create_production_accounts_graph(SITE_ID, field_name, lending_name, single_base = None):
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
                xy[base][x] =y
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

    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%m/%d/%Y'))
    plt.gca().xaxis.set_major_locator(mdates.DayLocator())
    plt.gcf().autofmt_xdate()

    fig = plt.gcf()
    fig.set_size_inches(16.5, 8.5)

    plt.title(lending_name)
    plt.suptitle("Slippage")

    plt.legend(loc="lower left")
    plt.savefig("results\\" + lending_name + ".slippage.jpg")


# create_price_file("..\\monitor-backend\\GLP\\glp.csv", "GLPUSDT",
#                   [("04", "2022"), ("05", "2022"), ("06", "2022")], 1, None)
#
#
# create_price_file("..\\monitor-backend\\ArbitrumDEX\\ohm-dai-mainnet.csv", "OHMUSDT",
#                   [("04", "2022"), ("05", "2022"), ("06", "2022")], 1e9, None)

# create_price_file("..\\monitor-backend\\ArbitrumDEX\\eth-gmx-arbitrum.csv", "GMXUSDT",
#                   [("04", "2022"), ("05", "2022"), ("06", "2022")], 1,
#                   "..\\monitor-backend\\ArbitrumDEX\\eth-dai-arbitrum.csv")
#
# create_price_file("..\\monitor-backend\\ArbitrumDEX\\eth-dpx-arbitrum.csv", "DPXUSDT",
#                   [("04", "2022"), ("05", "2022"), ("06", "2022")], 1,
#                   "..\\monitor-backend\\ArbitrumDEX\\eth-dai-arbitrum.csv")

# lending_platform_json_file = ".." + os.path.sep + "monitor-backend" + os.path.sep + "vesta" + os.path.sep + "data.json"
# chain_id = "arbitrum"
# kp = kyber_prices.KyberPrices(lending_platform_json_file, chain_id)
# print(kp.get_price("VST", "renBTC", 1000))

# lending_platform_json_file = "c:\\dev\\monitor-backend\\vesta\\data.json"
# file = open(lending_platform_json_file)
# data = json.load(file)
# data["collateralFactors"] = data["collateralFactors"].replace("}", ",'0x64343594Ab9b56e99087BfA6F2335Db24c2d1F17':0}")
# data["totalCollateral"] = data["totalCollateral"].replace("}", ",'0x64343594Ab9b56e99087BfA6F2335Db24c2d1F17':'0'}")
# data["totalBorrows"] = data["totalBorrows"].replace("}", ",'0x64343594Ab9b56e99087BfA6F2335Db24c2d1F17':'0'}")
# cp_parser = compound_parser.CompoundParser()
# users_data, assets_liquidation_data, \
# last_update_time, names, inv_names, decimals, collateral_factors, borrow_caps, collateral_caps, prices, \
# underlying, inv_underlying, liquidation_incentive, orig_user_data, totalAssetCollateral, totalAssetBorrow = cp_parser.parse(
#     data)


#  get_usd_volume_for_slippage(lending_platform_json_file, "ETH", "VST", 1.1, prices)
# create_current_simulation_risk(lending_platform_json_file)
# create_liquidata_data_from_json(lending_platform_json_file)
# print_account_information_graph("webserver\\0\\accounts.json")

# copy_site()
# get_gmx_price()
# base_path = "C:\\dev\\monitor-backend\\simulations\\current_risk_results\\2\\"
# print_time_series(base_path, "data_worst_day_data_unified_2020_03_ETHUSDT.csv_gOHM-VST_stability_report.csv", 1200)
# publish_results("1000/2022-10-1-12-30")