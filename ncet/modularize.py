import pandas as pd
from os.path import join as pjoin


def modularize(path, fname, dfNewPlant, orders, scalars_dict):

    print("Modularizing accounts")
    modules = pd.read_excel(
        pjoin(path, fname), header=0, sheet_name="Modules", index_col="Account"
    )
    accounts = modules.index
    fact_costs = (
        modules["Factory Cost (2018 USD)"].values * scalars_dict["Factory cost mult"]
    )
    offsite_work = (
        modules["Percent Offsite Work"].values * scalars_dict["Offsite work mult"]
    )
    offsite_efficiency = (
        modules["Offsite Efficiency"].values * scalars_dict["Offsite efficiency mult"]
    )

    idx_modules = dfNewPlant.index.str.match(
        "gggg"
    )  # something I know will be all False
    labor_savings = 0
    for i, account in enumerate(accounts):
        print("Modularizing account " + account)
        idx = dfNewPlant.index.str.match(account)
        idx_spec = dfNewPlant.index == (account)
        dfNewPlant.loc[idx, "Factory Equipment Cost"] += dfNewPlant.loc[
            idx, "Site Material Cost"
        ]  # material costs are brought to the factory
        dfNewPlant.loc[idx, "Factory Equipment Cost"] += (
            offsite_work[i]
            / offsite_efficiency[i]
            * dfNewPlant.loc[idx, "Site Labor Cost"]
        )  # 1/2 the labor is done in the factory at 2x the productivity
        dfNewPlant.loc[idx, "Site Labor Cost"] *= (
            1 - offsite_work[i]
        )  # half of the labor is done onsite still
        labor_savings += dfNewPlant.loc[idx, "Site Labor Hours"].sum() * (
            1 - offsite_work[i]
        )
        dfNewPlant.loc[idx, "Site Labor Hours"] *= (
            1 - offsite_work[i]
        )  # half of the labor is done onsite still
        dfNewPlant.loc[idx, "Site Material Cost"] = 0
        dfNewPlant.loc[
            idx, "Factory Equipment Cost"
        ] *= 1.02  # transportation costs are 2% of direct costs
        dfNewPlant.loc[idx_spec, "Factory Equipment Cost"] += (
            fact_costs[i] / orders
        )  # add in the cost of the factory
        idx_modules = idx_modules | idx
    print("Labor savings: " + str(labor_savings))

    return dfNewPlant, idx_modules
