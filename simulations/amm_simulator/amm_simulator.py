import os
import pandas as pd
import sys
import math 
import datetime

DEFAULT_FEES_PCT = 0.3/100

def import_scenario(csv_file_path):
    steps = []
    df = pd.read_csv(csv_file_path)
    
    for index, row in df.iterrows():
        if index == 0:
            if row['action'] != 'set_liquidity':
                raise Exception('First action should be set_liquidity, not', df['action'])
            
        steps.append({
            "step": row['step'],
            "time": row['time'],
            "action": row['action'],
            "vETH": float(row['vETH']),
            "vNFT": float(row['vNFT']),
            "userid": row['userid'],
            "oracle_price": row['oracle_price'],
        })
    
    return steps

def run_scenario(steps):
    print('running scenario with', len(steps), 'steps')
    outputs_platform = []
    outputs_users = []
    current_reserve_vETH = 0
    current_reserve_vNFT = 0
    total_collected_fees_vETH = 0

    # check number of differents users that will interract during this simulation
    users = []
    users_data = {}
    for step in steps:
        step_user = step['userid']
        if step_user != 'admin' and step_user not in users:
            users_data[step_user] = {
                "total_diff_vETH": 0,
                "total_diff_vNFT": 0,
                "total_diff_funding_payment_vETH": 0
            }
            users.append(step_user)

    total_diff_vETH = 0
    total_diff_vNFT = 0
    first_trade_time = 0
    funding_payment_start_time = 0
    funding_payment_end_time = 0
    last_hour_prices = {}
    last_price = 0
    last_oracle_price = 0

    # loop through steps, for each steps we will to something based on the 'action' of the step
    # possible actions: add_liquidity or swap
    for step in steps:
        step_name = ''
        action = step['action']
        print('working on step with action:', action)
        step_user = step['userid']
        step_diff_vETH = 0
        step_diff_vNFT = 0
        step_collected_fees_vETH = 0
        fees_pct = 0
        if action == 'set_liquidity':
            current_reserve_vETH = step['vETH']
            current_reserve_vNFT = step['vNFT']
            step_name = f'set liquidity: {step["vETH"]} vETH / {step["vNFT"]} vNFT'
        elif action == 'swap':
            if first_trade_time == 0:
                first_trade_time = step['time']
                print(f'initialized first_trade_time to {first_trade_time}')
                funding_payment_start_time = first_trade_time
                funding_payment_end_time = funding_payment_start_time + 3599
                print(f'new funding payment window: [{funding_payment_start_time} - {funding_payment_end_time}]')
                print(f'new funding payment window: [{datetime.datetime.fromtimestamp(funding_payment_start_time)} - {datetime.datetime.fromtimestamp(funding_payment_end_time)}]')

            # calculate funding payments while step time is > funding_payment_end_time
            # funding payments are calculated every hours so if no trades during few hours it means that 
            # we will calculate the fundping payments multiple times
            while step['time'] > funding_payment_end_time:
                print(f'{datetime.datetime.fromtimestamp(step["time"])} > {datetime.datetime.fromtimestamp(funding_payment_start_time)}, calculating funding payments')
                # print(f'current funding payment window: [{funding_payment_start_time} - {funding_payment_end_time}]')
                print(f'current funding payment window: [{datetime.datetime.fromtimestamp(funding_payment_start_time)} - {datetime.datetime.fromtimestamp(funding_payment_end_time)}]')
                # print('last_hour_prices', last_hour_prices)
                # print('last_price', last_price)
                # print('last_oracle_price', last_oracle_price)

                compute_funding_payments(outputs_platform, current_reserve_vETH, current_reserve_vNFT, total_collected_fees_vETH, users, users_data, step, total_diff_vETH, total_diff_vNFT, funding_payment_start_time, funding_payment_end_time, last_hour_prices, last_price, last_oracle_price, step_diff_vETH, step_diff_vNFT, step_collected_fees_vETH)
                
                # reset last hour prices
                last_hour_prices = {}
                # update funding payment windows
                funding_payment_start_time = funding_payment_end_time + 1
                funding_payment_end_time = funding_payment_start_time + 3599
                # print(f'new funding payment window: [{funding_payment_start_time} - {funding_payment_end_time}]')
                print(f'new funding payment window: [{datetime.datetime.fromtimestamp(funding_payment_start_time)} - {datetime.datetime.fromtimestamp(funding_payment_end_time)}]')


            current_price = current_reserve_vETH / current_reserve_vNFT
            diverging_fees, converging_fees = calc_fees_pct(current_price, step['oracle_price'])
            
            fees_pct = converging_fees
            # IF vETH is not NAN: it's swap vETH => vNFT
            # long position
            if not math.isnan(step['vETH']) and step['vETH'] > 0:
                amount_vETH = step['vETH']
                step_name = f'{step_user} swaps {amount_vETH} vETH to vNFT'
                print('step', step['step'], 'is swap_vETH_to_vNFT')

                # if amm price is already > oracle price and user still buy more vNFT, apply diverging fee
                if current_price > step['oracle_price']:
                    fees_pct = diverging_fees
                
                # calc vETH fees before swapping
                fees_amount_vETH = amount_vETH * fees_pct
                amount_vETH_minus_fees = amount_vETH - fees_amount_vETH
                amount_vNFT = swap_vETH_to_vNFT(current_reserve_vETH, current_reserve_vNFT, amount_vETH_minus_fees)
                print('step', step['step'], 'fees:', fees_amount_vETH, 'vETH')
                print('step', step['step'], step_user, 'received', amount_vNFT, 'vNFT by swapping', amount_vETH_minus_fees, 'vETH')
                current_reserve_vETH += amount_vETH_minus_fees
                current_reserve_vNFT -= amount_vNFT

                step_diff_vETH = amount_vETH_minus_fees
                step_diff_vNFT = -1 * amount_vNFT
                total_diff_vETH += amount_vETH_minus_fees
                total_diff_vNFT -= amount_vNFT
                users_data[step_user]["total_diff_vETH"] -= amount_vETH
                users_data[step_user]["total_diff_vNFT"] += amount_vNFT
                step_collected_fees_vETH = fees_amount_vETH
                total_collected_fees_vETH += fees_amount_vETH

            # IF vNFT is not NAN: it's swap vNFT => vETH
            # short position
            elif not math.isnan(step['vNFT']) and step['vNFT'] > 0:
                amount_vNFT = step['vNFT']
                step_name = f'{step_user} swaps {amount_vNFT} vNFT to vETH'
                print('step', step['step'], 'is swap_vNFT_to_vETH')

                # if amm price is already < oracle price and user still sell more vNFT, apply diverging fee
                if current_price < step['oracle_price']:
                    fees_pct = diverging_fees

                amount_vETH = swap_vNFT_to_vETH(current_reserve_vETH, current_reserve_vNFT, amount_vNFT)
                fees_amount_vETH = fees_pct * amount_vETH
                amount_vETH_minus_fees = amount_vETH - fees_amount_vETH
                print('step', step['step'], 'fees:', fees_amount_vETH, 'vETH')
                print('step', step['step'], step_user, 'received', amount_vETH_minus_fees, 'vETH by swapping', amount_vNFT, 'vNFT')
                current_reserve_vETH -= amount_vETH
                current_reserve_vNFT += amount_vNFT
                
                step_diff_vETH = -1 * amount_vETH
                step_diff_vNFT = amount_vNFT
                total_diff_vETH -= amount_vETH
                total_diff_vNFT += amount_vNFT
                users_data[step_user]["total_diff_vETH"] += amount_vETH_minus_fees
                users_data[step_user]["total_diff_vNFT"] -= amount_vNFT
                step_collected_fees_vETH = fees_amount_vETH
                total_collected_fees_vETH += fees_amount_vETH

            # here the swap is done, reserves are updated, save the price
            
            last_price = current_reserve_vETH / current_reserve_vNFT
            last_oracle_price = step['oracle_price']
            last_hour_prices[step['time']] = {
                'price': last_price,
                'oracle_price':last_oracle_price,
            }

        print('step', step['step'], 'updated reserves to:', current_reserve_vETH, current_reserve_vNFT)
        step_output_platform = {
            "step": step['step'],
            "time": step['time'],
            "step_name": step_name,
            "reserve_vETH": current_reserve_vETH,
            "reserve_vNFT": current_reserve_vNFT,
            "price (vETH/vNFT)": current_reserve_vETH / current_reserve_vNFT,
            "oracle price": step['oracle_price'],
            "applied_fees": fees_pct,
            "step_diff_vETH": step_diff_vETH,
            "step_diff_vNFT": step_diff_vNFT,
            "step_collected_fees_vETH": step_collected_fees_vETH,
            "total_collected_fees_vETH": total_collected_fees_vETH,
            "total_diff_vETH": total_diff_vETH,
            "total_diff_vNFT": total_diff_vNFT,
            "user_id": step_user
        }

        cpt_user_long = 0
        total_long = 0
        cpt_user_short = 0
        total_short = 0
        for user in users:
            # only take value when != 0; value == 0 mean user did not do anything yet so should not be counted
            if users_data[user]['total_diff_vNFT'] < 0:
                cpt_user_short += 1
                total_short += abs(users_data[user]['total_diff_vNFT'])
                
            if users_data[user]['total_diff_vNFT'] > 0:
                cpt_user_long += 1
                total_long += users_data[user]['total_diff_vNFT']

        step_output_platform['cpt_user_long'] = cpt_user_long
        step_output_platform['total_long'] = total_long
        step_output_platform['cpt_user_short'] = cpt_user_short
        step_output_platform['total_short'] = total_short
        outputs_platform.append(step_output_platform)


    # calculate platform PNL
    # let's set the next step as pnl calculation, and for that we need to track all in assets and out assets (since inception)
    # and then to calc pnl we need to reverse the position. meaning if the total is 7 ETH in, and 5 NFT out,
    # then we need to see how much ETH we get for dumping 5 NFT (According to current x,y) and the pnl is the difference from 7. 
    # if the total is 7 nft in and 9 eth out. when we need to find out how much eth is needed to buy 7 nft back. 
    # and the diff is the difference from 9 eth.

    pnl = 0
    # find which asset is out
    # eth out
    if total_diff_vETH < 0:
        print(f'pnl calc: will search amount of vETH needed to buy', total_diff_vNFT, 'vNFT to calc PNL')
        vETH_needed_to_buy_vNFT = find_amount_vETH_to_buy_vNFT(current_reserve_vETH, current_reserve_vNFT, total_diff_vNFT)
        # vNFT_bought = swap_vETH_to_vNFT(current_reserve_vETH, current_reserve_vNFT, vETH_needed_to_buy_vNFT)
        # print(vNFT_bought, total_diff_vNFT)
        print(f'pnl calc: needing {vETH_needed_to_buy_vNFT} vETH to buy back {total_diff_vNFT} vNFT')
        pnl = abs(total_diff_vETH) - vETH_needed_to_buy_vNFT
    # nft out
    elif total_diff_vNFT < 0:
        vNFT_to_dump = -1 * total_diff_vNFT
        print(f'pnl calc: will dump', vNFT_to_dump, 'vNFT to vETH to calc PNL')
        amount_vETH = swap_vNFT_to_vETH(current_reserve_vETH, current_reserve_vNFT, vNFT_to_dump)
        print(f'pnl calc: dumping {vNFT_to_dump} will get back {amount_vETH} vETH')
        pnl = total_diff_vETH - amount_vETH
    else: 
        raise Exception('no asset in negative??')
    
    print(f'pnl calc: {pnl} vETH')

    return { 'outputs_platform': outputs_platform, 'outputs_users': outputs_users, 'pnl': pnl}

