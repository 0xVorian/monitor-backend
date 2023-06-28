import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import math

def generate_brownian_motion(std, initial_value, num_steps, seed):
    np.random.seed(seed)
    dt = 1.0 / num_steps
    num_samples = num_steps + 1
    increments = np.random.normal(0, np.log(std) * np.sqrt(dt), num_samples)
    #print(np.std(increments) * np.sqrt(num_steps))
    brownian_motion = [initial_value]
    for i in increments:
        brownian_motion.append(float(brownian_motion[-1] * math.exp(i)))
    df = pd.DataFrame()
    df["adjust_price"] = brownian_motion
    start_time = 1583971231305404
    timestamps = [start_time + i * 1000 * 1000 * 60 for i in range(len(df))]
    df["timestamp_x"] = timestamps
    return df

# std = 2  # Standard deviation
# initial_value = 100  # Initial value
# num_steps = 60 * 24  # Number of steps
# lasts = []
# for i in range(5000):
#     bm = generate_brownian_motion(std, initial_value, num_steps, 2000 + i)
#     lasts.append(bm.iloc[-1]["adjust_price"])
#     plt.plot(np.log(bm["adjust_price"]))
# over300 = 0
# for x in lasts:
#     if x > 300:
#         over300 += 1
# plt.title(str(np.median(lasts)) + " " + str(np.std(lasts)) + " " + str(over300))
# plt.show()
