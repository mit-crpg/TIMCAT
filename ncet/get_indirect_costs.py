import pandas as pd
import numpy as np
from os.path import join as pjoin

# def get_indirect_costs(dfNewPlant, dfPWR12BE, plant_characteristics, learning_rate):
def get_indirect_costs(dfNewPlant, plant_characteristics, learning_rate, scalars_dict):

    print("Scaling indirect costs")
    # dfOverrun = pd.read_csv('input_CostOverrun.csv')
    # dfOverrun.set_index('Account', inplace=True)
    # idx_indirect_dfOverrun = dfOverrun.index.str.match('A.9')
    # dfOverrun = dfOverrun.loc[idx_indirect_dfOverrun] #reduce the overrun cost DB just to the indirect cost accounts
    construction_months = (
        plant_characteristics["Construction duration (months)"] * learning_rate
    )

    root_idx = dfNewPlant["Subcategories"] == 1
    NQA_idx = dfNewPlant["NQA1"] == 1
    # indirect_idxNP  = dfNewPlant.index.str.match("A.9")
    direct_idxNP = dfNewPlant.index.str.match("A.2")
    # indirect_idx12  = dfPWR12BE.index.str.match("A.9")

    "These are the EEDB ME/BE Indirect Cost overruns at the total indirect cost level"
    # base_indirect_overrun = {'Factory Equipment Cost':2.7558, 'Site Labor Hours': 1.9092, 'Site Labor Cost': 1.92746, 'Site Material Cost': 1.66704, 'Total Cost':2.43577}
    NNC_indirect_cost = {
        "Factory Equipment Cost": 0,
        "Site Labor Hours": 0,
        "Site Labor Cost": 0,
        "Site Material Cost": 0,
        "Total Cost": 0,
    }
    NQA_indirect_cost = {
        "Factory Equipment Cost": 0,
        "Site Labor Hours": 0,
        "Site Labor Cost": 0,
        "Site Material Cost": 0,
        "Total Cost": 0,
    }
    np_indirect_cost = {
        "Factory Equipment Cost": 0,
        "Site Labor Hours": 0,
        "Site Labor Cost": 0,
        "Site Material Cost": 0,
        "Total Cost": 0,
    }
    indirect_multiplier = {
        "Factory Equipment Cost": 3.661,
        "Site Labor Hours": 0.360,
        "Site Labor Cost": 0.360,
        "Site Material Cost": 0.785,
    }

    "Make adjustments for uncertainty in the indirect cost multipliers"
    indirect_keys = [x for x in scalars_dict.keys() if "[Indirect]" in x]
    for indirect_key in indirect_keys:
        indirect_category = indirect_key.split("]")[1].strip()
        indirect_multiplier[indirect_category] = scalars_dict[indirect_key]

    "Pre compute values"
    total_direct_labor_hours = dfNewPlant.loc[
        (root_idx & direct_idxNP), "Site Labor Hours"
    ].sum()
    avgNumWorkersNewPlant = (
        total_direct_labor_hours / construction_months / 160
    )  # 160 working hours in a month
    mult_workers = np.max(
        [1, avgNumWorkersNewPlant / 1058]
    )  # 1058 comes from the EEDB average 12.1 million hours over 72 months, setting the max =1, assuming the BE plant was peak efficiency in staffing
    mult_constructionTime = np.max(
        [1, construction_months / 72]
    )  # the PWR12 better experience from EEDB took 72 months to build, assume there isnt a gain for shorter construction here
    print("Construction duration is {:.0F}".format(construction_months))
    print("Total direct labor hours is {:.0F}".format(total_direct_labor_hours))

    "Update indirect scalers"
    indirect_multiplier["Site Material Cost"] = (
        indirect_multiplier["Site Material Cost"] * mult_workers
    )
    indirect_multiplier["Factory Equipment Cost"] = (
        indirect_multiplier["Factory Equipment Cost"] * mult_constructionTime
    )

    # ----------------- NQA 1 Indirect costs ----------------
    "Scaling the indirect labor hours, labor costs, and material cost"
    for col in ["Site Labor Hours", "Site Labor Cost", "Site Material Cost"]:
        NQA_col_sum = dfNewPlant.loc[(root_idx & direct_idxNP & NQA_idx), col].sum()
        NQA_indirect_cost[col] = indirect_multiplier[col] * NQA_col_sum

    "Scaling the indirect factory costs and total cost"  # have to do this after the labor hours scaling
    NQA_indirect_cost["Factory Equipment Cost"] = (
        indirect_multiplier["Factory Equipment Cost"]
        * NQA_indirect_cost["Site Labor Cost"]
    )
    NQA_indirect_cost["Total Cost"] = sum(NQA_indirect_cost.values())

    # ----------------- NNC 1 Indirect costs ----------------
    "Scaling the indirect labor hours, labor costs, and material cost"
    for col in ["Site Labor Hours", "Site Labor Cost", "Site Material Cost"]:
        NNC_col_sum = dfNewPlant.loc[(root_idx & direct_idxNP & ~NQA_idx), col].sum()
        NNC_indirect_cost[col] = indirect_multiplier[col] * NNC_col_sum

    "Scaling the indirect factory costs and total cost"  # have to do this after the labor hours scaling
    NNC_indirect_cost["Factory Equipment Cost"] = (
        indirect_multiplier["Factory Equipment Cost"]
        * NNC_indirect_cost["Site Labor Cost"]
    )
    NNC_indirect_cost["Total Cost"] = sum(NNC_indirect_cost.values())

    # ----------------- Split costs ----------------
    idx = root_idx & direct_idxNP & NQA_idx
    NQA_direct_sum = (
        dfNewPlant.loc[idx, "Factory Equipment Cost"].sum()
        + dfNewPlant.loc[idx, "Site Labor Cost"].sum()
        + dfNewPlant.loc[idx, "Site Material Cost"].sum()
    )
    NQA_total_max = 1.49 * NQA_direct_sum

    idx = root_idx & direct_idxNP & ~NQA_idx
    NNC_direct_sum = (
        dfNewPlant.loc[idx, "Factory Equipment Cost"].sum()
        + dfNewPlant.loc[idx, "Site Labor Cost"].sum()
        + dfNewPlant.loc[idx, "Site Material Cost"].sum()
    )
    NNC_total = 0.60 * NNC_direct_sum

    NQA_diff = NQA_total_max - NQA_indirect_cost["Total Cost"]
    NNC_diff = NNC_total - NNC_indirect_cost["Total Cost"]

    if (
        NQA_diff > -NNC_diff
    ):  # Essentially do the total shifts in cost make sense, and should we correct for over/under expensive indirect costs
        NQA_extra = -NNC_diff
    else:
        NQA_extra = NQA_diff

    NQA_total = NQA_extra + NQA_indirect_cost["Total Cost"]
    NQA_mult = NQA_total / NQA_indirect_cost["Total Cost"]
    NNC_mult = NNC_total / NNC_indirect_cost["Total Cost"]

    for col in [
        "Site Labor Hours",
        "Site Labor Cost",
        "Site Material Cost",
        "Factory Equipment Cost",
    ]:
        NQA_indirect_cost[col] = NQA_indirect_cost[col] * NQA_mult
        NNC_indirect_cost[col] = NNC_indirect_cost[col] * NNC_mult
        np_indirect_cost[col] = NNC_indirect_cost[col] + NQA_indirect_cost[col]
    np_indirect_cost["Total Cost"] = sum(np_indirect_cost.values())
    # np_indirect_cost['Account'] = 'A.9'
    np_indirect_cost["Account Description"] = "Indirect Costs"
    np_indirect_cost["Subcategories"] = 1

    dfNewPlant = pd.concat(
        [dfNewPlant, pd.Series(np_indirect_cost, name="A.9").to_frame().T], 
    )
    
    # #----------------- Divide costs among correct overrun accounts ----------------
    # for col in ['Site Labor Hours', 'Site Labor Cost', 'Site Material Cost', 'Factory Equipment Cost']:
    # 	# pdb.set_trace()
    # 	indirect_cost_BE = dfPWR12BE.at['A.9', col]
    # 	NP_BE_ratio = np_indirect_cost[col]/indirect_cost_BE
    # 	if NP_BE_ratio <=1:
    # 		dfNewPlant.loc[indirect_idxNP, col] = dfPWR12BE.loc[indirect_idx12, col] * NP_BE_ratio
    # 	else:
    # 		for account in dfOverrun.index:
    # 			if len(account) > 5:
    # 				idxNP  = dfNewPlant.index.str.match(account)
    # 				idx12  = dfPWR12BE.index.str.match(account)
    # 			scaler = (dfOverrun.loc[account, col] - 1) / (base_indirect_overrun[col] - 1) * (NP_BE_ratio - 1) + 1
    # 			dfNewPlant.loc[idxNP, col] = dfPWR12BE.loc[idx12, col] * scaler

    # dfNewPlant.loc[indirect_idxNP, 'Total Cost'] = dfNewPlant.loc[indirect_idxNP, 'Factory Equipment Cost'] + dfNewPlant.loc[indirect_idxNP, 'Site Material Cost'] + dfNewPlant.loc[indirect_idxNP, 'Site Labor Cost']

    return dfNewPlant
