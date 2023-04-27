import glob

import matplotlib.pyplot as plt
import pandas as pd
import sys
import curve_lion
import random
import numpy as np
import os

def get_random_trades1(curve_liquidity, total_trades, timeseries_std, mean_reversion):
    std = (((curve_liquidity / 2) ** 2) / total_trades) ** 0.5
    std *= timeseries_std
    numbers = np.random.normal(loc=0, scale=std, size=total_trades)
    # injection_size = curve_liquidity / 3
    #
    # total_injections = 12
    # for i in range(total_injections):
    #     midpoint = (len(numbers) / total_injections) * i + (24 if i == 0 else 0)
    #     numbers = np.insert(numbers, int(midpoint), injection_size)
    #
    # numbers -= (injection_size * total_injections) / len(numbers)
    if mean_reversion == 1:
        numbers -= np.sum(numbers) / len(numbers)

    return numbers


def get_random_trades0(curve_liquidity, total_trades, timeseries_std, mean_reversion):
    std = (((curve_liquidity / 2) ** 2) / total_trades) ** 0.5
    std *= timeseries_std
    std = int(std)
    numbers =  [random.randint(-std, std) for i in range(total_trades)]
    if mean_reversion == 1:
        numbers -= np.sum(numbers) / len(numbers)

    # injection_size = curve_liquidity / 3
    # for i in range(12):
    #     midpoint = (len(numbers) / 12) * i + (24 if i == 0 else 0)
    #     numbers = np.insert(numbers, int(midpoint), injection_size)
    #
    # numbers -= int(injection_size * 12 / len(numbers))
    return numbers


def do_trade(trade_volume):
    global total_mint, total_buy, oracle_to_asset_depeg, total_unminted_volume

    price = oracle_to_asset_depeg.get_price(oracle_to_asset_depeg.ebtc_balance, oracle_to_asset_depeg.wbtc_balance)

    if trade_volume < 0:
        if price > 1:
            trade_volume /= price ** price_power_factor
        total_buy += trade_volume
        oracle_to_asset_depeg.ebtc_balance -= oracle_to_asset_depeg.get_return(oracle_to_asset_depeg.wbtc_index,
                                                                               oracle_to_asset_depeg.ebtc_index,
                                                                               -trade_volume,
                                                                               [oracle_to_asset_depeg.ebtc_balance,
                                                                                oracle_to_asset_depeg.wbtc_balance])
        oracle_to_asset_depeg.wbtc_balance += -trade_volume

    elif trade_volume > 0:
        if price < 1:
            volume_before = trade_volume
            trade_volume = volume_before * price ** price_power_factor
            total_unminted_volume += (volume_before - trade_volume)

        total_mint += trade_volume
        oracle_to_asset_depeg.wbtc_balance -= oracle_to_asset_depeg.get_return(
            oracle_to_asset_depeg.wbtc_index,
            oracle_to_asset_depeg.ebtc_index,
            trade_volume,
            [oracle_to_asset_depeg.wbtc_balance, oracle_to_asset_depeg.ebtc_balance])
        oracle_to_asset_depeg.ebtc_balance += trade_volume


def do_check_redemption(max_qty):
    global total_redemption
    price = oracle_to_asset_depeg.get_price(oracle_to_asset_depeg.ebtc_balance, oracle_to_asset_depeg.wbtc_balance)
    if price < redemption_price:
        redemption_volume = oracle_to_asset_depeg.close_arb(max_qty, redemption_price)["return_qty"]
        total_redemption += redemption_volume


def get_results():
    x = {
        "Minted": int(total_mint / 1e8),
        "Redemption": int(total_redemption / 1e8),
        "Unmintet": int(total_unminted_volume / 1e8),
        "Redemption/Minted": round(total_redemption / (total_mint + 1), 2),
        "UnMinted/Minted": round(total_unminted_volume / (total_mint + 1), 2)
    }
    return x


def create_graphs():
    files = glob.glob("results\\*.*.csv")
    for f in files:
        df = pd.read_csv(f)
        file_name = os.path.basename(f)
        fff = file_name.split(".")
        ponzi_delay = fff[0]
        price_power_factor = fff[1]
        redemption_frequency = fff[2]
        title = "ponzi_delay." + ponzi_delay + " price_power_factor." + price_power_factor + " redemption_frequency." + redemption_frequency
        img_name = "file_name" + file_name + ".jpg"

        do_plot("unminted-minted." + img_name, title, "unminted-minted", df.index, df["unminted/minted"],
                "unminted/minted", df["price"], "price")

        do_plot("redemption-minted." + img_name, title, "unminted-minted", df.index, df["redemption/minted"],
                "redemption/minted", df["price"], "price")

        do_plot("redemption-unminted-minted." + img_name, title, "(redemption+unminted)/minted", df.index,
                df["(redemption+unminted)/minted"],
                "(redemption+unminted)/minted", df["price"], "price")

        do_plot("redemption-total_ponzi_volume." + img_name, title, "redemption/total_ponzi_volume", df.index,
                df["redemption/total_ponzi_volume"],
                "redemption/total_ponzi_volume", df["current_ponzi_volume"], "current ponzi volume")


def do_plot(file_name, title, sub_title, x, y1, y1_name, y2, y2_name):
    plt.close()
    fig, ax1 = plt.subplots()
    fig.set_size_inches(12.5, 8.5)
    ax2 = ax1.twinx()
    x1 = ax1.plot(x, y1, 'r-', label=y1_name + " (Left)")
    x2 = ax2.plot(x, y2, 'm-', label=y2_name + " (Right)")
    lns = x1 + x2
    labs = [l.get_label() for l in lns]
    ax1.legend(lns, labs, loc=0)
    ax1.set_label('Time')
    plt.title(title)
    plt.suptitle(sub_title)
    print(file_name)
    plt.savefig("results_imgs/" + file_name + ".jpg")


