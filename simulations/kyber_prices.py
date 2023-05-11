import json
import requests
import time
import private_config
import datetime


last_gas_price_fetch = None
current_gas_price = None
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

    # get gas price from rpc
    def get_gas_price(self, chain_id):
        print('getting gas price for chainid', chain_id)
        rpcUrl = ''
        
        callDataJson = json.dumps({
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "eth_gasPrice",
                            "params": []
                        })
        modeFeeHistory = False
        if chain_id == '100': # gnosis
            rpcUrl = 'https://rpc.ankr.com/gnosis'
        elif chain_id == '1313161554': # aurora
            rpcUrl = 'https://mainnet.aurora.dev'
        elif chain_id == '42161': # arbitrum
            # for arbitrum, get the data from the last 10 blocks
            # for better accuracy
            rpcUrl = 'https://rpc.ankr.com/arbitrum'
            modeFeeHistory = True
            callDataJson = json.dumps({
                            "jsonrpc": "2.0",
                            "method": "eth_feeHistory",
                            "params": [
                                9,
                                "latest",
                                [25, 57]
                            ],
                            "id": 1
                        })
        else: 
            raise Exception("get_gast_price: unknown chain id: " + self.chain_id)
    

        feeReponse = requests.post(rpcUrl, data=callDataJson)
        feeReponseData = feeReponse.json()
        if modeFeeHistory:
            # when getting data from fee history, average gas price over last 10 blocks
            fees = feeReponseData['result']['baseFeePerGas']
            avgFee = 0
            for fee in fees:
                feeBase10 = int(fee, 16)
                print('fee', fee, feeBase10)
                avgFee += feeBase10
            
            avgFee = avgFee / len(fees)
            return int(avgFee)
        else:
            return int(feeReponseData['result'], 16)
    
    def get_price(self, base, quote, volume_in_base):
        fnName = 'getPrice['+ base + '/' + quote + ']:'
        print(fnName, 'start getting price for amount:', volume_in_base)
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
        url_to_send = ""
        global current_gas_price
        global last_gas_price_fetch

        if private_config.use_one_inch_pathfinder: 
            now = datetime.datetime.now()
            print(fnName, 'using 1inch pathfinder')
            if last_gas_price_fetch == None or (now - last_gas_price_fetch).total_seconds() > 120 : # fetch gas price every 2 minutes
                current_gas_price = self.get_gas_price(self.chain_id)
                last_gas_price_fetch = datetime.datetime.now()
                print(fnName, 'updated gas price to', current_gas_price)

            url_to_send = 'https://pathfinder.1inch.io/v1.4/chain/'+str(self.chain_id)+'/router/v5/quotes?fromTokenAddress='+ str(token_in) + \
                            '&toTokenAddress='+str(token_out)+'&amount='+str(int(amount_in))+'&preset=maxReturnResult&gasPrice='+ str(current_gas_price)
        else:
            url_to_send = "https://api.1inch.io/v4.0/" + str(self.chain_id) + "/quote?" \
                "fromTokenAddress=" + str(token_in) + "&" \
                "toTokenAddress=" + str(token_out) + "&" \
                "amount=" + str(int(amount_in))
        time.sleep(1)
        time_to_sleep = 1
        while True:
            try:
                response = requests.get(url_to_send, headers= {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:77.0) Gecko/20100101 Firefox/77.0'})
                data = response.json()
                response_amount_in = int(amount_in) / 10 ** self.decimals[self.inv_names[base]]
                if base == "VST":
                    response_amount_in = int(amount_in) / 10 ** 6

                response_amount_out = 0
                if private_config.use_one_inch_pathfinder: 
                    response_amount_out = int(data['bestResult']['toTokenAmount']) / 10 ** self.decimals[self.inv_names[quote]]
                else:
                    response_amount_out = int(data["toTokenAmount"]) / 10 ** self.decimals[self.inv_names[quote]]

                print(fnName, 'url used', url_to_send)
                print(fnName, 'response amount', response_amount_out)

                price_in_base = response_amount_in / response_amount_out
                print(fnName, 'price_in_base', price_in_base)
                return price_in_base
            except Exception as e:
                print(e)
                print(response.text)
                error_data = response.json()
                print(error_data)
                if error_data['err'] == 'all quoteResults failed':
                    # if no route found from the API, return a very high number
                    print('all quoteResults failed returning -1')
                    return -1
                time.sleep(time_to_sleep)
                time_to_sleep += 3


