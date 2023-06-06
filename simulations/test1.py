import pandas as pd
import numpy as np

def calc_std(df1, df2, market_name):

    test_rolling_std = np.average(
        df1["price"].rolling(5 * 30).std().dropna() / df1["price"].rolling(5 * 30).mean().dropna())

    eth_rolling_std = np.average(
        df2["price"].rolling(5 * 30).std().dropna() / df2["price"].rolling(5 * 30).mean().dropna())


    print("-----------------------------------------------------")
    print(market_name)
    print("eth_avg", np.average(df2["price"]))
    print("eth_min", np.min(df2["price"]))
    print("eth_std", np.std(df2["price"]) / np.average(df2["price"]))
    print("test_avg", np.average(df1["price"]))
    print("test_min", np.min(df1["price"]))
    print("test_std", np.std(df1["price"]) / np.average(df1["price"]))
    print("std Ratio", (np.std(df1["price"]) / np.average(df1["price"])) / (np.std(df2["price"]) / np.average(df2["price"])))
    print("30M Rolling STD Ratio", test_rolling_std / eth_rolling_std)

    #return test_rolling_std / eth_rolling_std

df1 = pd.read_csv("data\\usdc-eth-mainnet.csv")
df2 = pd.read_csv("data\\comp-eth-mainnet.csv")
df3 = pd.read_csv("data\\link-eth-mainnet.csv")
df4 = pd.read_csv("data\\uni-eth-mainnet.csv")
df5 = pd.read_csv("data\\wbtc-eth-mainnet.csv")

df1["price"] = df1[" price"]

df2 = pd.merge(df2, df1, on="block number")

df2["price"] = (1 / df2[" price_x"]) * df2[" price_y"]

df3 = pd.merge(df3, df1, on="block number")
df3["price"] = (1 / df3[" price_x"]) * df3[" price_y"]

df4 = pd.merge(df4, df1, on="block number")
df4["price"] = (1 / df4[" price_x"]) * df4[" price_y"]

df5 = pd.merge(df5, df1, on="block number")
df5["price"] = (1 / df5[" price_x"]) * df5[" price_y"]
df5 = df5.loc[df5[" qty1_x"] > 1e-5]
df2.to_csv("comp.csv")

calc_std(df2, df1, "comp")
calc_std(df3, df1, "link")
calc_std(df4, df1, "uni")
calc_std(df5, df1, "wbtc")

