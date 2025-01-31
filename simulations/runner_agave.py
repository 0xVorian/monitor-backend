import json
import time
import os
import glob
import numpy as np
import pandas as pd
import compound_parser
import base_runner
import copy
import kyber_prices
import utils
import sys
import private_config
import shutil
import datetime

def create_dex_information():
    print("create_dex_information")
    data = {"json_time": time.time()}
    for market in assets_to_simulate:
        data[market] = {"count": 0, "total": 0, "avg": 0, "med": 0,
                        "top_10": 0,
                        "top_5": 0, "top_1": 0, "users": []}

    fp = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "dex_liquidity.json", "w")
    json.dump(data, fp)


def create_simulation_config(SITE_ID, c, ETH_PRICE, assets_to_simulate, assets_aliases, liquidation_incentive,
                             inv_names):
    def roundUp(x):
        x = max(x, 1_000_000)
        x = int((x + 1e6 - 1) / 1e6) * 1e6
        if x == 0:
            print(x)
            exit()
        return x

    print("create_simulation_config")
    f1 = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "usd_volume_for_slippage.json")
    jj1 = json.load(f1)

    f2 = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "assets_std_ratio.json")
    jj2 = json.load(f2)
    data = {"json_time": time.time()}
    now_time = time.time()
    for base_to_simulation in assets_to_simulate:
        for quote_to_simulation in jj1[base_to_simulation]:
            if assets_aliases[base_to_simulation] != assets_aliases[quote_to_simulation]:
                key = base_to_simulation + "-" + quote_to_simulation
                new_c = copy.deepcopy(c)
                if assets_aliases[base_to_simulation] in jj2 and \
                        assets_aliases[quote_to_simulation] in jj2[assets_aliases[base_to_simulation]]:
                    std_ratio = jj2[assets_aliases[base_to_simulation]][assets_aliases[quote_to_simulation]]
                else:
                    std_ratio = jj2[assets_aliases[quote_to_simulation]][assets_aliases[base_to_simulation]]

                slippage = jj1[base_to_simulation][quote_to_simulation]["volume"] / ETH_PRICE
                li = float(liquidation_incentive[inv_names[base_to_simulation]])
                li = li if li < 1 else li - 1
                new_c["liquidation_incentives"] = [li]
                new_c["series_std_ratio"] = std_ratio
                new_c["volume_for_slippage_10_percentss"] = [slippage]
                new_c["json_time"] = now_time
                # if "DAI" in base_to_simulation or "DAI" in quote_to_simulation:
                #     new_c["volume_for_slippage_10_percents_price_drop"] = 50_000 / ETH_PRICE
                #     new_c["price_recovery_times"] = [2]
                # else:
                #     new_c["price_recovery_times"] = [0]

                max_collateral = collateral_caps[inv_names[base_to_simulation]]
                max_debt = borrow_caps[inv_names[quote_to_simulation]]

                cc = [0.25 * max_collateral, 0.5 * max_collateral, 0.75 * max_collateral, 1 * max_collateral,
                      1.25 * max_collateral, 1.5 * max_collateral, 1.75 * max_collateral, 2 * max_collateral]

                dd = [0.25 * max_debt, 0.5 * max_debt, 0.75 * max_debt, 1 * max_debt, 1.25 * max_debt,
                      1.5 * max_debt, 1.75 * max_debt, 2 * max_debt]

                for c1 in cc:
                    c1 = roundUp(c1)
                    c1 = c1 / ETH_PRICE
                    c1 = int(c1)
                    if c1 not in new_c["collaterals"]:
                        new_c["collaterals"].append(c1)
                    for d1 in dd:
                        d1 = roundUp(d1)
                        d1 = d1 / ETH_PRICE
                        d1 = int(d1)
                        if d1 < c1 and d1 not in new_c["collaterals"]:
                            new_c["collaterals"].append(d1)

                current_collateral = 0
                current_debt = 0

                for index, row in users_data.iterrows():
                    current_debt += float(row["DEBT_" + base_to_simulation])
                    current_collateral += float(row["COLLATERAL_" + base_to_simulation])

                # new_c["collaterals"].append(roundUp(current_debt) / ETH_PRICE)
                # new_c["collaterals"].append(roundUp(current_collateral) / ETH_PRICE)
                new_c["collaterals"] = [100_000 / ETH_PRICE, 200_000 / ETH_PRICE, 300_000 / ETH_PRICE,
                                        400_000 / ETH_PRICE, 500_000 / ETH_PRICE,
                                        600_000 / ETH_PRICE, 700_000 / ETH_PRICE, 800_000 / ETH_PRICE,
                                        900_000 / ETH_PRICE, 1_000_000 / ETH_PRICE,
                                        1_500_000 / ETH_PRICE, 2_000_000 / ETH_PRICE, 2_500_000 / ETH_PRICE,
                                        3_000_000 / ETH_PRICE,
                                        4_000_000 / ETH_PRICE, 5_000_000 / ETH_PRICE, 5_000_000 / ETH_PRICE,
                                        6_000_000 / ETH_PRICE, 7_000_000 / ETH_PRICE, 8_000_000 / ETH_PRICE,
                                        9_000_000 / ETH_PRICE, 10_000_000 / ETH_PRICE, 15_000_000 / ETH_PRICE]
                if 0 in new_c["collaterals"]:
                    print(new_c)
                new_c["current_debt"] = current_debt / ETH_PRICE
                data[key] = new_c

    fp = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "simulation_configs.json", "w")
    json.dump(data, fp)

