# vAMM Simulator: how to use

The vAMM simulator uses a csv scenario as inputs. The csv list all actions (trades/repegs/others) that will happen sequentially in the vAMM.

## Install required python dependencies

`pip install -r requirements.txt`

## Run the scenario

`python amm_simulator.py '/path/to/scenario.csv'`

At the end, the simulator will output another csv, it will be placed in the same directory as the input scenario

Example: with input scenario here `'/home/bob/scenario.csv'`, the output csv will be placed here `'/home/bob/output_scenario.csv'`

## Scenario

A scenario describes all the actions that will happen in the amm

### Example

| t | action        | vETH | vNFT  | fees | userid |
| - | ------------- | ---- | ----- | ---- | ------ |
| 1 | set_liquidity | 10   | 2000  | 0.01 | admin  |
| 2 | swap          | 1    |       | 0.01 | user1  |
| 3 | swap          | 5    |       | 0.01 | user2  |
| 4 | swap          | 1    |       | 0.01 | user1  |
| 5 | swap          | 1    |       | 0.01 | user3  |
| 6 | set_liquidity | 100  | 20000 | 0.01 | admin  |
| 7 | swap          |      | 200   | 0.01 | user2  |


### Columns definition
| label  | description                                                                                                                                   |
| ------ | --------------------------------------------------------------------------------------------------------------------------------------------- |
| t      | The time where the action took place, can be anything (just a number, a blocknumber…)                                                         |
| action | The performed action: set_liquidity or swap. The first action must always be set_liquidity as it sets the base liquidity of the AMM           |
| vETH   | Number of vETH, for set_liquidity action: it means the amount of vETH in the reserve. For swap it means how much vETH will be sold to the AMM |
| vNFT   | Same as vETH but for the other side of the AMM                                                                                                |
| fees   | The trade fees if any                                                                                                                         |
| userid | The user, admin for set_liquidity, userid for a swap, used to track positions                                                                 |


## Output

The output lists, for every steps in the scenario, what happened in the AMM

### Example output

| t | step_name                                | reserve_vETH       | reserve_vNFT       | price (vETH/vNFT)    | step_diff_vETH       | step_diff_vNFT       | step_collected_fees_vETH | total_collected_fees_vETH | total_diff_vETH   | total_diff_vNFT      | trader_id | cpt_user_long | total_long         | cpt_user_short | total_short |
| ----- | ---------------------------------------- | ------------------ | ------------------ | -------------------- | -------------------- | -------------------- | ------------------------ | ------------------------- | ----------------- | -------------------- | --------- | ------------- | ------------------ | -------------- | ----------- |
| 1     | set liquidity: 10.0 vETH / 2000.0 vNFT   | 10.0               | 2000.0             | 0.005                | 0.0                  | 0.0                  | 0.0                      | 0.0                       | 0.0               | 0.0                  | admin     | 0             | 0.0                | 0              | 0           |
| 2     | user1 swaps 1.0 vETH to vNFT             | 10.99              | 1819.8362147406733 | 0.006039005          | 0.99                 | \-180.16378525932666 | 0.01                     | 0.01                      | 0.99              | \-180.16378525932666 | user1     | 1             | 180.16378525932666 | 0              | 0           |
| 3     | user2 swaps 5.0 vETH to vNFT             | 15.940000000000001 | 1254.7051442910915 | 0.012704180000000002 | 4.95                 | \-565.1310704495817  | 0.05                     | 0.060000000000000005      | 5.94              | \-745.2948557089084  | user2     | 2             | 745.2948557089084  | 0              | 0           |
| 4     | user1 swaps 1.0 vETH to vNFT             | 16.93              | 1181.3349084465444 | 0.014331245000000001 | 0.99                 | \-73.370235844547    | 0.01                     | 0.07                      | 6.930000000000001 | \-818.6650915534553  | user1     | 2             | 818.6650915534553  | 0              | 0           |
| 5     | user3 swaps 1.0 vETH to vNFT             | 17.919999999999998 | 1116.0714285714284 | 0.01605632           | 0.99                 | \-65.26347987511602  | 0.01                     | 0.08                      | 7.920000000000001 | \-883.9285714285713  | user3     | 3             | 883.9285714285713  | 0              | 0           |
| 6     | set liquidity: 100.0 vETH / 20000.0 vNFT | 100.0              | 20000.0            | 0.005                | 0.0                  | 0.0                  | 0.0                      | 0.08                      | 7.920000000000001 | \-883.9285714285713  | admin     | 3             | 883.9285714285713  | 0              | 0           |
| 7     | user2 swaps 200.0 vNFT to vETH           | 99.00990099009901  | 20200.0            | 0.004901480247034604 | \-0.9900990099009901 | 200.0                | 0.009900990099009901     | 0.0899009900990099        | 6.929900990099011 | \-683.9285714285713  | user2     | 3             | 683.9285714285713  | 0              | 0           |


### Columns definition
| label                     | description                                               |
| ------------------------- | --------------------------------------------------------- |
| t                         | the time where the action happened                        |
| step_name                 | A label for the step, describes the human readable action |
| reserve_vETH              | The amount in the vETH reserve AFTER the action           |
| reserve_vNFT              | The amount in the vNFT reserve AFTER the action           |
| price (vETH/vNFT)         | Price                                                     |
| step_diff_vETH            | Difference between action t-1 and t for vETH              |
| step_diff_vNFT            | Difference between action t-1 and t for NFT               |
| step_collected_fees_vETH  | Amount of vETH collected as fee for this step             |
| total_collected_fees_vETH | Total of vETH collected since the beginning               |
| total_diff_vETH           | Total in/out for vETH                                     |
| total_diff_vNFT           | Total in/out for vNFT                                     |
| user_id                 | The trader that made the swap                             |
| cpt_user_long             | Amount of users in long position                          |
| total_long                | Amount of vNFT in long position                           |
| cpt_user_short            | Amount of users in short position                         |
| total_short               | Amount of vNFT in short position                          |