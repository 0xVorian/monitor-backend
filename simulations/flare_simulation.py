import glob
import itertools
import os
import sys
import traceback
import matplotlib.pyplot as plt
from joblib import Parallel, delayed
import pandas as pd
import copy
import datetime
import unibox
import traceback
import brownian_motion
import uuid

class flare_simulation():
    liquidation_incentive = 0.1
    initial_dept_volume = 100_000_000


    def get_site_id(self, SITE_ID, use_random=False):
        if str(os.path.sep) in SITE_ID:
            SITE_ID = SITE_ID.split(str(os.path.sep))[0]
        n = datetime.datetime.now()
        d = str(n.year) + "-" + str(n.month) + "-" + str(n.day) + "-" + str(n.hour) + "-" + str(n.minute)
        rnd = ""
        if use_random:
            rnd = "_" + str(uuid.uuid4())
        SITE_ID = SITE_ID + os.path.sep + d + rnd
        os.makedirs("webserver" + os.path.sep + SITE_ID, exist_ok=True)
        return SITE_ID

    def usd_liquidation_size_with_flare(self, safe_ratio, curr_price, usd_collateral, btc_debt, liquidation_bonus,
                                        usd_liquidation_ratio, flare_collateral, flare_price, flare_safe_ratio):
        usd_curr_ratio = usd_collateral / (btc_debt * curr_price)
        flare_curr_ratio = flare_collateral * flare_price / (btc_debt * curr_price)
        # print("xxx", curr_ratio)

        usd_ratio = usd_liquidation_ratio
        if usd_ratio > usd_curr_ratio:
            usd_ratio = usd_curr_ratio

        flare_ratio = 1 + liquidation_bonus - usd_ratio
        if flare_ratio > flare_curr_ratio:
            flare_ratio = flare_curr_ratio
            usd_ratio = min(1 + liquidation_bonus - flare_ratio, usd_curr_ratio)

        # print(flare_ratio, flare_curr_ratio)

        burned_btc_1 = min(btc_debt * (safe_ratio - usd_curr_ratio) / (safe_ratio - (1 + liquidation_bonus)), btc_debt)
        burned_btc_2 = min(
            btc_debt * (flare_safe_ratio - flare_curr_ratio) / (flare_safe_ratio - (1 + liquidation_bonus)),
            btc_debt)
        burned_btc = max(burned_btc_1, burned_btc_2)

        usd_liquidation_size = burned_btc * usd_ratio * curr_price
        flare_liquidation_size = burned_btc * curr_price * flare_ratio / flare_price

        return {"usd_liquidation": usd_liquidation_size, "burned_btc": burned_btc,
                "flare_liquidation": flare_liquidation_size}

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

    def convert_to_array(self, dai_eth):
        arr = []
        for index, row in dai_eth.iterrows():
            arr.append({"timestamp_x": row["timestamp_x"],
                        "btc_usd_price": row["btc_usd_price"],
                        "flare_btc_price": row["flare_btc_price"],
                        "flare_usd_price": row["flare_btc_price"] * row["btc_usd_price"]})
        return arr

    def crete_price_trajectory(self, eth_usd_data, binance_btc_for_flare_data, btc_usd_std, flr_btc_std):

        data1 = eth_usd_data
        data1["btc_usd_price"] = data1["open"]

        # binance_btc_for_flare_data["ask_price"] = binance_btc_for_flare_data["open"]
        # binance_btc_for_flare_data["bid_price"] = binance_btc_for_flare_data["open"]

        data2 = self.adjust_series_price(copy.deepcopy(binance_btc_for_flare_data), flr_btc_std)
        min_len = min(len(data1), len(data2))

        data1 = data1.loc[:min_len - 1]
        data2 = data2.loc[:min_len - 1]
        data1 = data1.reset_index(drop=True)
        data2 = data2.reset_index(drop=True)
        data1["flare_btc_price"] = data2["adjust_price"]
        data1["timestamp_x"] = data2["timestamp_x"]

        dai_eth_array = self.convert_to_array(data1)
        return dai_eth_array

    def get_liquidation_incentive(self, start_liquidation_time, current_time, liquidation_incentive_time_factor):
        time_diff_in_s_hours_units = int((current_time - start_liquidation_time) / (1000 * 1000 * 60 * 60 * 3))
        time_diff_in_s_hours_units = min(time_diff_in_s_hours_units, 6)  # max 6 units
        return self.liquidation_incentive + time_diff_in_s_hours_units * liquidation_incentive_time_factor

    def create_liquidation_df(self, collateral_volume, debt_volume, min_cr):
        return pd.DataFrame()

    def run_single_simulation(self,collateral_asset_name,
                              eth_usdt_data, flare_btc_data,
                              btc_usd_std, flr_btc_std,
                              debt_volume, min_usd_cr, safe_usd_cr,
                              usd_collateral_ratio,
                              usd_dl_x, flr_dl_x,
                              usd_dl_recovery, flr_dl_recovery,
                              min_flare_cr, safe_flare_cr,
                              liquidation_incentive_time_factor,
                              SITE_ID, seed=0):

        eth_usdt_data = copy.deepcopy(eth_usdt_data)
        flare_btc_data = copy.deepcopy(flare_btc_data)

        initial_safe_flare_cr = safe_flare_cr
        initial_safe_usd_cr = safe_usd_cr
        initial_usd_dl_x = usd_dl_x
        initial_flr_dl_x = flr_dl_x

        safe_flare_cr += min_flare_cr
        safe_usd_cr += min_usd_cr
        usd_dl_x *= debt_volume
        flr_dl_x *= debt_volume

        flr_collateral_volume = safe_flare_cr * debt_volume
        usd_collateral_volume = safe_usd_cr * debt_volume

        uni_box = unibox.unibox(flr_dl_x, usd_dl_x)

        initial_debt_volume_for_simulation = debt_volume
        initial_flr_collateral_volume_for_simulation = flr_collateral_volume
        initial_usd_collateral_volume_for_simulation = usd_collateral_volume
        min_usd_ucr = float('inf')
        min_flr_ucr = float('inf')
        running_score = 0
        time_series_report_name = ""
        try:
            flr_liquidation_table = []
            usd_liquidation_table = []
            time_series_report = []

            file = self.crete_price_trajectory(eth_usdt_data, flare_btc_data, btc_usd_std, flr_btc_std)
            state = 0
            debt_volume /= file[0]["btc_usd_price"]
            flr_collateral_volume /= file[0]["flare_usd_price"]
            initial_adjust_dept_volume_for_simulation = debt_volume
            total_liquidations = 0
            total_flare_liquidation = 0
            total_usd_liquidation = 0
            start_liquidation_time = 0
            for row in file:
                current_time = row["timestamp_x"]
                row_btc_usd_price = row["btc_usd_price"]
                row_flare_btc_price = row["flare_btc_price"]
                row_flare_usd_price = row["flare_usd_price"]
                uni_box.update_prices(row_flare_usd_price, row_btc_usd_price)
                # print(row_flare_usd_price, row_btc_usd_price)
                while len(flr_liquidation_table) > flr_dl_recovery:
                    first_flr_liquidation_table = flr_liquidation_table.pop(0)
                    # print("FLARE", first_flr_liquidation_table)
                    uni_box.recover_flare_liquidity(first_flr_liquidation_table)

                # recover usd_x_y
                while len(usd_liquidation_table) > usd_dl_recovery:
                    first_usd_liquidation_table = usd_liquidation_table.pop(0)
                    # print("USD", first_usd_liquidation_table)
                    uni_box.recover_usd_liquidity(first_usd_liquidation_table)

                usd_ucr = 2
                flr_ucr = 2
                if debt_volume > 0:
                    usd_ucr = usd_collateral_volume / (debt_volume * row_btc_usd_price)
                    flr_ucr = (flr_collateral_volume * row_flare_usd_price) / (debt_volume * row_btc_usd_price)

                min_usd_ucr = min(min_usd_ucr, usd_ucr)
                min_flr_ucr = min(min_flr_ucr, flr_ucr)
                open_liquidation = 0
                li = 0
                if (debt_volume > 0 and (usd_ucr <= min_usd_cr
                        or flr_ucr <= min_flare_cr
                        or (state == 1 and (usd_ucr <= safe_usd_cr or flr_ucr <= safe_flare_cr)))):
                    if start_liquidation_time == 0:
                        start_liquidation_time = current_time
                    state = 1

                    li = self.get_liquidation_incentive(start_liquidation_time, current_time,
                                                        liquidation_incentive_time_factor)
                    if li + 1 >= safe_usd_cr:
                        li = safe_usd_cr - 1.01

                    l_size = self.usd_liquidation_size_with_flare(safe_usd_cr, row_btc_usd_price, usd_collateral_volume,
                                                                  debt_volume,
                                                                  li,
                                                                  usd_collateral_ratio, flr_collateral_volume,
                                                                  row_flare_usd_price, safe_flare_cr)


                    burned_btc_volume = l_size["burned_btc"]
                    usd_liquidation_volume = l_size["usd_liquidation"]
                    flr_liquidation_volume = l_size["flare_liquidation"]
                    open_liquidation = burned_btc_volume

                    obj = uni_box.find_btc_liquidation_size(burned_btc_volume, flr_liquidation_volume,
                                                            usd_liquidation_volume)
                    usd_liquidation_volume = obj["usd"]
                    flr_liquidation_volume = obj["flare"]
                    burned_btc_volume = obj["btc"]

                    btc_returned1 = uni_box.dump_usd_to_btc(usd_liquidation_volume)
                    usd_liquidation_table.append(btc_returned1)
                    btc_returned2 = uni_box.dump_flare_to_btc(flr_liquidation_volume)
                    flr_liquidation_table.append(btc_returned2)

                    if burned_btc_volume > debt_volume:
                        print(burned_btc_volume, debt_volume)
                        print("XXXX")
                        exit()

                    usd_collateral_volume -= usd_liquidation_volume
                    flr_collateral_volume -= flr_liquidation_volume
                    total_liquidations += burned_btc_volume
                    total_flare_liquidation += flr_liquidation_volume
                    total_usd_liquidation += usd_liquidation_volume
                    debt_volume -= burned_btc_volume

                else:
                    flr_liquidation_table.append(0)
                    usd_liquidation_table.append(0)
                    state = 0
                    start_liquidation_time = 0

                uni_usd = uni_box.get_usd_xy()
                uni_flare = uni_box.get_flare_xy()
                report_row = {"timestamp": row["timestamp_x"],
                              "simulation_initial_debt_volume": initial_adjust_dept_volume_for_simulation,
                              collateral_asset_name +  "_usd_price": row_btc_usd_price,
                              "flare_" + collateral_asset_name + "_price": row_flare_btc_price,
                              "flare_usd_price": row_flare_usd_price,
                              "debt_volume": debt_volume,
                              "usd_collateral_volume": usd_collateral_volume,
                              "flare_collateral_volume": flr_collateral_volume,
                              "uniswap_" + collateral_asset_name  + "_usd_price_deviation": (uni_usd["usd"] / uni_usd["btc"]) - 1,
                              "uniswap_flare_" + collateral_asset_name + "_price_deviation": (uni_flare["flare"] / uni_flare["btc"]) - 1,
                              "total_flare_liquidation": total_flare_liquidation,
                              "total_usd_liquidation": total_usd_liquidation,
                              "total_liquidations": total_liquidations,
                              "open_liquidation": open_liquidation,
                              "li": li,
                              "usd_ucr": usd_ucr,
                              "flare_ucr": flr_ucr,
                              "min_flare_ucr": min_flr_ucr,
                              "min_usd_ucr": min_usd_ucr}

                time_series_report.append(report_row)

            time_series_report_name = f"webserver" + os.path.sep + SITE_ID + os.path.sep + \
                                      f"{collateral_asset_name}Std-{btc_usd_std}+" \
                                      f"FlrStd-{flr_btc_std}+" \
                                      f"MinUsdCr-{min_usd_cr}+" \
                                      f"SafeUsdCr-{round(initial_safe_usd_cr, 2)}+" \
                                      f"LiTimeFactor-{liquidation_incentive_time_factor}+" \
                                      f"MinFlrCr-{min_flare_cr}+" \
                                      f"SafeFlrCr-{round(initial_safe_flare_cr, 2)}+" \
                                      f"UsdCr-{usd_collateral_ratio}+" \
                                      f"UsdDlX-{initial_usd_dl_x}+" \
                                      f"UsdRec-{usd_dl_recovery}+" \
                                      f"FlrDlX-{initial_flr_dl_x}+" \
                                      f"FlrRec-{flr_dl_recovery}"

            report_df = pd.DataFrame(time_series_report)
            if save_time_seriws:
                report_df.to_csv(time_series_report_name + ".csv")
            plt.cla()
            plt.close()
            fig, ax1 = plt.subplots()
            fig.set_size_inches(12.5, 8.5)
            ax2 = ax1.twinx()
            total_flare_liquidation_for_report = report_df["total_flare_liquidation"].max() / (
                        initial_flr_collateral_volume_for_simulation / file[0]["flare_usd_price"])
            title = "Min USD CR: " + str(round(min_usd_ucr, 2)) + " Min Flare CR: " + str(round(min_flr_ucr, 2))
            running_score = (report_df["open_liquidation"] / report_df[["usd_ucr", "flare_ucr"]].min(axis=1)).mean()
            suptitle = "Score: " + str(round(running_score, 2)) + \
                       " Total Flare Liquidation: " + str(round(total_flare_liquidation_for_report, 2)) + \
                       " Seed: " + str(seed)
            plt.suptitle(suptitle)
            plt.title(title)

            x1 = ax1.plot(report_df["timestamp"], report_df[collateral_asset_name +  "_usd_price"] / report_df.iloc[0][collateral_asset_name + "_usd_price"], 'b-',
                          label=collateral_asset_name + " Usd Price")

            x2 = ax1.plot(report_df["timestamp"],
                          (1 / report_df["flare_" + collateral_asset_name+ "_price"]) / (1 / report_df.iloc[0]["flare_" + collateral_asset_name +  "_price"]), 'g-',
                          label=collateral_asset_name + " Flare Price")

            x3 = ax1.plot(report_df["timestamp"], report_df["usd_ucr"], 'r-', label="Usd CR")

            x4 = ax1.plot(report_df["timestamp"], report_df["flare_ucr"], 'c-', label="Flare CR")

            x5 = ax2.plot(report_df["timestamp"],
                          report_df["debt_volume"] / report_df.iloc[0]["debt_volume"], 'm-',
                          label="DebtVolume")

            x6 = ax2.plot(report_df["timestamp"],
                          (report_df["usd_collateral_volume"] / report_df[collateral_asset_name + "_usd_price"]) / report_df.iloc[0][
                              "debt_volume"], 'y-',
                          label="UsdCollateralVolume")

            x7 = ax2.plot(report_df["timestamp"],
                          (report_df["flare_collateral_volume"] * report_df["flare_usd_price"] / report_df[
                              collateral_asset_name + "_usd_price"]) / report_df.iloc[0]["debt_volume"], 'b-',
                          label="FlareCollateralVolume")

            x8 = ax2.plot(report_df["timestamp"],
                          report_df["open_liquidation"] / report_df.iloc[0]["debt_volume"],
                          label="OpenLiquidations")

            x9 = ax2.plot(report_df["timestamp"],
                          report_df["total_liquidations"] / report_df.iloc[0]["debt_volume"],
                          label="TotalLiquidations")

            lns = x1 + x2 + x3 + x4 + x5 + x6 + x7 + x8 + x9
            labs = [l.get_label() for l in lns]
            ax1.legend(lns, labs, loc=0)
            if save_images:
                plt.savefig(time_series_report_name + ".jpg")

        except Exception as e:
            min_usd_ucr = -100
            min_flare_ucr = -100
            print(traceback.format_exc())
            print("Exception!!!!!")
            exit()

        finally:
            return {
                "file_name": time_series_report_name,
                collateral_asset_name + "_usd_std": btc_usd_std,
                "flr_" + collateral_asset_name +"_std": flr_btc_std,
                "debt_volume": initial_debt_volume_for_simulation,
                "usd_collateral_volume": initial_usd_collateral_volume_for_simulation,
                "flare_collateral_volume": initial_flr_collateral_volume_for_simulation,
                "liquidation_incentive_time_factor": liquidation_incentive_time_factor,
                "usd_dl_x": initial_usd_dl_x,
                "usd_dl_recovery": usd_dl_recovery,
                "flare_dl_x": initial_flr_dl_x,
                "flare_dl_recovery": flr_dl_recovery,
                "min_usd_cr": min_usd_cr,
                "min_flare_cr": min_flare_cr,
                "safe_usd_cr": safe_usd_cr,
                "safe_flare_cr": safe_flare_cr,
                "usd_collateral_ratio": usd_collateral_ratio,
                "min_usd_ucr": min_usd_ucr,
                "min_flare_ucr": min_flr_ucr,
                "running_score": running_score,
                "total_flare_liquidation_for_report": total_flare_liquidation_for_report,
                "seed": seed}

    def run_simulation(self, collateral_asset_name, c, eth_usdt_data, flare_btc_data, SITE_ID, seed=0):
        summary_report = []
        all = itertools.product(c["btc_usd_std"], c["flare_btc_std"],
                                c["debt_volume"], c["min_usd_cr"], c["safe_usd_cr"],
                                c["usd_collateral_ratio"],
                                c["usd_dl_x"], c["flare_dl_x"],
                                c["usd_dl_recovery"], c["flare_dl_recovery"],
                                c["min_flare_cr"], c["safe_flare_cr"], c["liquidation_incentive_time_factor"])
        myprod2 = copy.deepcopy(all)
        all_runs = len(list(myprod2))
        print("Total Runs", all_runs)
        indx = 0
        for r in all:
            report = self.run_single_simulation(collateral_asset_name, eth_usdt_data, flare_btc_data, r[0], r[1], r[2], r[3], r[4], r[5], r[6],
                                                r[7], r[8], r[9], r[10], r[11], r[12], SITE_ID, seed)

            summary_report.append(report)
            indx += 1
            print(indx / all_runs)
            pd.DataFrame(summary_report).to_csv(f"webserver" + os.path.sep + SITE_ID + os.path.sep + "summary.csv")
        pd.DataFrame(summary_report).to_csv(f"webserver" + os.path.sep + SITE_ID + os.path.sep + "summary.csv")

    def run_random_simulation(self, collateral_asset_name, seed):
        c = {
            "btc_usd_std": [1],
            "flare_btc_std": [1],
            "debt_volume": [self.initial_dept_volume],
            "usd_dl_x": [0.1, 0.2, 0.3],
            "usd_dl_recovery": [30, 60, 90, 120],
            "flare_dl_x": [0.1, 0.2, 0.3],
            "flare_dl_recovery": [30, 60, 90, 120],
            "min_usd_cr": [1.2, 1.3, 1.4],
            "safe_usd_cr": [0.2, 0.3, 0.4],
            "min_flare_cr": [1.5, 1.7, 2.0],
            "safe_flare_cr": [0.1, 0.5, 1.0],
            "usd_collateral_ratio": [1],
            "liquidation_incentive_time_factor": [0, 0.05]}

        SITE_ID = self.get_site_id("flare", True)
        btc_usdt_data = brownian_motion.generate_brownian_motion(0.3, 100, 60 * 24, seed)
        btc_usdt_data["open"] = btc_usdt_data["adjust_price"]
        btc_usdt_data["ask_price"] = btc_usdt_data["adjust_price"]
        btc_usdt_data["bid_price"] = btc_usdt_data["adjust_price"]

        flare_btc_data = brownian_motion.generate_brownian_motion(0.5, 100, 60 * 24, seed + 1)
        flare_btc_data["open"] = flare_btc_data["adjust_price"]
        flare_btc_data["ask_price"] = flare_btc_data["adjust_price"]
        flare_btc_data["bid_price"] = flare_btc_data["adjust_price"]

        result = self.run_simulation(collateral_asset_name, c,btc_usdt_data, flare_btc_data, SITE_ID, seed)

    def run_regular_simulation(self, collateral_asset_name):
        c = {}
        if collateral_asset_name == "Btc":
            c = {
                "btc_usd_std": [1],
                "flare_btc_std": [0.5],
                "debt_volume": [self.initial_dept_volume],
                "usd_dl_x": [0.1, 0.2, 0.3],
                "usd_dl_recovery": [30, 60, 90, 120],
                "flare_dl_x": [0.1, 0.2, 0.3],
                "flare_dl_recovery": [30, 60, 90, 120],
                "min_usd_cr": [1.2, 1.3, 1.4],
                "safe_usd_cr": [0.2, 0.3, 0.4],
                "min_flare_cr": [1.5, 1.7, 2.0],
                "safe_flare_cr": [0.1, 0.5, 1.0],
                "usd_collateral_ratio": [1],
                "liquidation_incentive_time_factor": [0, 0.05]}

            SITE_ID = self.get_site_id("flare")
            binance_btcusdt = "data\\binance_btcusdt.csv"
            simulation_file_name = "c:\\dev\\monitor-backend\\simulations\\data_worst_day\\data_unified_2020_03_ETHUSDT.csv"
            flare_btc_data = pd.read_csv(simulation_file_name)
            btc_usdt_data = pd.read_csv(binance_btcusdt)
            self.run_simulation(collateral_asset_name, c, btc_usdt_data, flare_btc_data, SITE_ID)

        if collateral_asset_name == "Doge":
            c = {
                "btc_usd_std": [1],
                "flare_btc_std": [2],
                "debt_volume": [self.initial_dept_volume],
                "usd_dl_x": [0.1, 0.2, 0.3],
                "usd_dl_recovery": [30, 60, 90, 120],
                "flare_dl_x": [0.1, 0.2, 0.3],
                "flare_dl_recovery": [30, 60, 90, 120],
                "min_usd_cr": [1.5, 2.0, 2.5],
                "safe_usd_cr": [0.2, 0.3, 0.4],
                "min_flare_cr": [2, 2.5, 3.0],
                "safe_flare_cr": [0.1, 0.5, 1.0],
                "usd_collateral_ratio": [1],
                "liquidation_incentive_time_factor": [0, 0.05]}

            SITE_ID = self.get_site_id("flare")
            binance_dogusdt = "data\\binance_dogeusdt.csv"
            simulation_file_name = "c:\\dev\\monitor-backend\\simulations\\data_worst_day\\data_unified_2020_03_ETHUSDT.csv"
            flare_btc_data = pd.read_csv(simulation_file_name)
            dog_usdt_data = pd.read_csv(binance_dogusdt)
            self.run_simulation(collateral_asset_name, c, dog_usdt_data, flare_btc_data, SITE_ID)

        if collateral_asset_name == "Xrp":
            c = {
                "btc_usd_std": [1],
                "flare_btc_std": [0.66],
                "debt_volume": [self.initial_dept_volume],
                "usd_dl_x": [0.1, 0.2, 0.3],
                "usd_dl_recovery": [30, 60, 90, 120],
                "flare_dl_x": [0.1, 0.2, 0.3],
                "flare_dl_recovery": [30, 60, 90, 120],
                "min_usd_cr": [1.2, 1.3, 1.4],
                "safe_usd_cr": [0.2, 0.3, 0.4],
                "min_flare_cr": [1.5, 1.7, 2.0],
                "safe_flare_cr": [0.1, 0.5, 1.0],
                "usd_collateral_ratio": [1],
                "liquidation_incentive_time_factor": [0, 0.05]}

            SITE_ID = self.get_site_id("flare")
            binance_dogusdt = "data\\binance_xrpusdt.csv"
            simulation_file_name = "c:\\dev\\monitor-backend\\simulations\\data_worst_day\\data_unified_2020_03_ETHUSDT.csv"
            flare_btc_data = pd.read_csv(simulation_file_name)
            dog_usdt_data = pd.read_csv(binance_dogusdt)
            self.run_simulation(collateral_asset_name, c, dog_usdt_data, flare_btc_data, SITE_ID)


    def analyaze_random_results(self, collateral_asset_name):
        files = glob.glob("flare_data\\**\\*.csv", recursive=True)
        df = pd.concat((pd.read_csv(f) for f in files), ignore_index=True)
        gg = [collateral_asset_name + "_usd_std", "flr_" + collateral_asset_name + "_std", "debt_volume", "usd_collateral_volume", "flare_collateral_volume",
              "liquidation_incentive_time_factor", "usd_dl_x", "usd_dl_recovery", "flare_dl_x", "flare_dl_recovery",
              "min_usd_cr", "min_flare_cr", "safe_usd_cr", "safe_flare_cr", "usd_collateral_ratio"]
        # df = pd.read_csv("xxx.csv")
        seed = df.iloc[0]["seed"]
        uniques = df.loc[df["seed"] == seed][gg]
        for index, row in uniques.iterrows():
            temp_df = df.loc[
                (df[collateral_asset_name + "_usd_std"] == row[collateral_asset_name + "_usd_std"]) &
                (df["flr_" + collateral_asset_name + "_std"] == row["flr_" + collateral_asset_name + "_std"]) &
                (df["debt_volume"] == row["debt_volume"]) &
                (df["usd_collateral_volume"] == row["usd_collateral_volume"]) &
                (df["flare_collateral_volume"] == row["flare_collateral_volume"]) &
                (df["liquidation_incentive_time_factor"] == row["liquidation_incentive_time_factor"]) &
                (df["usd_dl_x"] == row["usd_dl_x"]) &
                (df["usd_dl_recovery"] == row["usd_dl_recovery"]) &
                (df["flare_dl_x"] == row["flare_dl_x"]) &
                (df["flare_dl_recovery"] == row["flare_dl_recovery"]) &
                (df["min_usd_cr"] == row["min_usd_cr"]) &
                (df["min_flare_cr"] == row["min_flare_cr"]) &
                (df["safe_usd_cr"] == row["safe_usd_cr"]) &
                (df["safe_flare_cr"] == row["safe_flare_cr"]) &
                (df["usd_collateral_ratio"] == row["usd_collateral_ratio"])
                ]

            temp_df = temp_df.sort_values(['min_usd_ucr', 'min_flare_cr'])

            selected_row_00 = temp_df.iloc[int(len(temp_df) * 0)]
            seed_00 = selected_row_00["seed"]
            min_usd_ucr_00 = selected_row_00["min_usd_ucr"]
            min_flare_ucr_00 = selected_row_00["min_flare_ucr"]

            selected_row_01 = temp_df.iloc[int(len(temp_df) * 0.1)]
            seed_01 = selected_row_01["seed"]
            min_usd_ucr_01 = selected_row_01["min_usd_ucr"]
            min_flare_ucr_01 = selected_row_01["min_flare_ucr"]

            selected_row_09 = temp_df.iloc[int(len(temp_df) * 0.9)]
            seed_09 = selected_row_09["seed"]
            min_usd_ucr_09 = selected_row_09["min_usd_ucr"]
            min_flare_ucr_09 = selected_row_09["min_flare_ucr"]

            selected_row_10 = temp_df.iloc[int(len(temp_df) * 1) - 1]
            seed_10 = selected_row_10["seed"]
            min_usd_ucr_10 = selected_row_10["min_usd_ucr"]
            min_flare_ucr_10 = selected_row_10["min_flare_ucr"]

            if min_usd_ucr_00 > min_usd_ucr_10:
                print(min_usd_ucr_00, min_usd_ucr_10)
                exit()

            print(index, len(temp_df))
            uniques.at[index, 'seed_00'] = seed_00
            uniques.at[index, 'min_usd_ucr_00'] = min_usd_ucr_00
            uniques.at[index, 'min_flare_ucr_00'] = min_flare_ucr_00

            uniques.at[index, 'seed_01'] = seed_01
            uniques.at[index, 'min_usd_ucr_01'] = min_usd_ucr_01
            uniques.at[index, 'min_flare_ucr_01'] = min_flare_ucr_01

            uniques.at[index, 'seed_09'] = seed_09
            uniques.at[index, 'min_usd_ucr_09'] = min_usd_ucr_09
            uniques.at[index, 'min_flare_ucr_09'] = min_flare_ucr_09

            uniques.at[index, 'seed_10'] = seed_10
            uniques.at[index, 'min_usd_ucr_10'] = min_usd_ucr_10
            uniques.at[index, 'min_flare_ucr_10'] = min_flare_ucr_10

        uniques.to_csv("uniques.csv", index=False)
        return uniques

    def create_timeseries_for_seed(self, seed, title):
        btc_usdt_data = brownian_motion.generate_brownian_motion(0.3, 100, 60 * 24, seed)
        btc_usdt_data["open"] = btc_usdt_data["adjust_price"]
        btc_usdt_data["ask_price"] = btc_usdt_data["adjust_price"]
        btc_usdt_data["bid_price"] = btc_usdt_data["adjust_price"]

        flare_btc_data = brownian_motion.generate_brownian_motion(0.5, 100, 60 * 24, seed + 1)
        flare_btc_data["open"] = flare_btc_data["adjust_price"]
        flare_btc_data["ask_price"] = flare_btc_data["adjust_price"]
        flare_btc_data["bid_price"] = flare_btc_data["adjust_price"]

        file = self.crete_price_trajectory(btc_usdt_data, flare_btc_data, 1, 1)
        report_df = pd.DataFrame(file)
        plt.plot(report_df["btc_usd_price"] / report_df.iloc[0]["btc_usd_price"], label="btc usd")
        plt.plot((1 / report_df["flare_btc_price"]) / (1 / report_df.iloc[0]["flare_btc_price"]), label="btc flare")
        plt.title("Seed: " + str(seed))
        plt.suptitle(title)
        plt.legend()
        plt.show()
        plt.cla()
        plt.close()

    def run_simulation_on_random_analisys(self,collateral_asset_name, SITE_ID, record, percentile):

        seed = int(record["seed_" + str(percentile)])
        btc_usdt_data = brownian_motion.generate_brownian_motion(0.3, 100, 60 * 24, seed)
        btc_usdt_data["open"] = btc_usdt_data["adjust_price"]
        btc_usdt_data["ask_price"] = btc_usdt_data["adjust_price"]
        btc_usdt_data["bid_price"] = btc_usdt_data["adjust_price"]

        flare_btc_data = brownian_motion.generate_brownian_motion(0.5, 100, 60 * 24, seed + 1)
        flare_btc_data["open"] = flare_btc_data["adjust_price"]
        flare_btc_data["ask_price"] = flare_btc_data["adjust_price"]
        flare_btc_data["bid_price"] = flare_btc_data["adjust_price"]

        result = flare_simulation().run_single_simulation(
            collateral_asset_name,
            btc_usdt_data,
            flare_btc_data,
            1, 1,
            record["debt_volume"], record["min_usd_cr"], record["safe_usd_cr"] - record["min_usd_cr"],
            record["usd_collateral_ratio"],
            record["usd_dl_x"], record["flare_dl_x"],
            record["usd_dl_recovery"], record["flare_dl_recovery"],
            record["min_flare_cr"], record["safe_flare_cr"] - record["min_flare_cr"],
            record["liquidation_incentive_time_factor"],
            SITE_ID, seed)

        gg = [collateral_asset_name + "_usd_std",
              "flr_"+ collateral_asset_name+"_std", "debt_volume",
              "liquidation_incentive_time_factor", "usd_dl_x", "usd_dl_recovery", "flare_dl_x", "flare_dl_recovery",
              "min_usd_cr", "min_flare_cr", "safe_usd_cr", "safe_flare_cr", "usd_collateral_ratio"]

        for g in gg:
            if result[g] != record[g]:
                print(g, result[g], record[g])
                exit()

        if round(result["min_usd_ucr"], 2) != round(record["min_usd_ucr_" + str(percentile)], 2):
            print("error in usd", result["min_usd_ucr"], record["min_usd_ucr_" + str(percentile)])
            exit()

        if round(result["min_flare_ucr"], 2) != round(record["min_flare_ucr_" + str(percentile)], 2):
            print("error in flare", result["min_flare_ucr"], record["min_flare_ucr_" + str(percentile)])
            exit()

        print(seed, result["min_usd_ucr"], record["min_usd_ucr_" + str(percentile)])

        return result

    def run_simulations_on_random_analisys(self,collateral_asset_name, percentile, file_name="uniques.csv"):
        SITE_ID = self.get_site_id("flare")
        df = pd.read_csv(file_name)
        records = df.to_dict('records')
        print(len(records))
        Parallel(n_jobs=10)(delayed(self.run_simulation_on_random_analisys)(collateral_asset_name, SITE_ID, r, percentile) for r in records)

    def is_cheaper(self, row1, row2, map):
        for key in map:
            if map[key] == "+" and row1[key] < row2[key]:
                return True
            if map[key] == "-" and row1[key] > row2[key]:
                return True
        return False

    def is_alive(self, row):
        return row["min_usd_ucr_01"] >= 1.1 and row["min_flare_ucr_01"] >= 1.1

    def find_ef_on_random_analisys(self, file_name="uniques.csv"):
        #min_usd_cr, min_flare_cr, safe_usd_cr, safe_flare_cr
        map = {"min_usd_cr": "+", "min_flare_cr": "+", "safe_usd_cr": "+", "safe_flare_cr": "+",
               "liquidation_incentive_time_factor":"+",
               "usd_dl_x":"+", "flare_dl_x":"+",
               "usd_dl_recovery":"-", "flare_dl_recovery":"-"}
        keys = map.keys()
        df = pd.read_csv(file_name)
        report = []
        for index1, row1 in df.iterrows():
            is_valid = True
            if self.is_alive(row1):
                for index2, row2 in df.iterrows():
                    if index1 != index2 and self.is_alive(row2) and not self.is_cheaper(row1, row2, map):
                        print("index", index1, "row2 is better")
                        is_valid = False
                        break
                if is_valid:
                    report_row = {}
                    for cl in df.columns:
                        report_row[cl] = row1[cl]
                    report.append(report_row)
                    print("report", len(report))
            else:
                print("index", index1, " is dead")
        print(len(report))
        pd.DataFrame(report).to_csv("ef.csv", index=False)


if __name__ == '__main__':
    ######
    # save_time_seriws =  False
    # save_images = False
    # initail_seed = int(sys.argv[1])
    # total_runs = 50
    # Parallel(n_jobs=10)(delayed(flare_simulation().run_random_simulation)("Btc", initail_seed + j) for j in range(total_runs))

    # flare_simulation().analyaze_random_results("Btc")

    # flare_simulation().create_timeseries_for_seed(1030, "Best")
    # flare_simulation().create_timeseries_for_seed(1019, "Worst")

    save_time_seriws = False
    save_images = True
    flare_simulation().run_simulations_on_random_analisys("Btc", "01")

    # flare_simulation().find_ef_on_random_analisys()

    # collateral_asset = "Xrp"
    # save_time_seriws = False
    # save_images = True
    # flare_simulation().run_regular_simulation(collateral_asset)

