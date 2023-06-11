import numpy as np
import matplotlib.pyplot as plt
import pandas as pd


def generate_brownian_motion(std, initial_value, num_steps):
    dt = 1.0 / num_steps
    num_samples = num_steps + 1
    increments = np.random.normal(0, std * np.sqrt(dt), num_samples)
    brownian_motion = [initial_value]
    for i in increments:
        brownian_motion.append(brownian_motion[-1] * (1 + i))
    df = pd.DataFrame()
    df["adjust_price"] = brownian_motion
    start_time = 1583971231305404
    timestamps = [start_time + i * 1000 * 1000 * 60 for i in range(len(df))]
    df["timestamp_x"] = timestamps
    return df

# std = 0.5  # Standard deviation
# initial_value = 100  # Initial value
# num_steps = 60 * 24  # Number of steps
# lasts = []
# for i in range(1000):
#     bm = generate_brownian_motion(std, initial_value, num_steps)
#     lasts.append(bm.iloc[-1]["adjust_price"])
#     plt.plot(bm["adjust_price"])
# plt.title(np.mean(lasts))
# plt.show()
