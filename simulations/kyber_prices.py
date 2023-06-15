import json
import requests
import time


class KyberPrices:
    def __init__(self, network, inv_names, underlying, decimals):
        self.url = "https://aggregator-api.kyberswap.com/" + network + "/route/encode?" \
                                                                       "tokenIn=TOKEN_IN&" \
                                                                       "tokenOut=TOKEN_OUT&" \
                                                                       "amountIn=AMOUNT_IN&" \
                                                                       "saveGas=0&" \
                                                                       "gasInclude=0&" \
                                                                       "gasPrice=70000000&" \
                                                                       "slippageTolerance=50&" \
                                                                       "deadline=DEAD_LINE&" \
                                                                       "to=0x0000000000000000000000000000000000000000&" \
                                                                       "chargeFeeBy=&" \
                                                                       "feeReceiver=&" \
                                                                       "isInBps=&feeAmount=&" \
                                                                       "clientData={'source':'kyberswap'}"

        self.underlying = underlying
        self.decimals = decimals
        self.inv_names = inv_names
        self.chain_id = network

    def get_price(self, base, quote, volume_in_base):
        token_in = self.underlying[self.inv_names[base]]
        token_out = self.underlying[self.inv_names[quote]]
        amount_in = volume_in_base * 10 ** self.decimals[self.inv_names[base]]
        if base == "VST":
            token_in = "0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8"
            amount_in = volume_in_base * 10 ** 6

        # url_to_send = self.url.replace("DEAD_LINE", str(time.time() + 1000))
        # url_to_send = url_to_send.replace("TOKEN_IN", str(token_in))
        # url_to_send = url_to_send.replace("TOKEN_OUT", str(token_out))
        # url_to_send = url_to_send.replace("AMOUNT_IN", str(int(amount_in)))
        url_to_send = "https://api.1inch.io/v4.0/" + str(self.chain_id) + "/quote?" \
                "fromTokenAddress=" + str(token_in) + "&" \
                "toTokenAddress=" + str(token_out) + "&" \
                "amount=" + str(int(amount_in))
        time.sleep(1)
        time_to_sleep = 1
        while True:
            try:
                response = requests.get(url_to_send)
                data = response.json()
                response_amount_in = int(amount_in) / 10 ** self.decimals[self.inv_names[base]]
                if base == "VST":
                    response_amount_in = int(amount_in) / 10 ** 6

                response_amount_out = int(data["toTokenAmount"]) / 10 ** self.decimals[self.inv_names[quote]]
                price_in_base = response_amount_in / response_amount_out
                return price_in_base
            except Exception as e:
                print(e)
                print(response.json)
                print(response.text)
                time.sleep(time_to_sleep)
                time_to_sleep += 3


