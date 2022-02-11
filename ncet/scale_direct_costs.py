import pandas as pd
from .special_cases import special_cases


def scale_direct_costs(base, scaling_table, plant_characteristics, scalars_dict):
    # --------------------------------------------- Scale the baseline database ------------------------------------#
    dfNP = pd.read_csv(base, index_col="Account")
    dfNP.fillna(0, inplace=True)
    costs = ["Factory Equipment Cost", "Site Material Cost", "Site Labor Cost"]
    hours = ["Site Labor Hours"]
    dfNP["Count per plant"] = 1
    # Scale based on total scaling factors
    for account in scaling_table.index:
        idx = dfNP.index.str.match(account)
        dfNP.loc[idx, (costs + hours)] *= (
            scaling_table.at[account, "Scaling Factor"]
            * scaling_table.at[account, "Multipliers"]
        )
        dfNP.loc[idx, "Count per plant"] = scaling_table.at[account, "Count per plant"]

    # Scale based on costs and hours scaling factors
    accounts = scaling_table.index[scaling_table["Site Material Cost Mult"] != 1]
    for account in accounts:
        for header in costs + hours:
            dfNP.at[account, header] *= scaling_table.at[account, (header + " Mult")]
    dfNP["Total Cost"] = (
        dfNP["Site Material Cost"].values
        + dfNP["Site Labor Cost"].values
        + dfNP["Factory Equipment Cost"].values
    )

    # Adjust for SPC, rebar, e-beam, integral PWR, etc.
    dfNP = special_cases(dfNP, plant_characteristics, scalars_dict)

    # Drop indirect rows
    indirect_rows = dfNP.index.str.match("A.9")
    dfNP = dfNP[~indirect_rows]

    return dfNP