def do_check_ponzi_box(index):
    global ponzi_box, total_ponzi_volume
    price = oracle_to_asset_depeg.get_price(oracle_to_asset_depeg.ebtc_balance, oracle_to_asset_depeg.wbtc_balance)
    if price < redemption_price:
        redemption_volume = oracle_to_asset_depeg.close_arb(2 ** 100, redemption_price)["return_qty"]
        if redemption_volume > 0:
            ponzi_box[index] = redemption_volume
            total_ponzi_volume += redemption_volume

    prev_index = index - ponzi_delay
    if prev_index in ponzi_box:
        trade_volume = ponzi_box[prev_index]
        del ponzi_box[prev_index]
        oracle_to_asset_depeg.wbtc_balance -= oracle_to_asset_depeg.get_return(
            oracle_to_asset_depeg.wbtc_index,
            oracle_to_asset_depeg.ebtc_index,
            trade_volume,
            [oracle_to_asset_depeg.wbtc_balance, oracle_to_asset_depeg.ebtc_balance])
        oracle_to_asset_depeg.ebtc_balance += trade_volume
        do_check_redemption(2 ** 100)


print_time_series = False
box_initial_balance = 1_000 * 1e8
box_A = 200
box_le = 0.1
box_recovery_halflife = 1
total_trades = 24 * 30 * 12
redemption_price = 0.98

redemption_frequencys = [2 ** 100]
ponzi_delays = [0, 24 * 30]
price_power_factors = [0]
mean_reversions = [0]
timeseries_stds = [10]

start = int(sys.argv[1])
all_results = []

ponzi_box = {}
for i in range(10):
    random_seed = start + i
    np.random.seed(random_seed)
    all_results = []
    print(random_seed)

    for timeseries_std in timeseries_stds:
        trade_list = get_random_trades1(box_initial_balance, total_trades, timeseries_std, 0)
        #trade_list = get_random_trades0(box_initial_balance, total_trades, timeseries_std, 0)
        for price_power_factor in price_power_factors:
            for redemption_frequency in redemption_frequencys:
                for ponzi_delay in ponzi_delays:
                    total_ponzi_volume = 0
                    total_unminted_volume = 0
                    total_buy = 0
                    total_mint = 0
                    total_redemption = 0
                    oracle_to_asset_depeg = curve_lion.curve_lion(box_A, box_initial_balance, box_initial_balance,
                                                                  box_le, 0.1,
                                                                  box_recovery_halflife)
                    index = 0
                    timeseries_data = []
                    for trade in trade_list:
                        price = oracle_to_asset_depeg.get_price(oracle_to_asset_depeg.ebtc_balance,
                                                                oracle_to_asset_depeg.wbtc_balance)

                        current_ponzi_volume = sum(ponzi_box.values())
                        timeseries_data.append({"trade_volume": trade,
                                                "total_unminted_volume": total_unminted_volume / 1e8,
                                                "total_buy": total_buy / 1e8,
                                                "total_mint": total_mint / 1e8,
                                                "total_ponzi_volume": total_ponzi_volume / 1e8,
                                                "total_redemption": total_redemption / 1e8,
                                                "price": price,
                                                "current_ponzi_volume": current_ponzi_volume / 1e8})

                        index += 1
                        do_trade(trade)
                        if ponzi_delay > 0:
                            do_check_ponzi_box(index)
                        else:
                            do_check_redemption(redemption_frequency)

                    df = pd.DataFrame(timeseries_data)
                    df["unminted/minted"] = df["total_unminted_volume"] / df["total_mint"]
                    df["redemption/minted"] = df["total_redemption"] / df["total_mint"]
                    df["(redemption+unminted)/minted"] = (df["total_unminted_volume"] + df["total_redemption"]) / df[
                        "total_mint"]
                    df["redemption/total_ponzi_volume"] = df["total_redemption"] / df["total_ponzi_volume"]
                    if print_time_series:
                        df.to_csv(f"results\\{ponzi_delay}.{price_power_factor}.{redemption_frequency}.csv")

                    results = get_results()
                    last_row = df.iloc[-1]
                    results["total_ponzi_volume"] = total_ponzi_volume
                    results["unminted/minted"] = last_row["total_unminted_volume"] / last_row["total_mint"]
                    results["redemption/minted"] = last_row["total_redemption"] / last_row["total_mint"]
                    results["(redemption+unminted)/minted"] = (last_row["total_unminted_volume"] + last_row[
                        "total_redemption"]) / last_row[
                                                                  "total_mint"]
                    #results["redemption/total_ponzi_volume"] = last_row["total_redemption"] / last_row["total_ponzi_volume"]
                    results["timeseries_std"] = timeseries_std
                    results["ponzi_delay"] = ponzi_delay
                    results["price_power_factor"] = price_power_factor
                    results["redemption_frequency"] = redemption_frequency

                    print('ponzi delay', str(ponzi_delay).ljust(10),
                          "ponzi volume", str(int(last_row["total_ponzi_volume"])).ljust(10),
                          "redemption", str(int(last_row["total_redemption"])).ljust(10),
                          "last ponzi volume", str(int(sum(ponzi_box.values()) / 1e8)).ljust(10),
                          round(last_row["total_redemption"] / last_row["total_mint"], 3))

                    all_results.append(results)

    pd.DataFrame(all_results).to_csv("redemption.csv")