def calc_fees_pct(amm_price, oracle_price):
    converging_fee = diverging_fee = DEFAULT_FEES_PCT
    diff = abs(amm_price - oracle_price) / oracle_price


    if diff > 1:
        print(f'diff is {diff*100}%, diverging fees are 100%')
        converging_fee = 0.13
        diverging_fee = 1
        return converging_fee, diverging_fee

    if diff < 2.5/100:
        print(f'diff is {diff*100}%, no need for dynamic fees calc')
        return converging_fee, diverging_fee
    
    max_reached = True

    divergence_bound_low = 10
    if diff >= 2.5/100:
        diverging_fee = 1/100
        converging_fee = 0.2/100
    if diff >= 5/100:
        diverging_fee = 5/100
        converging_fee = 0.15/100
        max_reached = False

    while not max_reached:
        if diff > divergence_bound_low / 100:
            diverging_fee = divergence_bound_low / 100
            converging_fee = 0.13/100 # min is 0.13% for converging fees according to https://nftperp.notion.site/Technical-Stuff-nftperp-v1-f8c37312f0064895877b8b01de72fee2
            divergence_bound_low += 5
        else:
            print(f'max divergence range reached with: {divergence_bound_low-5}%')
            max_reached = True

    return converging_fee, diverging_fee

