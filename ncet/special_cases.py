import pandas as pd
import pdb


def cost_multipliers(scaling_table, scalars_dict, plant_characteristics):
    # Some of the scalars dict have a key word to indicate how to apply them

    # Simplication scalars
    if plant_characteristics["Gen III+ or later"]:
        simple_keys = [x for x in scalars_dict.keys() if "[Simple]" in x]
        for simple_key in simple_keys:
            account = simple_key.split("]")[1].split(":")[0].strip()
            idx = scaling_table.index.str.match(account)
            # Don't do the cut the piping cost if a specific pipe weight was provided
            if (account != 'A.222.12') and (not all(scaling_table.loc[idx, 'Option']==1)):
                scaling_table.loc[idx, 'Multipliers'] *= scalars_dict[simple_key]

    # Passive safety systems scalars
    if plant_characteristics["Safety"] == "Passive":
        elect_keys = [x for x in scalars_dict.keys() if "[Electrical]" in x]

        for elect_key in elect_keys:
            account = elect_key.split("]")[1].split(":")[0].strip()
            idx = scaling_table.index.str.match(account)
            scaling_table.loc[idx, "Multipliers"] *= scalars_dict[elect_key]

    return scaling_table


def special_cases(dfNewPlant, plant_characteristics, scalars_dict):
    costs = ["Factory Equipment Cost", "Site Material Cost", "Site Labor Cost"]
    hours = ["Site Labor Hours"]

    # ---------------------------------------------Adjust for high strength rebar usage------------------------------------------------#
    accounts80 = plant_characteristics["Grade 80"]
    hsr80 = ["Grade 80"] * len(accounts80)

    accounts100 = plant_characteristics["Grade 100"]
    hsr100 = ["Grade 100"] * len(accounts100)

    accounts = accounts80 + accounts100
    hsr = hsr80 + hsr100
    aux = {"Grade 80": [0.81, 1.1], "Grade 100": [0.7, 1.5]}
    for i, account in enumerate(accounts):
        idx = dfNewPlant.index.str.match(account)

        reduction = aux[hsr[i]][0]
        cost_mult = aux[hsr[i]][1]

        idx_rebar = (dfNewPlant["Account Description"] == "Reinforcing Steel") & idx
        idx_cadwelds = (dfNewPlant["Account Description"] == "Cadwelds") & idx

        unit_mat_cost = (
            dfNewPlant.loc[idx_rebar, "Site Material Cost"]
            / dfNewPlant.loc[idx_rebar, "Site Quantity"]
        )
        unit_lab_cost = (
            dfNewPlant.loc[idx_rebar, "Site Labor Cost"]
            / dfNewPlant.loc[idx_rebar, "Site Quantity"]
        )
        unit_lab_hours = (
            dfNewPlant.loc[idx_rebar, "Site Labor Hours"]
            / dfNewPlant.loc[idx_rebar, "Site Quantity"]
        )
        dfNewPlant.loc[
            idx_rebar, "Site Quantity"
        ] *= reduction  # % reduction the rebar density
        dfNewPlant.loc[idx_rebar, "Site Material Cost"] = (
            dfNewPlant.loc[idx_rebar, "Site Quantity"] * unit_mat_cost * cost_mult
        )  # % material cost increase
        dfNewPlant.loc[idx_rebar, "Site Labor Cost"] = (
            dfNewPlant.loc[idx_rebar, "Site Quantity"] * unit_lab_cost
        )
        dfNewPlant.loc[idx_rebar, "Site Labor Hours"] = (
            dfNewPlant.loc[idx_rebar, "Site Quantity"] * unit_lab_hours
        )
        dfNewPlant.loc[idx_rebar, "Total Cost"] = (
            dfNewPlant.loc[idx_rebar, "Site Labor Cost"]
            + dfNewPlant.loc[idx_rebar, "Site Material Cost"]
        )

        dfNewPlant.loc[
            idx_cadwelds, (costs + hours)
        ] *= reduction  # % reduction the rebar density
        dfNewPlant.loc[idx_cadwelds, "Total Cost"] = (
            dfNewPlant.loc[idx_cadwelds, "Site Labor Cost"]
            + dfNewPlant.loc[idx_cadwelds, "Site Material Cost"]
        )

    # ---------------------------------------------Adjust for steel plate composite usage------------------------------------------------#

    accounts1 = plant_characteristics["SPC One sided"]
    spc1 = ["One sided"] * len(accounts1)
    accounts2 = plant_characteristics["SPC Two sided"]
    spc2 = ["Two sided"] * len(accounts2)
    spc_accounts = accounts1 + accounts2
    spc = spc1 + spc2

    "Apply operating engineer and welding cost to the rebar install"
    lab_rates = pd.read_csv(
        "input_LaborIndices.csv",
        dtype={"1986": float, "2018": float, "Index": float, "Base Rate": float},
    )
    lab_rates.set_index("Craft", inplace=True)
    operating_eng_rate = (
        lab_rates.loc["Operating Engineers", "Base Rate"]
        * lab_rates.loc["Operating Engineers", "Index"]
    )
    ironworker_rate = (
        lab_rates.loc["Ironworkers", "Base Rate"]
        * lab_rates.loc["Ironworkers", "Index"]
    )

    aux = {
        "One sided": [
            scalars_dict["SPC rebar reduction mult"] / 2,
            scalars_dict["SPC steel cost escalation"],
        ],
        "Two sided": [
            scalars_dict["SPC rebar reduction mult"],
            scalars_dict["SPC steel cost escalation"],
        ],
    }
    for i, account in enumerate(spc_accounts):
        idx = dfNewPlant.index.str.match(account)

        work_reduction = aux[spc[i]][0]
        cost_mult = aux[spc[i]][1]

        idx_spc = (
            idx
            & (dfNewPlant["Category2"] != "Interior Concrete")
            & (dfNewPlant["Category2"] != "Substructure Concrete")
        )  # don't apply the steel plate composite to interior concrete or foundation
        idx_formwork = (dfNewPlant["Account Description"] == "Formwork") & idx_spc
        idx_rebar = (dfNewPlant["Account Description"] == "Reinforcing Steel") & idx_spc
        # idx_concrete = (dfNewPlant['Account Description'] == 'Concrete') & idx_spc
        idx_cadwelds = (dfNewPlant["Account Description"] == "Cadwelds") & idx_spc

        # Adjust the relevant costs
        dfNewPlant.loc[
            idx_rebar, "Site Material Cost"
        ] *= cost_mult  # rebar cost is 1.48 times higher
        dfNewPlant.loc[
            idx_formwork, (costs + hours)
        ] *= work_reduction  # formwork becomes half or fully free
        dfNewPlant.loc[idx_cadwelds, (costs + hours)] = 0.0  # no cadwelding with spc

        newPlant_superArea = plant_characteristics["SPC Area"][i]
        dfNewPlant.loc[
            idx_rebar, ["Site Labor Cost", "Site Labor Hours"]
        ] = 0.0  # first rebar install becomes free
        lift_time = scalars_dict["SPC operating engineer lift time (per 30 m2)"]
        dfNewPlant.loc[idx_rebar, "Site Labor Hours"] = (
            newPlant_superArea / 30.2 * lift_time
        )  # each section is 30.2 m^2 and takes ~8 hours to lift
        dfNewPlant.loc[idx_rebar, "Site Labor Cost"] = (
            dfNewPlant.loc[idx_rebar, "Site Labor Hours"] * operating_eng_rate
        )

        weld_time = scalars_dict["SPC weld time (per 30 m2)"]
        weld_hours = (
            newPlant_superArea / 30.2 * weld_time * (1 - work_reduction)
        )  # each section is 30.2 m^2 and takes ~87 hours to weld, half the welding for the one sided case
        dfNewPlant.loc[idx_rebar, "Site Labor Hours"] += weld_hours
        dfNewPlant.loc[idx_rebar, "Site Labor Cost"] += weld_hours * ironworker_rate
        dfNewPlant.loc[idx_rebar, "Total Cost"] = (
            dfNewPlant.loc[idx_rebar, "Site Labor Cost"]
            + dfNewPlant.loc[idx_rebar, "Site Material Cost"]
        )

    # ---------------------------------------------Adjust for rebar densities------------------------------------------------#
    # There has to be a better way to do this...
    if "Rebar table" in plant_characteristics:
        rebar_dict = plant_characteristics["Rebar table"]
        for bldg in rebar_dict:
            if bldg == "A.212.":
                accounts = ["A.212.132", "A.212.14112", "A.212.14122", "A.212.1402"]
                defaults = [0.047, 0.047, 0.049, 0.039]
                densities = (
                    rebar_dict[bldg].replace("[", "").replace("]", "").split(",")
                )
                densities = [float(x) for x in densities]
                densities.insert(
                    1, densities[1]
                )  # combining shell and dome for superstructure
                for i, account in enumerate(accounts):
                    dfNewPlant.loc[account, (costs + hours)] *= (
                        densities[i] / defaults[i]
                    )

            elif bldg == "A.213.":
                accounts = ["A.213.132", "A.213.1412"]
                defaults = [0.011, 0.013]
                densities = (
                    rebar_dict[bldg].replace("[", "").replace("]", "").split(",")
                )
                densities = [float(i) for i in densities]
                for i, account in enumerate(accounts):
                    dfNewPlant.loc[account, (costs + hours)] *= (
                        densities[i] / defaults[i]
                    )

            elif bldg == "A.215.":
                accounts = ["A.215.132", "A.215.1412"]
                defaults = [0.019, 0.022]
                densities = (
                    rebar_dict[bldg].replace("[", "").replace("]", "").split(",")
                )
                densities = [float(i) for i in densities]
                for i, account in enumerate(accounts):
                    dfNewPlant.loc[account, (costs + hours)] *= (
                        densities[i] / defaults[i]
                    )

    # ---------------------------------------------Adjust for containment types------------------------------------------------#

    if plant_characteristics["Containment type"] != ["Steel lined concrete"]:
        if "A.212." not in spc_accounts:
            # Reduce rebar density because the building isn't pressure containing
            idx = dfNewPlant.index.str.match("A.212.14")
            idx_rebar = (dfNewPlant["Account Description"] == "Reinforcing Steel") & idx
            idx_cadwelds = (dfNewPlant["Account Description"] == "Cadwelds") & idx
            dfNewPlant.loc[idx_cadwelds, (costs + hours)] /= 2.5
            dfNewPlant.loc[idx_rebar, (costs + hours)] /= 2.5

    if plant_characteristics["Containment type"] == "Steel vessel":
        idx = dfNewPlant.index.str.match("A.212.140")
        idx_steel = (dfNewPlant["Account Description"] == "Embedded Steel") & idx
        idx_rcp = (
            dfNewPlant["Account Description"] == "Reactor Cavity Liner Plate"
        ) & idx
        idx_mse = (
            dfNewPlant["Account Description"] == "Major Support Embedments"
        ) & idx
        dfNewPlant.loc[idx_steel, (costs + hours)] /= 4
        dfNewPlant.loc[idx_rcp, (costs + hours)] = 0.0
        dfNewPlant.loc[idx_mse, (costs + hours)] = 0.0

    # ---------------------------------------------Advanced manufacturing or intregal RPV------------------------------------------------#

    if plant_characteristics["RPV thickness (m)"] <= 0.11:
        # EPRI can E-beam weld (and do other things to) your vessel reducing cost ~40%
        dfNewPlant.loc["A.221.12", (costs + hours)] *= scalars_dict[
            "E-beam weld cost reduction mult"
        ]

    if (plant_characteristics['Containment type'] == 'Steel vessel') and (plant_characteristics['Containment thickness (m)'] <= .11):
        dfNewPlant.loc['A.212.15', (costs + hours)] *= scalars_dict[
            'E-beam weld cost reduction mult'
            ]

    if plant_characteristics[
        "Integral PWR"
    ]:  # no vessel cost for an integrated steam generator/pressurizer/vessel
        dfNewPlant.loc["A.222.132", (costs + hours)] *= scalars_dict[
            "222.13 Steam generators reduction mult"
        ]
        dfNewPlant.loc["A.222.14", (costs + hours)] *= scalars_dict[
            "222.14 Pressurizer reduction mult"
        ]

    # This is the case where the SG vessel is part of the primary pressure boundary (not the case for 
	# PWRs where tubes are the primary pressure boundary). 
	# The vessel cost goes up by a factor of 3.5, which raise the total SG cost by 2.25
	# The tubes for the PWR are inconel and more expensive than the stainless equivalent for HTGRs,
	# but the HTGR coiling is more complicated, so call it a wash in cost per area
    if plant_characteristics['SG vessel is primary pressure boundary'] and not plant_characteristics['Integral PWR']: 
        dfNewPlant.loc['A.222.132', (costs + hours)] *= 2.25
        # pdb.set_trace()

    return dfNewPlant
