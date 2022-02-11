import numpy as np
from os.path import join as pjoin
import pdb
import bottleneck as bn


def sum_accounts(df, idx_loc):
    print("Summing up root costs")
    df["Total Cost"] = (
        df["Site Labor Cost"] + df["Site Material Cost"] + df["Factory Equipment Cost"]
    )
    idx = df["Subcategories"] != 1
    accounts = df.index[idx].unique()

    headers = [
        "Factory Equipment Cost",
        "Site Material Cost",
        "Site Labor Cost",
        "Total Cost",
        "Site Labor Hours",
    ]
    summed_values = []
    for account in accounts:
        summed_values.append(df[headers].iloc[idx_loc[account]].to_numpy().sum(axis=0))
        # summed_values.append(bn.nansum(df[headers].iloc[idx_loc[account]].to_numpy(), axis=0))
    df.loc[accounts, headers] = summed_values

    "Sum up the total costs"
    df.at["A.1", "Factory Equipment Cost"] = (
        df.at["A.2", "Factory Equipment Cost"] + df.at["A.9", "Factory Equipment Cost"]
    )
    df.at["A.1", "Site Material Cost"] = (
        df.at["A.2", "Site Material Cost"] + df.at["A.9", "Site Material Cost"]
    )
    df.at["A.1", "Site Labor Hours"] = (
        df.at["A.2", "Site Labor Hours"] + df.at["A.9", "Site Labor Hours"]
    )
    df.at["A.1", "Site Labor Cost"] = (
        df.at["A.2", "Site Labor Cost"] + df.at["A.9", "Site Labor Cost"]
    )
    df.at["A.1", "Total Cost"] = df.at["A.2", "Total Cost"] + df.at["A.9", "Total Cost"]

    return df