def fix_wstETH_price():
    oracle_file = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "oracles.json")
    oracle_data = json.load(oracle_file)
    oracle_file.close()

    print('updating wstETH price, from:', oracle_data['wstETH']['dex_price'],'to:', oracle_data['wstETH']['oracle'])
    oracle_data['wstETH']['dex_price'] = oracle_data['wstETH']['oracle']
    
    fp = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "oracles.json", "w")
    json.dump(oracle_data, fp)
    fp.close()

def fix_usd_volume_for_slippage():
    balancer_file = open(balancer_volume_json_file)
    balancer_data = json.load(balancer_file)

    current_file = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "usd_volume_for_slippage.json")
    current_data = json.load(current_file)

    # overwrite current data with balancer data
    for base_symbol in balancer_data: 
        if base_symbol == 'json_time': continue
        if base_symbol == 'sDAI': continue
        for quote_symbol in balancer_data[base_symbol]:
            if quote_symbol == 'sDAI': continue
            balancer_liquidity = float(balancer_data[base_symbol][quote_symbol]["volume"])
            old_liquidity = float(current_data[base_symbol][quote_symbol]["volume"])
            if balancer_liquidity > old_liquidity:
                print("overwritting volume for", base_symbol, quote_symbol, current_data[base_symbol][quote_symbol], "with", balancer_data[base_symbol][quote_symbol])
                current_data[base_symbol][quote_symbol] = balancer_data[base_symbol][quote_symbol]
            else:
                print("keeping 1inch volume for", base_symbol, quote_symbol, current_data[base_symbol][quote_symbol], "because balancer volume is lower:", balancer_data[base_symbol][quote_symbol])
                
    
    # # for every wstETH pairs (whether base or quote), replace value by ETH value
    # # e.g:
    # # - wstETH/USDC => ETH/USDC 
    # # - GNO/wstETH => GNO/ETH
    # for base_symbol in current_data: 
    #     if base_symbol == 'json_time': continue
    #     for quote_symbol in current_data[base_symbol]:
    #         if base_symbol == 'wstETH' and quote_symbol == 'WETH':
    #             continue
    #         if quote_symbol == 'wstETH' and base_symbol == 'WETH':
    #             continue

    #         if base_symbol == 'wstETH' or quote_symbol == 'wstETH':
    #             new_base = base_symbol
    #             new_quote = quote_symbol
    #             if new_base == 'wstETH':
    #                 new_base = 'WETH'
    #             if new_quote == 'wstETH':
    #                 new_quote = 'WETH'
    #             print("overwritting volume for", base_symbol, quote_symbol, 'with new symbols:', new_base, new_quote)
    #             print('old value:', current_data[base_symbol][quote_symbol], "new value:", current_data[new_base][new_quote])
    #             current_data[base_symbol][quote_symbol] = current_data[new_base][new_quote]

    # for every wxDAI pair (whether base or quote), add sDAI liquidity with the same amount
    current_data['sDAI'] = {}
    current_data['sDAI']['WXDAI'] = {}
    current_data['sDAI']['WXDAI']['volume'] = 100000000
    current_data['sDAI']['WXDAI']['llc'] = 1
    current_data['WXDAI']['sDAI'] = {}
    current_data['WXDAI']['sDAI']['volume'] = 100000000
    current_data['WXDAI']['sDAI']['llc'] = 1

    for base_symbol in list(current_data): 
        if base_symbol == 'json_time': continue
        if base_symbol == 'sDAI': continue

        for quote_symbol in list(current_data[base_symbol]):
            if quote_symbol == 'sDAI': continue
            if base_symbol == 'WXDAI':
                print('copying on', base_symbol, '/', quote_symbol, 'to sDAI/', quote_symbol)
                current_data['sDAI'][quote_symbol] = current_data[base_symbol][quote_symbol]
            if quote_symbol == 'WXDAI':
                print('copying on', base_symbol, '/', quote_symbol, 'to', base_symbol, '/sDAI')
                current_data[base_symbol]['sDAI'] = current_data[base_symbol][quote_symbol]


    balancer_file.close()
    current_file.close()
    fp = open("webserver" + os.path.sep + SITE_ID + os.path.sep + "usd_volume_for_slippage.json", "w")
    json.dump(current_data, fp)
    fp.close()