def compute_funding_payments(outputs_platform, current_reserve_vETH, current_reserve_vNFT, total_collected_fees_vETH, users, users_data, step, total_diff_vETH, total_diff_vNFT, funding_payment_start_time, funding_payment_end_time, last_hour_prices, last_price, last_oracle_price, step_diff_vETH, step_diff_vNFT, step_collected_fees_vETH):
    current_price = current_reserve_vETH / current_reserve_vNFT

                # if no new trade, add the last prices to the last_hour_prices
    if len(last_hour_prices) == 0:
        last_hour_prices[funding_payment_start_time] = {
                        'price': last_price,
                        'oracle_price':last_oracle_price,
                    }

    twaps = calc_twaps(funding_payment_start_time, funding_payment_end_time, last_hour_prices)
    print('twaps', twaps)

    funding_rate = calc_funding_rate(twaps)
    print('funding_rate', funding_rate)
    funding_rate_new = calc_funding_rate_new(funding_rate, users_data)
    print('funding_rate_new', funding_rate_new)
                
    receiving_user_position_size = {}
    total_payments = 0

    step_name = ''
                # When the funding rate is above zero (positive), traders that are long (contract buyers) have to pay the ones that are short (contract sellers).
    if funding_rate > 0:
        step_name = f'funding payment long --> short'
        print('funding_rate is > 0, long buyer will pay short buyers')
        total_short = 0
        for user in users_data:
                        # save position for user who are short
            if users_data[user]['total_diff_vNFT'] < 0:
                receiving_user_position_size[user] = abs(users_data[user]['total_diff_vNFT'])
                total_short += abs(users_data[user]['total_diff_vNFT'])
                            
                        # calculate payment for user who are long
            if users_data[user]['total_diff_vNFT'] > 0:
                user_payment = users_data[user]['total_diff_vNFT'] * funding_rate_new['funding_rate_new_long'] * current_price
                users_data[user]['total_diff_funding_payment_vETH'] -= user_payment
                            # print(f'user {user} will pay {user_payment} vNFT')
                total_payments += user_payment

                    # calc short user ratios and distribute total_payments between every short users
        for user in receiving_user_position_size:
            user_ratio = receiving_user_position_size[user] / total_short
            payment_to_user = total_payments * user_ratio
                        # print(f'giving {payment_to_user} vNFT to {user}')
            users_data[user]['total_diff_funding_payment_vETH'] += payment_to_user

                #  In contrast, a negative funding rate means that short positions pay longs.
    elif funding_rate < 0:
        step_name = f'funding payment short --> long'
        print('funding_rate is < 0, short buyer will pay long buyers')
        total_long = 0
        for user in users_data:
                        # calculate payment for user who are short
            if users_data[user]['total_diff_vNFT'] < 0:
                user_payment = abs(users_data[user]['total_diff_vNFT'] * funding_rate_new['funding_rate_new_short']) * current_price
                users_data[user]['total_diff_funding_payment_vETH'] -= abs(user_payment)
                            # print(f'user {user} will pay {user_payment} vNFT')
                total_payments += user_payment
                            
                        # save position for user who are long
            if users_data[user]['total_diff_vNFT'] > 0:
                receiving_user_position_size[user] = abs(users_data[user]['total_diff_vNFT'])
                total_long += abs(users_data[user]['total_diff_vNFT'])

                    # calc long user ratios and distribute total_payments between every long users
        for user in receiving_user_position_size:
            user_ratio = receiving_user_position_size[user] / total_long
            payment_to_user = total_payments * user_ratio
                        # print(f'giving {payment_to_user} vNFT to {user}')
            users_data[user]['total_diff_funding_payment_vETH'] += payment_to_user
                
    print(f'total payment for [{datetime.datetime.fromtimestamp(funding_payment_start_time)} - {datetime.datetime.fromtimestamp(funding_payment_end_time)}]: {total_payments} vNFT')

    step_output_platform = {
                            "step": 'funding_payments',
                            "time": funding_payment_end_time,
                            "step_name": step_name + f' total payments: {total_payments} vETH',
                            "reserve_vETH": current_reserve_vETH,
                            "reserve_vNFT": current_reserve_vNFT,
                            "price (vETH/vNFT)": current_price,
                            "oracle price": step['oracle_price'],
                            "step_diff_vETH": step_diff_vETH,
                            "step_diff_vNFT": step_diff_vNFT,
                            "step_collected_fees_vETH": step_collected_fees_vETH,
                            "total_collected_fees_vETH": total_collected_fees_vETH,
                            "total_diff_vETH": total_diff_vETH,
                            "total_diff_vNFT": total_diff_vNFT,
                            "user_id": 'admin'
                        }
                
    cpt_user_long = 0
    total_long = 0
    cpt_user_short = 0
    total_short = 0
    for user in users:
                    # only take value when != 0; value == 0 mean user did not do anything yet so should not be counted
        if users_data[user]['total_diff_vNFT'] < 0:
            cpt_user_short += 1
            total_short += abs(users_data[user]['total_diff_vNFT'])
                        
        if users_data[user]['total_diff_vNFT'] > 0:
            cpt_user_long += 1
            total_long += users_data[user]['total_diff_vNFT']

    step_output_platform['cpt_user_long'] = cpt_user_long
    step_output_platform['total_long'] = total_long
    step_output_platform['cpt_user_short'] = cpt_user_short
    step_output_platform['total_short'] = total_short
    outputs_platform.append(step_output_platform)

