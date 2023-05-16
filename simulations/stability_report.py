import datetime
import glob
import traceback
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import copy
import seaborn as sns
import stability_pool_simple
import uuid
import shutil
import os

sns.set_theme()


class stability_report:
    liquidation_side = "binance-futures_ETHUSDT_liquidation_long"
    liquidation_factor = 1  # ratio of liquidation
    ETH_PRICE = 2000

    def plot_for_html(self, directory, name, print_time_series, li):
        # if os.path.isdir(directory + os.path.sep + name.replace("|", "-")):
        #     shutil.rmtree(directory + os.path.sep + name.replace("|", "-"))
        os.makedirs(directory + os.path.sep + name.replace("|", "-"))
        files = glob.glob(directory + os.path.sep + "*_" + name.replace("|","-") + "_*")
        print(name)
        print(directory + os.path.sep + "*_" + name.replace("|","-") + "_*")
        print(files)
        all_df = pd.DataFrame()
        for file in files:
            if "liquidation_data" not in file:
                df = pd.read_csv(file)
                if len(df) == 0:
                    all_df = copy.deepcopy(df)
                else:
                    # all_df = all_df.append(df)
                    all_df = pd.concat([all_df, df])
        all_df["Total Debt (M)"] = round(all_df["collateral"] / 1_000_000, 1)
        all_df["Stress Factor"] = all_df["collateral_liquidation_factor"]

        gg = [('price_recovery_time', 'prc'),
              ('volume_for_slippage_10_percents', 'vfs10p'), ('recovery_halflife_retail', 'rhr'),
              ('stability_pool_initial_balance_ratio', 'spibr'), ('share_institutional', 'si')]

        uniques = all_df.groupby([g[0] for g in gg]).size().reset_index().rename(columns={0: 'count'})
        to_return = []
        for index, row in uniques.iterrows():
            batch_df = copy.deepcopy(all_df)
            for g in gg:
                batch_df = batch_df.loc[batch_df[g[0]] == row[g[0]]]

            sns.set(font_scale=1.5)
            hm = self.get_heatmap(batch_df, "Total Debt (M)", "Stress Factor", "max_drop")
            ax = sns.heatmap(hm, annot=True, linewidths=.5, cmap="PiYG", vmin=0.5, vmax=1)
            file_name = "hm"
            for g in gg:
                file_name += "^" + g[1] + "^" + str(row[g[0]])
            fig = plt.gcf()
            fig.set_size_inches(12.5, 10.5)
            plt.suptitle("Dex Liquidity (M-USD): " + str(row["volume_for_slippage_10_percents"] * self.ETH_PRICE / 1_000_000))
            plt.savefig(directory + os.path.sep + name.replace("|", "-") + os.path.sep + file_name + ".jpg")
            plt.cla()
            plt.close()
            group_by_df = pd.DataFrame({'max_drop':
                                            batch_df.groupby(["Total Debt (M)", "Stress Factor"])[
                                                "max_drop"].max()}).reset_index()
            to_return.append((group_by_df, file_name, name, li))

        if print_time_series:
            for index, row in all_df.iterrows():
                file_name = row["simulation_name"]
                print(file_name)
                df = pd.read_csv(str(directory) + os.path.sep + str(file_name) + ".csv")
                fig, ax1 = plt.subplots()
                fig.set_size_inches(12.5, 8.5)
                ax2 = ax1.twinx()
                ax1.plot(df["ts"], df["price"], 'g-')
                ax2.plot(df["ts"], df["market_volume"] * self.ETH_PRICE / 1_000_000, 'r-', label="Market Volume")
                ax2.plot(df["ts"], df["stability_pool_available_volume"] * self.ETH_PRICE / 1_000_000, 'm-',
                         label="Stability Pool Liquidity")
                ax2.plot(df["ts"], df["open_liquidations"] * self.ETH_PRICE / 1_000_000, 'y-',
                         label="open_liquidations")
                ax2.plot(df["ts"], df["pnl"] / 1_000_000, 'c-', label="PNL")
                ax2.plot(df["ts"], df["liquidation_volume"].rolling(30).sum() * self.ETH_PRICE / 1_000_000, 'b-',
                         label="30 minutes Liquidation Volume")

                ax1.set_label('Time')
                ax1.set_ylabel('Price', color='g')

                gg = [('trade_every', 'te'),
                    ('price_recovery_time', 'prc'),
                      ('volume_for_slippage_10_percents', 'vfs10p'), ('recovery_halflife_retail', 'rhr'),
                      ('stability_pool_initial_balance_ratio', 'spibr'), ('share_institutional', 'si'),
                      ('collateral', 'c'),
                      ('collateral_liquidation_factor', 'clf')]

                file_name = "ts." + str(row["simulation_name"])
                for g in gg:
                    file_name += "^" + g[1] + "^" + str(row[g[0]])
                plt.title("Max Drop:" + str(round(row["max_drop"], 2)))
                plt.legend()
                plt.savefig(directory + os.path.sep + name.replace("|", "-") + os.path.sep + file_name + ".jpg")
                plt.cla()
                plt.close()

        return to_return

    def get_slippage_for_volume(self, v, s, v1):
        # x = y
        # x * y = k
        # (x + qty) * (x - v2) = k
        # (x - v2) = (x * x) / (x + qty)
        # (x - v2) / x = x / (x + qty)
        # Slippage(qty) = X / (X + qty)

        # s = x / (x + v)
        # s * (x + v) = x
        # s * x + s * v = x
        # s * v = x - s * x
        # s * v = x * (1 -s)
        x = (s * v) / (1 - s)

        # x' = x + v1
        # y' = x - ?
        # x'y' = x * x
        # priceimpact = y'/x'

        # (x + v) * (x - v1) = x * x
        # (x - v1) = (x * x) / (x + v)
        pi = (x * x) / pow(x + v1, 2)

        return pi

    def get_volume_for_slippage(self, v, s, s1):
        x = (s * v) / (1 - s)
        # Slippage(qty) = X / (X + qty)
        # s1 = x / (x + v1)
        # s1 * (x + v1) = x
        # s1 * x + s1 * v1 = x
        # s1 * v1 = x - s1 * x
        # s1 * v1 = x * (1 - s1)
        v1 = (x * (1 - s1)) / s1
        return v1

    def get_heatmap(self, df, x, y, z):
        df = copy.deepcopy(df)
        df[x] = df[x].astype(float)
        df[y] = df[y].astype(float)
        df[z] = df[z].astype(float)
        df["score"] = 1 - df[z]
        result = df.groupby([x, y])["score"].min().unstack(level=0)
        xx = df[y].unique()
        result.index = pd.CategoricalIndex(result.index, categories=sorted(xx, reverse=True))
        result.sort_index(inplace=True)
        return result

    def calc_series_std_ratio(self, file_name, dai_eth, convert):
        print(file_name, dai_eth, convert)
        dai_eth = pd.read_csv(dai_eth)
        dai_eth["price"] = 1 / dai_eth["price"]

        test_eth = pd.read_csv(file_name)
        test_eth["price"] = 1 / test_eth["price"]

        test_eth = test_eth.loc[test_eth["qty1"] != 0]
        test_eth["price"] = test_eth["price"].astype(float)

        if convert:
            test_eth = test_eth.merge(dai_eth, how='inner', left_on=['block_number'], right_on=['block_number'])
            test_eth["price"] = test_eth["price_y"] / test_eth["price_x"]

        dai_rolling_std = np.average(
            dai_eth["price"].rolling(5 * 30).std().dropna() / dai_eth["price"].rolling(5 * 30).mean().dropna())
        test_rolling_std = np.average(
            test_eth["price"].rolling(5 * 30).std().dropna() / test_eth["price"].rolling(5 * 30).mean().dropna())

        print("dai_avg", np.average(dai_eth["price"]))
        print("dai_min", np.min(dai_eth["price"]))
        print("dai_std", np.std(dai_eth["price"]) / np.average(dai_eth["price"]))

        print("test_avg", np.average(test_eth["price"]))
        print("test_min", np.min(test_eth["price"]))
        print("test_std", np.std(test_eth["price"]) / np.average(test_eth["price"]))

        print("30M Rolling STD Ratio", test_rolling_std / dai_rolling_std)

        return test_rolling_std / dai_rolling_std

    def adjust_series_price(self, df, factor):
        last_price = 0
        last_adjusted_price = 0
        for index, row in df.iterrows():
            price = (row["ask_price"] + row["bid_price"]) * 0.5
            if last_price != 0:
                price_change = ((price / last_price) - 1) * float(factor)
                adjust_price = last_adjusted_price + last_adjusted_price * price_change
            else:
                adjust_price = price

            df.at[index, "price"] = price
            df.at[index, "adjust_price"] = adjust_price
            last_adjusted_price = adjust_price
            last_price = price
        return copy.deepcopy(df)

    def check_max_liquidation_drop(self, open_liquidations, price):
        m_drop = 0
        m_drop_volume = 0
        for open_liquidation in open_liquidations:
            if open_liquidation["closed"] != open_liquidation["liquidation_volume"]:
                drop = ((open_liquidation["price"] - price) / open_liquidation["price"])
                if m_drop < drop:
                    m_drop = drop
                    m_drop_volume = open_liquidation["liquidation_volume"] - open_liquidation["closed"]
        return m_drop, m_drop_volume

    def convert_to_array(self, dai_eth, liquidation_df=None):
        arr = []
        initial_price = 0
        for index, row in dai_eth.iterrows():
            if initial_price == 0:
                initial_price = row["adjust_price"]
            if liquidation_df is None:
                arr.append({
                    "timestamp_x": row["timestamp_x"],
                    "adjust_price": row["adjust_price"],
                    self.liquidation_side: row[self.liquidation_side]})
            else:
                current_price = row["adjust_price"]
                current_price_change = current_price / initial_price
                if len(liquidation_df) == 0:
                    total_liquidations_eth = 0
                else:
                    total_liquidations_eth = \
                        liquidation_df.loc[current_price_change < liquidation_df["liquidation_price_change"]][
                            "liquidation_amount_usd"].sum() / self.ETH_PRICE
                liquidation_row = {
                    "timestamp_x": row["timestamp_x"],
                    "adjust_price": row["adjust_price"],
                    self.liquidation_side: total_liquidations_eth}
                arr.append(liquidation_row)
                if len(liquidation_df) > 0:
                    liquidation_df = liquidation_df.drop(
                        liquidation_df[current_price_change < liquidation_df["liquidation_price_change"]].index)
                    liquidation_df = liquidation_df.reset_index(drop=True)
        return arr

    def calc_simulation_pnl(self, open_liquidations, closed_liquidations, collateral_factor, liquidation_incentive, max_drop, prev_max_drop):
        all_liquidations = open_liquidations + closed_liquidations
        liquidation_total_pnl = 0
        for liquidation in all_liquidations:
            liquidation_pnl = 0

            #liquidation_price = liquidation["price"] * float(collateral_factor) * (1 - liquidation_incentive)
            #md = 1 - cf(li + 1)
            liquidation_price = 1 - float(collateral_factor) * (liquidation_incentive + 1)
            liquidation_price = liquidation["price"] * (1 - liquidation_price)

            for trade in liquidation["trades"]:
                volume = trade["volume"]
                price = trade["price"]
                if price < liquidation_price:
                    liquidation_pnl -= volume * (liquidation_price - price)

            if liquidation["worst_price"] < liquidation_price:
                liquidation_pnl -= (liquidation["liquidation_volume"] - liquidation["closed"]) * (
                        liquidation_price - liquidation["worst_price"])

            liquidation["pnl"] = liquidation_pnl
            liquidation_total_pnl += liquidation_pnl

        return liquidation_total_pnl

    def run_simulation(self, output_directory, file_name, name, config, print_time_series, liquidation_df, skip,
                       calc_pnl):

        try:
            output_file_name = output_directory + os.path.sep + file_name.replace(os.path.sep,
                                                                                  "_") + "_" + name.replace("|",
                                                                                                            "-") + "_" + "stability_report.csv"
            print(file_name, name, output_file_name)
            if skip and os.path.isfile(output_file_name):
                print("Skipping")
                return ""

            series_std_ratio = config["series_std_ratio"]
            trade_every = config["trade_every"]
            report = []
            print(file_name)
            dai_eth = pd.read_csv(file_name)
            total_days_in_file = len(pd.to_datetime(dai_eth['timestamp_x'] / 1000, unit='ms').dt.normalize().unique())
            #total_days_in_files_factor = total_days_in_file / 30
            total_days_in_files_factor = 1
            print(total_days_in_files_factor, total_days_in_file)
            dai_eth = self.adjust_series_price(dai_eth, series_std_ratio)
            x = min(dai_eth["timestamp_x"])
            dai_eth_array = self.convert_to_array(dai_eth, liquidation_df)
            if liquidation_df is not None:
                pd.DataFrame(dai_eth_array).to_csv(output_file_name + ".liquidation_data.csv")

            file_description = datetime.datetime.fromtimestamp(x / (1000 * 1000))
            file_description = datetime.date.strftime(file_description, "%d/%m/%Y")
            file_total_volume = sum(dai_eth[self.liquidation_side])
            simulation_id = str(uuid.uuid4())
            simulation_index = 0
            if "delays_in_minutes" not in config:
                config["delays_in_minutes"] = [0]

            total_runs = len(config["volume_for_slippage_10_percentss"]) * len(config["l_factors"]) * len(config["price_recovery_times"]) \
                         * len(config["share_institutionals"]) * len(config["recovery_halflife_retails"]) * len(config["collaterals"]) \
                         * len(config["liquidation_incentives"]) \
                         * len(config["stability_pool_initial_balances"]) * len(config["delays_in_minutes"])
            current_run = 0

            for volume_for_slippage_10_percents in config["volume_for_slippage_10_percentss"]:
                for l_factor in config["l_factors"]:
                    for price_recovery_time in config["price_recovery_times"]:
                        for share_institutional in config["share_institutionals"]:
                            for recovery_halflife_retail in config["recovery_halflife_retails"]:
                                for collateral in config["collaterals"]:
                                    for l_incentive in config["liquidation_incentives"]:
                                        for s_balance in config["stability_pool_initial_balances"]:
                                            for delay_in_minutes in config["delays_in_minutes"]:

                                                current_run += 1
                                                simulation_index += 1
                                                simulation_name = str(simulation_id) + "_" + str(simulation_index)
                                                target_volume = 0

                                                if liquidation_df is not None:
                                                    liquidation_ratio = 1
                                                    stability_pool_initial_balance = s_balance * config["current_debt"]
                                                else:
                                                    target_volume = collateral * l_factor * total_days_in_files_factor
                                                    stability_pool_initial_balance = collateral * s_balance
                                                    liquidation_ratio = target_volume / file_total_volume

                                                cycle_trade_volume = float(volume_for_slippage_10_percents)
                                                #self.get_volume_for_slippage(volume_for_slippage_10_percents * self.liquidation_factor, 1 - 0.1,1 - l_incentive)

                                                stability_pool_simple_instance = stability_pool_simple.stability_pool(
                                                    initial_balance=stability_pool_initial_balance,
                                                    recovery_interval=trade_every, recovery_volume=cycle_trade_volume,
                                                    share_institutional=share_institutional,
                                                    recovery_halflife_retail=recovery_halflife_retail)

                                                ts_report = []
                                                price_liquidation_factor = 1
                                                historical_cycle_trade_volume = []
                                                closed_liquidations = []
                                                open_liquidations = []
                                                prev_max_drop = 0
                                                max_drop = 0
                                                max_drop_open_volume = 0
                                                simulation_pnl = 0
                                                price_at_max_drop = 0
                                                max_liquidation_volume = 0
                                                min_price_liquidation_factor = float('inf')
                                                min_multiply_price_liquidation_factor = float('inf')
                                                all_liquidations_volume = 0
                                                max_daily_volume = 0
                                                last_row_date = 0
                                                daily_volume = 0
                                                collateral_factor = config["collateral_factor"]
                                                volume_for_slippage_10_percents_price_drop = volume_for_slippage_10_percents
                                                if "volume_for_slippage_10_percents_price_drop" in config:
                                                    oldVolume = volume_for_slippage_10_percents_price_drop
                                                    volume_for_slippage_10_percents_price_drop = config["volume_for_slippage_10_percents_price_drop"]
                                                    if oldVolume != volume_for_slippage_10_percents_price_drop:
                                                        print('VOLUME CHANGED: old:', oldVolume, 'new:', volume_for_slippage_10_percents_price_drop)
                                                for row in dai_eth_array:
                                                    time = row["timestamp_x"]
                                                    row_liquidation = row[self.liquidation_side]
                                                    liquidation_volume = (
                                                                                 row_liquidation * liquidation_ratio) / self.liquidation_factor
                                                    max_liquidation_volume = max(liquidation_volume, max_liquidation_volume)

                                                    row_date = datetime.datetime.fromtimestamp(time / (1000 * 1000))
                                                    row_date = datetime.date.strftime(row_date, "%d/%m/%Y")
                                                    if row_date != last_row_date:
                                                        last_row_date = row_date
                                                        if max_daily_volume < daily_volume:
                                                            max_daily_volume = daily_volume
                                                        daily_volume = 0

                                                    daily_volume += liquidation_volume

                                                    if row_liquidation > 0 and liquidation_volume == 0:
                                                        print("row_liquidation", row_liquidation,
                                                              "liquidation_volume", liquidation_volume,
                                                              'liquidation_ratio',liquidation_ratio,
                                                              "file_total_volume", file_total_volume,
                                                              "target_volume",target_volume , "EXIT1")
                                                        exit()

                                                    all_liquidations_volume += liquidation_volume

                                                    # recover price_liquidation_factor
                                                    missing_price_liquidation_factor = 1 - price_liquidation_factor
                                                    if price_recovery_time == 0:
                                                        price_liquidation_factor = 1
                                                        min_price_liquidation_factor = 1
                                                    else:
                                                        next_missing_price_liquidation_factor = missing_price_liquidation_factor * pow(
                                                            0.5, 1 / (price_recovery_time * 24 * 60))
                                                        price_liquidation_factor_recovery = missing_price_liquidation_factor - next_missing_price_liquidation_factor
                                                        if price_liquidation_factor_recovery < 0:
                                                            print("price_liquidation_factor_recovery",
                                                                  price_liquidation_factor_recovery, "EXIT2")
                                                            exit()

                                                        price_liquidation_factor += price_liquidation_factor_recovery
                                                        min_price_liquidation_factor = min(price_liquidation_factor,
                                                                                           price_liquidation_factor)

                                                        if price_liquidation_factor > 1:
                                                            print("Error", "EXIT3")
                                                            exit()

                                                    price = row["adjust_price"] * price_liquidation_factor

                                                    if liquidation_volume != 0:
                                                        liq = {"time": time,
                                                               "liquidation_volume": liquidation_volume,
                                                               "worst_price": price,
                                                               "pnl": 0,
                                                               "price": price,
                                                               "closed": 0,
                                                               "trades": []}
                                                        open_liquidations.append(liq)

                                                    for liquidation in open_liquidations:
                                                        if liquidation["worst_price"] > price:
                                                            liquidation["worst_price"] = price

                                                    open_liquidations_volume = sum(
                                                        [open_liquidation["liquidation_volume"] - open_liquidation["closed"] for
                                                         open_liquidation in
                                                         open_liquidations])

                                                    drop, volume = self.check_max_liquidation_drop(open_liquidations, price)
                                                    if max_drop < drop:
                                                        max_drop = drop
                                                        price_at_max_drop = price
                                                        max_drop_open_volume = open_liquidations_volume

                                                    market_volume = cycle_trade_volume - sum(historical_cycle_trade_volume)
                                                    close_liquidation_volume = 0
                                                    temp_trade_volume = 0
                                                    using_stability_pool_volume = 0
                                                    stability_pool_simple_recovery = 0
                                                    using_market_volume = 0
                                                    stability_pool_available_volume = 0

                                                    if stability_pool_initial_balance != 0:
                                                        stability_pool_simple_recovery = stability_pool_simple_instance.do_tick(
                                                            time,
                                                            market_volume)
                                                        stability_pool_available_volume = stability_pool_simple_instance.do_check_liquidation_size()
                                                        using_stability_pool_volume = min(open_liquidations_volume,
                                                                                          stability_pool_available_volume)
                                                        close_liquidation_volume += using_stability_pool_volume
                                                        temp_trade_volume += stability_pool_simple_recovery

                                                    if close_liquidation_volume < open_liquidations_volume:
                                                        using_market_volume = min(
                                                            open_liquidations_volume - close_liquidation_volume,
                                                            market_volume - stability_pool_simple_recovery)

                                                        close_liquidation_volume += using_market_volume
                                                        temp_trade_volume += using_market_volume

                                                        if open_liquidations_volume > 0 and close_liquidation_volume > 0 \
                                                                and close_liquidation_volume - open_liquidations_volume < 1:
                                                            close_liquidation_volume += 1  # for Rounding issues
                                                            #temp_trade_volume += 1


                                                        if calc_pnl:
                                                            simulation_pnl = self.calc_simulation_pnl(open_liquidations,
                                                                                                  closed_liquidations,
                                                                                                  collateral_factor,
                                                                                                  l_incentive, max_drop, prev_max_drop)
                                                    prev_max_drop = max_drop

                                                    # if close_liquidation_volume != temp_trade_volume:
                                                    #     print("BBBBBBBBBBBBBB", close_liquidation_volume, temp_trade_volume)
                                                    #     exit()
                                                    trade_volume = 0
                                                    if close_liquidation_volume > 0:
                                                        to_delete = []
                                                        for open_liquidation in open_liquidations:
                                                            start_liquidation_time = open_liquidation["time"] + delay_in_minutes * 60 * 1_000_000
                                                            if delay_in_minutes > 0 and time < start_liquidation_time:
                                                                continue
                                                            closed_volume = open_liquidation["closed"]
                                                            open_volume = open_liquidation["liquidation_volume"] - closed_volume

                                                            if open_volume > close_liquidation_volume:
                                                                open_liquidation["trades"].append(
                                                                    {"time": time, "volume": close_liquidation_volume,
                                                                     "price": open_liquidation["worst_price"]}
                                                                )
                                                                trade_volume += close_liquidation_volume
                                                                open_liquidation["closed"] += close_liquidation_volume
                                                                break
                                                            else:
                                                                current_liquidation_volume = open_volume
                                                                open_liquidation["trades"].append(
                                                                    {"time": time, "volume": current_liquidation_volume,
                                                                     "price": open_liquidation["worst_price"]})
                                                                open_liquidation["closed"] += current_liquidation_volume
                                                                trade_volume += current_liquidation_volume
                                                                close_liquidation_volume -= current_liquidation_volume
                                                                to_delete.append(open_liquidation)

                                                        for o in to_delete:
                                                            open_liquidations.remove(o)
                                                            closed_liquidations.append(copy.deepcopy(o))

                                                        # print("AAAAAAA", trade_volume, temp_trade_volume, trade_volume - temp_trade_volume)

                                                        if using_stability_pool_volume > 0 and trade_volume > 0:
                                                            stability_pool_simple_instance.do_set_liquidation_size(
                                                                min(using_stability_pool_volume, trade_volume))

                                                    ts_report.append({
                                                        "ts": time,
                                                        "price": price,
                                                        "liquidation_volume": liquidation_volume,
                                                        "open_liquidations": open_liquidations_volume,
                                                        "market_volume": market_volume,
                                                        "stability_pool_simple_recovery": stability_pool_simple_recovery,
                                                        "stability_pool_available_volume": stability_pool_available_volume,
                                                        "using_market_volume": using_market_volume,
                                                        "close_liquidation_volume": close_liquidation_volume,
                                                        "trade_volume": trade_volume,
                                                        "max_drop": max_drop,
                                                        "pnl": simulation_pnl
                                                    })

                                                    historical_cycle_trade_volume.append(trade_volume)
                                                    xx = int(len(historical_cycle_trade_volume) - trade_every / 60)
                                                    if xx > 0:
                                                        historical_cycle_trade_volume = historical_cycle_trade_volume[xx:]

                                                    # multiply the price by the trade slippage
                                                    if l_incentive > 0 and trade_volume > 0:
                                                        multiply_price_liquidation_factor = self.get_slippage_for_volume(
                                                            volume_for_slippage_10_percents_price_drop, 1 - l_incentive, trade_volume)
                                                    else:
                                                        multiply_price_liquidation_factor = 1

                                                    min_multiply_price_liquidation_factor = min(
                                                        min_multiply_price_liquidation_factor,
                                                        multiply_price_liquidation_factor)

                                                    price_liquidation_factor *= multiply_price_liquidation_factor

                                                open_volume = sum(
                                                    [open_liquidation["liquidation_volume"] - open_liquidation["closed"] for
                                                     open_liquidation in
                                                     open_liquidations])

                                                print(os.path.basename(file_name), name, "total runs", total_runs, "run", current_run,
                                                      "max_drop", round(max_drop, 2),
                                                      "simulation_pnl", round(simulation_pnl, 2))

                                                if print_time_series:
                                                    df = pd.DataFrame(ts_report)
                                                    df.to_csv(output_directory + os.path.sep + simulation_name + '.csv')

                                                report.append(
                                                    {"simulation_name": simulation_name,
                                                     "file_name": file_description,
                                                     "file_total_volume": file_total_volume,
                                                     "trade_every": trade_every,
                                                     "series_std_ratio": series_std_ratio,
                                                     "liquidation_incentive": l_incentive,
                                                     "price_recovery_time": price_recovery_time,
                                                     "volume_for_slippage_10_percents": volume_for_slippage_10_percents,
                                                     "delay_in_minutes": delay_in_minutes,
                                                     "cycle_trade_volume": cycle_trade_volume,
                                                     "collateral": collateral * self.ETH_PRICE,
                                                     "recovery_halflife_retail": recovery_halflife_retail,
                                                     "share_institutional": share_institutional,
                                                     "stability_pool_initial_balance_ratio": s_balance,
                                                     "stability_pool_initial_balance": stability_pool_initial_balance,
                                                     "collateral_liquidation_factor": l_factor,
                                                     "target_volume": target_volume,
                                                     "simulation volume": all_liquidations_volume,
                                                     "min_multiply_price_liquidation_factor": min_multiply_price_liquidation_factor,
                                                     "max_liquidation_volume": max_liquidation_volume,
                                                     "min_price_liquidation_factor": min_price_liquidation_factor,
                                                     "max_simulation_daily_volume": max_daily_volume,
                                                     "max_drop": max_drop,
                                                     "price_at_max_drop": price_at_max_drop,
                                                     "max_drop_volume": max_drop_open_volume,
                                                     "pnl": simulation_pnl,
                                                     "open_volume": open_volume})
            df = pd.DataFrame(report)
            df.to_csv(output_file_name)
        except Exception as e:
            print("Exception !!!!!!!!!!!!!!!", str(e))
            traceback.print_exc()

