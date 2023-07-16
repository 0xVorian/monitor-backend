import requests
import json
from datetime import datetime, timedelta
import pandas as pd

def download_candles(symbol, interval, start_time, end_time):
    # Binance API endpoint for klines (candles) data
    url = "https://api.binance.com/api/v3/klines"

    # Parameters for the API request
    params = {
        "symbol": symbol,
        "interval": interval,
        "startTime": start_time,
        "endTime": end_time
    }

    # Send GET request to Binance API
    response = requests.get(url, params=params)

    if response.status_code == 200:
        # Convert response to JSON format
        data = json.loads(response.text)

        # Extract relevant data from the response
        candles = []
        for item in data:
            candle = {
                "open_time": item[0],
                "open": item[1],
                "high": item[2],
                "low": item[3],
                "close": item[4],
                "volume": item[5],
                "close_time": item[6],
                "quote_asset_volume": item[7],
                "number_of_trades": item[8],
                "taker_buy_base_asset_volume": item[9],
                "taker_buy_quote_asset_volume": item[10],
                "ignore": item[11]
            }
            candles.append(candle)

        return candles
    else:
        print("Request failed with status code:", response.status_code)
        return None


# all_candels = []
# d = datetime(2023, 1, 1)
# symbol = "DOGEUSDT"  # Symbol for Bitcoin against USDT
# interval = "1m"  # 1-minute interval
#
# while d < datetime.now():
#     start_time = int(d.timestamp() * 1000)
#     d = d + timedelta(hours=6)
#     end_time = int(d.timestamp() * 1000)
#     candles = download_candles(symbol, interval, start_time, end_time)
#     all_candels += candles
#     print(d, len(all_candels))

# all_candels = pd.DataFrame(all_candels)
# print(len(all_candels))
# all_candels = all_candels.drop_duplicates()
# print(len(all_candels))
# print(all_candels["open"].min())
# print(all_candels["close"].max())
# all_candels.to_csv(symbol + "_for_std.csv")