def calc_funding_rate(twaps):
    return (twaps['twap_amm'] - twaps['twap_oracle']) / 24

def calc_funding_rate_new(funding_rate, users_data):
    long_size = 0
    short_size = 0
    for user in users_data:
        # only take value when != 0; value == 0 mean user did not do anything yet so should not be counted
        if users_data[user]['total_diff_vNFT'] < 0:
            short_size += abs(users_data[user]['total_diff_vNFT'])
            
        if users_data[user]['total_diff_vNFT'] > 0:
            long_size += users_data[user]['total_diff_vNFT']
    funding_rate_new_long = 0
    funding_rate_new_short = 0
    if long_size > 0:
        funding_rate_new_long = (funding_rate * math.pow((short_size * long_size), 0.5)) / long_size
    if short_size > 0:
        funding_rate_new_short = (funding_rate * math.pow((short_size * long_size), 0.5)) / short_size

    return {'funding_rate_new_long': funding_rate_new_long, 'funding_rate_new_short': funding_rate_new_short}

def calc_twaps(funding_payment_start_time, funding_payment_end_time, last_hour_prices):
    last_prices = last_hour_prices[next(iter(last_hour_prices))]
    twap_amm = 0
    twap_oracle = 0
    
    interval_length = funding_payment_end_time - funding_payment_start_time + 1
    time_range = range(interval_length)
    for i in time_range:
        time = funding_payment_start_time + i
        if time in last_hour_prices:
            last_prices = last_hour_prices[time]

        twap_amm += last_prices['price']
        twap_oracle += last_prices['oracle_price']

    twap_amm = twap_amm / interval_length
    twap_oracle = twap_oracle / interval_length

    return {'twap_amm': twap_amm, 'twap_oracle': twap_oracle}