def get_supply_borrow():
    supply_borrow_file = open(supply_borrow_json_file)
    supply_borrow = json.load(supply_borrow_file)
    supply_borrow_file.close()
    return supply_borrow

def get_alert_params():
    alert_params = []
    
    # RISK DAO CHANNEL: send all alerts to risk_dao_channel
    alert_params.append({
        "is_default": True, # is default mean it's the risk dao general channel where all msg are sent
        "tg_bot_id": private_config.risk_dao_bot,
        "tg_channel_id": private_config.risk_dao_channel,
        "oracle_threshold": 3, # oracle threshold is always in absolute
        "slippage_threshold": 10, # liquidity threshold before sending alert
        "only_negative": False, # only send liquidity alert if the new volume < old volume
        "supply_borrow_threshold": 10, # supply/borrow threshold before sending alert
    })

    # REAL AGAVE ALERT CHANNEL: send only oracle > 3% and liquidity alerts where <-50%
    alert_params.append({
        "is_default": False, # is default mean it's the risk dao general channel where all msg are sent
        "tg_bot_id": private_config.risk_dao_bot,
        "tg_channel_id": private_config.agave_channel,
        "oracle_threshold": 3, # oracle threshold is always in absolute
        "slippage_threshold": 50, # liquidity threshold before sending alert
        "only_negative": True, # only send liquidity alert if the new volume < old volume
        "supply_borrow_threshold": 10, # supply/borrow threshold before sending alert
    })
    
    # PRIVATE AGAVE CHANNEL: alerts when liquidity <-10%
    alert_params.append({
        "is_default": False, # is default mean it's the risk dao general channel where all msg are sent
        "tg_bot_id": private_config.risk_dao_bot,
        "tg_channel_id": private_config.agave_channel_internal,
        "oracle_threshold": 3, # oracle threshold is always in absolute
        "slippage_threshold": 10, # liquidity threshold before sending alert
        "only_negative": True, # only send liquidity alert if the new volume < old volume
        "supply_borrow_threshold": 10, # supply/borrow threshold before sending alert
    })

    return alert_params

lending_platform_json_file = ".." + os.path.sep + "Agave" + os.path.sep + "data.json"
oracle_json_file = ".." + os.path.sep + "Agave" + os.path.sep + "oracle.json"
balancer_volume_json_file = ".." + os.path.sep + "Agave" + os.path.sep + "balancer_volume_for_slippage.json"
supply_borrow_json_file = ".." + os.path.sep + "Agave" + os.path.sep + "agave_supply_borrow.json"

