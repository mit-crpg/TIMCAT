import pandas as pd
import numpy as np
from os.path import join as pjoin
import pdb


def get_sub_account_iloc(df):
    idx_base = df["Subcategories"] == 1
    accounts = df.index
    idx_dict = {}
    # pdb.set_trace()
    for account in accounts:
        idx_dict[account] = np.argwhere(
            (df.index.str.match(account) & idx_base).to_numpy()
        ).flatten()

    return idx_dict