# x * y = k
# (x + Δx) * (y - Δy) = k
# Δy = (y * Δx) / (x + Δx)
def swap_vETH_to_vNFT(reserve_vETH, reserve_vNFT, amount_vETH):
    output_vNFT = (reserve_vNFT * amount_vETH) / (reserve_vETH + amount_vETH)
    return output_vNFT

def swap_vNFT_to_vETH(reserve_vETH, reserve_vNFT, amount_vNFT):
    output_vETH = (reserve_vETH * amount_vNFT) / (reserve_vNFT + amount_vNFT)
    return output_vETH

# Δx = (x * Δy) / (y - Δy)
def find_amount_vETH_to_buy_vNFT(reserve_vETH, reserve_vNFT, amount_vNFT):
    amount_needed_to_buy_vNFT = (reserve_vETH * amount_vNFT) / (reserve_vNFT - amount_vNFT)
    return amount_needed_to_buy_vNFT

if __name__ == '__main__':
    print(sys.argv)
    scenario_path = f'{sys.argv[1]}'
    scenario_name = os.path.basename(scenario_path)
    print('starting amm simulator on', scenario_path, scenario_name)
    steps = import_scenario(scenario_path)
    # print(steps)
    scenario_result = run_scenario(steps)
    df_platform = pd.DataFrame(scenario_result['outputs_platform'])
    output_path = scenario_path.replace(scenario_name, f'output_{scenario_name}')
    df_platform.to_csv(output_path, index=False)
    print('result saved to', output_path)
    # df_users = pd.DataFrame(scenario_result['outputs_users'])
    # df_users.to_csv(scenario_path.replace(scenario_name, f'output_{scenario_name}'), index=False)
    
    # fig, ax1 = plt.subplots()
    # fig.set_size_inches(12.5, 8.5)
    # ax2 = ax1.twinx()
    # ax1.plot(df_platform["block"], df_platform["reserve_vETH"], 'g-')
    # ax2.plot(df_platform["block"], df_platform["total_collected_fees_vETH"], 'b-', label='fees vETH')
    # ax2.plot(df_platform["block"], df_platform["reserve_vNFT"], 'r-')
    # ax1.set_label('Step')
    # ax1.set_ylabel('Reserve vETH', color='g')
    # ax2.set_label('Step')
    # ax2.set_ylabel('Reserve vNFT', color='r')

    # scenario_name = scenario_path.replace('.csv', '')
    # plt.title(scenario_name)
    # plt.legend()
    # plt.savefig(scenario_name + ".jpg")
    # plt.cla()
    # plt.close()
    exit()