assets_to_simulate = ['USDC', 'WXDAI', 'LINK', 'GNO', 'WBTC', 'WETH', 'FOX', "USDT", "EURe", "wstETH", "sDAI"]
assets_aliases = {'USDC': 'USDC', 'WXDAI': 'DAI', 'LINK': 'LINK', 'GNO': 'GNO', 'WBTC': 'BTC', 'WETH': 'ETH',
                  'FOX': 'FOX', "USDT":"USDC", "EURe":"EUR", "wstETH": "wstETH", "sDAI": "DAI"}

ETH_PRICE = 1600
print_time_series = False
total_jobs = 8
platform_prefix = ""
SITE_ID = "4"
chain_id = "og"
l_factors = [0.25, 0.5, 1, 1.5, 2]

alert_mode = False
send_alerts = False
old_alerts = {}
c = {
    "series_std_ratio": 0,
    'volume_for_slippage_10_percentss': [],
    'trade_every': 1800,
    "collaterals": [],
    'liquidation_incentives': [],
    "stability_pool_initial_balances": [0],
    'share_institutionals': [0],
    'recovery_halflife_retails': [0],
    "price_recovery_times": [0],
    "l_factors": [0.25, 0.5, 1, 1.5, 2]
}

if __name__ == '__main__':
    fast_mode = len(sys.argv) > 1
    print("FAST MODE", fast_mode)
    alert_mode = len(sys.argv) > 2
    print("ALERT MODE", alert_mode)
    send_alerts = len(sys.argv) > 3
    print("SEND ALERTS", send_alerts)

    while True:
        startDate = round(datetime.datetime.now().timestamp())
        if alert_mode:
            # if in alert mode, record monitoring data
            utils.record_monitoring_data({
                "name": 'Agave',
                "status": "running",
                "lastStart": startDate,
                'runEvery': 30 * 60
            })

        if os.path.sep in SITE_ID:
            SITE_ID = SITE_ID.split(os.path.sep)[0]
        SITE_ID = utils.get_site_id(SITE_ID)
        #SITE_ID = "4\\2023-3-21-8-40"
        file = open(lending_platform_json_file)
        data = json.load(file)

        if os.path.exists(oracle_json_file):
            file = open(oracle_json_file)
            oracle = json.load(file)
            data["prices"] = copy.deepcopy(oracle["prices"])
            print("FAST ORACLE")

        cp_parser = compound_parser.CompoundParser()
        users_data, assets_liquidation_data, \
        last_update_time, names, inv_names, decimals, collateral_factors, borrow_caps, collateral_caps, prices, \
        underlying, inv_underlying, liquidation_incentive, orig_user_data, totalAssetCollateral, totalAssetBorrow = cp_parser.parse(
            data)

        users_data["nl_user_collateral"] = 0
        users_data["nl_user_debt"] = 0

        for base_to_simulation in assets_to_simulate:
            users_data["NL_COLLATERAL_" + base_to_simulation] = users_data["NO_CF_COLLATERAL_" + base_to_simulation]
            users_data["NL_DEBT_" + base_to_simulation] = users_data["DEBT_" + base_to_simulation]
            users_data["MIN_" + base_to_simulation] = users_data[
                ["NO_CF_COLLATERAL_" + base_to_simulation, "DEBT_" + base_to_simulation]].min(axis=1)

            users_data["NL_COLLATERAL_" + base_to_simulation] -= users_data["MIN_" + base_to_simulation]
            users_data["NL_DEBT_" + base_to_simulation] -= users_data["MIN_" + base_to_simulation]
            users_data["nl_user_collateral"] += users_data["NL_COLLATERAL_" + base_to_simulation]
            users_data["nl_user_debt"] += users_data["NL_DEBT_" + base_to_simulation]

        kp = kyber_prices.KyberPrices("100", inv_names, underlying, decimals)

        base_runner.create_overview(SITE_ID, users_data, totalAssetCollateral, totalAssetBorrow)
        base_runner.create_lending_platform_current_information(SITE_ID, last_update_time, names, inv_names, decimals,
                                                                prices, collateral_factors, collateral_caps,
                                                                borrow_caps,
                                                                underlying)
        base_runner.create_account_information(SITE_ID, users_data, totalAssetCollateral, totalAssetBorrow, inv_names,
                                            assets_liquidation_data)
        base_runner.create_oracle_information(SITE_ID, prices, chain_id, names, assets_aliases, kp.get_price)
        create_dex_information()
        base_runner.create_whale_accounts_information(SITE_ID, users_data, assets_to_simulate)
        base_runner.create_open_liquidations_information(SITE_ID, users_data, assets_to_simulate)
        
        ignore_list=[]
        if alert_mode:
            # build ignore list for each tokens with <= $10 collateral caps
            for tokenAddr in collateral_caps: 
                tokenName = names[tokenAddr]
                tokenCap = collateral_caps[tokenAddr]
                if tokenCap <= 10:
                    print('Adding', tokenName, 'to the ignore list because collateralCap:', tokenCap)
                    ignore_list.append(tokenName)
            
            # we also add sDAI to the ignore list
            ignore_list.append('sDAI')
            # we also add wstETH to the ignore list
            ignore_list.append('wstETH')

            # for every tokens in the ignore list, delete entry in inv_names before calling 'create_usd_volumes_for_slippage'
            # it will remove them from the data fetch and will greatly speed up the alert process
            # the slippage data for these tokens will not be needed anyway as we will ignore them
            # this is only done when in alert mode
            for name in ignore_list:
                del inv_names[name]
            
            print('new value for inv_names', inv_names)

        # remove sDAI from inv_names to prevent fetching liquidity from 1inch as we will get the liquidity from WXDAI pair
        if 'sDAI' in inv_names:
            del inv_names['sDAI']
        base_runner.create_usd_volumes_for_slippage(SITE_ID, chain_id, inv_names, liquidation_incentive, kp.get_price, False)        
        # re add after
        inv_names['sDAI'] = '0xaf204776c7245bF4147c2612BF6e5972Ee483701'

        fix_usd_volume_for_slippage()
        # fix_wstETH_price()
        if alert_mode:
            d1 = utils.get_file_time(oracle_json_file)
            d1 = min(last_update_time, d1)

            current_supply_borrow = None # 17/08/2023: disable supply/borrow alerts get_supply_borrow()
            alert_params = get_alert_params()
            print('alert_params', alert_params)
            old_alerts = utils.compare_to_prod_and_send_alerts(old_alerts, d1, "agave", "4", SITE_ID, alert_params, send_alerts, ignore_list= ignore_list, current_supply_borrow= current_supply_borrow)
            print('old_alerts', old_alerts)
            endDate =  round(datetime.datetime.now().timestamp())
            utils.record_monitoring_data({
                "name": 'Agave',
                "status": "success",
                "lastEnd": endDate,
                "lastDuration": endDate - startDate,
            })
            print("Alert Mode.Sleeping For 30 Minutes")
            time.sleep(30 * 60)
        else:
            base_runner.create_assets_std_ratio_information(SITE_ID,
                                                            ['DAI', 'USDC', 'LINK', 'GNO', 'BTC', 'ETH', 'FOX', 'EUR', 'wstETH'],
                                                            [("04", "2022"), ("05", "2022"), ("06", "2022")])
            create_simulation_config(SITE_ID, c, ETH_PRICE, assets_to_simulate, assets_aliases, liquidation_incentive,
                                    inv_names)
            base_runner.create_simulation_results(SITE_ID, ETH_PRICE, total_jobs, collateral_factors, inv_names,
                                                print_time_series, fast_mode)
            base_runner.create_risk_params(SITE_ID, ETH_PRICE, total_jobs, l_factors, print_time_series)
            base_runner.create_current_simulation_risk(SITE_ID, ETH_PRICE, users_data, assets_to_simulate,
                                                    assets_aliases,
                                                    collateral_factors, inv_names, liquidation_incentive, total_jobs,
                                                    False)

            n = datetime.datetime.now().timestamp()
            d1 = utils.get_file_time(oracle_json_file)
            d0 = min(last_update_time, d1)
            utils.update_time_stamps(SITE_ID, d0)
            utils.publish_results(SITE_ID)
            #utils.compare_to_prod_and_send_alerts(old_alerts, d1, "agave", "4", SITE_ID, "", 10, False)
            # if d1 < float('inf'):
            #     print("oracle_json_file", round((n - d1) / 60), "Minutes")
            # if last_update_time < float('inf'):
            #     print("last_update_time", round((n - last_update_time) / 60), "Minutes")
            print("Simulation Ended")
            exit()
