import pandas as pd
import numpy as np
from os.path import join as pjoin
import pdb
from .bldg_features import eval_bldg
from .special_cases import cost_multipliers
from .material_use_uncertainty import material_use_uncertainty


def fill_scaling_table(path, fname, base, scalars_dict, scaling_table=None):

    if scaling_table is None:
        scaling_table = pd.read_csv(
            pjoin(path, "input_scaling_exponents.csv"), header=0, index_col="Account"
        )
    else:
        scaling_table.set_index("Account", inplace=True)

    scaling_table["Option"] = 1
    scaling_table["New Base Unit Value"] = 0.0
    scaling_table["Multipliers"] = 1.0
    scaling_table["Factory Equipment Cost Mult"] = 1.0
    scaling_table["Site Labor Hours Mult"] = 1.0
    scaling_table["Site Labor Cost Mult"] = 1.0
    scaling_table["Site Material Cost Mult"] = 1.0
    scaling_table["Count per plant"] = 1
    scaling_table["New Cost"] = 0.0
    inside_dict = {}

    plant_characteristics = pd.read_excel(
        pjoin(path, fname),
        sheet_name="PlantCharacteristics",
        header=None,
        skiprows=[0],
        index_col=0,
    ).to_dict()[1]
    plant_characteristics["SPC One sided"] = []
    plant_characteristics["SPC Two sided"] = []
    plant_characteristics["SPC Area"] = []
    plant_characteristics["Grade 80"] = []
    plant_characteristics["Grade 100"] = []
    plant_characteristics["Containment type"] = ["Steel lined concrete"]

    plant_characteristics["sc1_BV"] = 0  # Seismic Category 1 Building Volume tally
    plant_characteristics[
        "sc1_concrete"
    ] = 0  # Seismic Category 1 concrete Volume tally
    concrete = 0
    bv_accounts_225 = ["A.212.", "A.213.", "A.215.", "A.216.", "A.217."]
    bv_225 = 0

    df21 = pd.read_excel(
        pjoin(path, fname),
        header=0,
        sheet_name="21-Structures&Improvements",
        skiprows=[0],
        index_col="Account",
    )
    df22 = pd.read_excel(
        pjoin(path, fname),
        header=0,
        sheet_name="22-ReactorEquipment",
        skiprows=[0],
        index_col="Account",
    )
    df23 = pd.read_excel(
        pjoin(path, fname),
        header=0,
        sheet_name="23-TurbineEquipment",
        skiprows=[0],
        index_col="Account",
    )
    df24 = pd.read_excel(
        pjoin(path, fname),
        header=0,
        sheet_name="24-ElectricalEquipment",
        skiprows=[0],
        index_col="Account",
    )
    df25 = pd.read_excel(
        pjoin(path, fname),
        header=0,
        sheet_name="25-MiscEquipment",
        skiprows=[0],
        index_col="Account",
    )
    df26 = pd.read_excel(
        pjoin(path, fname),
        header=0,
        sheet_name="26-HeatRejectionSystem",
        skiprows=[0],
        index_col="Account",
    )

    # Add this for making the building_table
    plant_characteristics["New Bldg"] = df21["SSCs moved to"]
    # Add dict to adjust rebar costs in special cases [should figure out a better way to do this eventually]
    if any(df21["Rebar density"] != "Default"):
        plant_characteristics["Rebar table"] = df21.loc[
            df21["Rebar density"] != "Default", "Rebar density"
        ].to_dict()

    # ---------------------------------------------Account 21 Structures & Improvements------------------------------------------------#
    print("Evaluating account 21: Structures & Improvements")
    accounts = df21.index.unique()
    ibv = scaling_table["Option 1"] == "Building volume"
    isba = scaling_table["Option 1"] == "Substructure area"
    isbv = scaling_table["Option 1"] == "Substructure volume"
    ispa = scaling_table["Option 1"] == "Superstructure area"
    ispv = scaling_table["Option 1"] == "Superstructure volume"
    ipow = scaling_table["Option 1"] == "Plant power"
    ic = scaling_table["Option 1"] == "Constant"

    for account in accounts:
        aux = df21.loc[account]
        print("	Account: " + account + ", Name: " + aux["Name"])

        if aux["Method"] == "Detailed (EEDB based)":
            idx = scaling_table.index.str.match(account)

            # Calculate material use volumes/areas
            portions = aux["Portions"]
            subArea, subVol, superArea, superVol, bv = eval_bldg(portions, aux)

            # Check if the building is inside another building (or has one inside it), and account for the changes to material use as necessary
            if aux["Inside?"] != "None":
                inside_acct = "A." + aux["Inside?"].split("A.")[1]
                in_or_out = aux["Inside?"].split(":")[0]
                if in_or_out == "Inside":
                    inside_dict[inside_acct] = [
                        account,
                        subArea,
                        subVol,
                        superArea,
                        superVol,
                        bv,
                    ]
                elif in_or_out == "Outside":
                    (
                        in_account,
                        in_subArea,
                        in_subVol,
                        in_superArea,
                        in_superVol,
                        in_bv,
                    ) = inside_dict[account]
                    subArea -= in_subArea
                    subVol -= in_subVol
                    bv -= in_bv
            print(
                "		Superstructure volume: {:.0F}, area: {:.0F}".format(
                    superVol, superArea
                )
            )
            print("		Substructure volume: {:.0F}, area: {:.0F}".format(subVol, subArea))
            print("		Building volume: {:.0F}".format(bv))
            plant_characteristics[account] = subArea

            # Update the scaling table with the calculated values
            scaling_table.loc[(idx & ibv), "New Base Unit Value"] = bv
            scaling_table.loc[(idx & isba), "New Base Unit Value"] = subArea
            scaling_table.loc[(idx & isbv), "New Base Unit Value"] = subVol
            scaling_table.loc[(idx & ispa), "New Base Unit Value"] = superArea
            scaling_table.loc[(idx & ispv), "New Base Unit Value"] = superVol
            scaling_table.loc[(idx & ic), "New Base Unit Value"] = 1
            scaling_table.loc[
                (idx & ipow), "New Base Unit Value"
            ] = plant_characteristics["Total Plant Thermal Power (MWt)"]

            if aux["Steel plate composite"] == "One sided":
                plant_characteristics["SPC One sided"].append(account)
                plant_characteristics["SPC Area"].append(superArea)
            elif aux["Steel plate composite"] == "Two sided":
                plant_characteristics["SPC Two sided"].append(account)
                plant_characteristics["SPC Area"].append(superArea)

            if aux["High strength rebar"] == "Grade 80":
                plant_characteristics["Grade 80"].append(account)
            elif aux["High strength rebar"] == "Grade 100":
                plant_characteristics["Grade 100"].append(account)

            if aux["Seismic Class 1"]:
                plant_characteristics["sc1_BV"] += bv
                plant_characteristics["sc1_concrete"] += subVol + superVol
            if account in bv_accounts_225:
                bv_225 += bv
            concrete += subVol + superVol

            if aux["Name"] == "Containment Liner":
                # default is option 1, scaled by superstructure area for steel lined concrete, these are the exceptions
                if aux["Superstructure type"] == "Stainless steel vessel":
                    scaling_table.at[account, "Option"] = 0
                    mass = 8000.0 * (
                        superVol + subVol
                    )  # 8000 kg/m^3 is the density of stainless steel
                    print("		Mass of containment vessel: {:.0F}".format(mass))
                    scaling_table.at[account, "New Base Unit Value"] = mass
                    scaling_table.at[
                        account, "Multipliers"
                    ] = 2.3  # stainless more than carbon steel
                    scaling_table.at[
                        account, "Count per plant"
                    ] = plant_characteristics["Number of Reactors"]
                    plant_characteristics["Containment type"] = "Steel vessel"
                    plant_characteristics["Containment vessel mass (kg)"] = mass

                elif aux["Superstructure type"] == "Standalone steel building":

                    plant_characteristics[
                        "Containment type"
                    ] = "Standalone steel building"
                    # The multipliers came from the EEDB APWR6/PWR6/BE account breakdowns
                    scaling_table.at[
                        account, "Factory Equipment Cost Mult"
                    ] *= scalars_dict["212.15 Factory cost mult"]
                    scaling_table.at[account, "Site Labor Hours Mult"] *= scalars_dict[
                        "212.15 Labor hours mult"
                    ]
                    scaling_table.at[account, "Site Labor Cost Mult"] *= scalars_dict[
                        "212.15 Labor cost mult"
                    ]
                    scaling_table.at[
                        account, "Site Material Cost Mult"
                    ] *= scalars_dict["212.15 Material cost mult"]
                    plant_characteristics["Containment type"] = [
                        "Standalone steel building"
                    ]

        elif aux["Method"] == "Detailed (Generic)":
            print("Error, generic building not implemented yet")
            break

        elif aux["Method"] == "Plant power scaling":
            idx = scaling_table.index.str.match(account)
            scaling_table.loc[idx, "Option"] = 2
            scaling_table.loc[idx, "New Base Unit Value"] = plant_characteristics[
                "Total Plant Thermal Power (MWt)"
            ]

        elif aux["Method"] == "RX power scaling":
            idx = scaling_table.index.str.match(account)
            scaling_table.loc[idx, "Option"] = 2
            scaling_table.at[idx, "New Base Unit Value"] = (
                plant_characteristics["Total Plant Thermal Power (MWt)"]
                / plant_characteristics["Number of Reactors"]
            )

        elif aux["Method"] == "Fixed cost":
            idx = scaling_table.index.str.match(account)
            scaling_table.loc[idx, "Option"] = 4
            scaling_table.at[idx, "New Base Unit Value"] = 1

        elif aux["Method"] == "Direct cost":
            idx = scaling_table.index.str.match(account)
            scaling_table.loc[idx, "Option"] = 3
            scaling_table.at[idx, "New Base Unit Value"] = df21.loc[
                account, "Direct cost per RX (2018 USD)"
            ]

    # ------------------------------------------------------Account 22-26 ------------------------------------------------------#
    print("Evaluating account 22 - 26")
    df_big = df22.append(df23)
    df_big = df_big.append(df24)
    df_big = df_big.append(df25)
    df_big = df_big.append(df26)

    idx_PPS = df_big.index[df_big["Method"] == "Plant power scaling"]
    scaling_table.loc[idx_PPS, "Option"] = 2
    scaling_table.loc[idx_PPS, "New Base Unit Value"] = plant_characteristics[
        "Total Plant Thermal Power (MWt)"
    ]

    idx_EPS = df_big.index[df_big["Method"] == "Plant electric power scaling"]
    scaling_table.loc[idx_EPS, "Option"] = 2
    scaling_table.loc[idx_EPS, "New Base Unit Value"] = plant_characteristics[
        "Net Electrical Power (MWe)"
    ]

    idx_TEPS = df_big.index[df_big["Method"] == "Turbine electric power scaling"]
    scaling_table.loc[idx_TEPS, "Option"] = 2
    scaling_table.loc[idx_TEPS, "New Base Unit Value"] = plant_characteristics[
        "Net Electrical Power (MWe)"
    ]
    scaling_table.loc[idx_TEPS, "Count per plant"] = plant_characteristics[
        "Number of Reactors"
    ]

    idx_RPS = df_big.index[df_big["Method"] == "RX power scaling"]
    scaling_table.loc[idx_RPS, "Option"] = 2
    scaling_table.loc[idx_RPS, "New Base Unit Value"] = (
        plant_characteristics["Total Plant Thermal Power (MWt)"]
        / plant_characteristics["Number of Reactors"]
    )
    scaling_table.loc[idx_RPS, "Count per plant"] = plant_characteristics[
        "Number of Reactors"
    ]

    idx_FC = df_big.index[df_big["Method"] == "Fixed cost"]
    scaling_table.loc[idx_FC, "Option"] = 4
    scaling_table.loc[idx_FC, "New Base Unit Value"] = 1

    idx_D = df_big.index[df_big["Method"] == "Detailed"]
    scaling_table.loc[idx_D, "Option"] = 1
    scaling_table.loc[idx_D, "New Base Unit Value"] = df_big.loc[idx_D, "Value"]
    scaling_table.loc[idx_D, "Count per plant"] = df_big.loc[
        idx_D, "Count per plant (DI)"
    ]

    idx_Dv = df_big.index[df_big["Method"] == "Detailed volume"]
    scaling_table.loc[idx_Dv, "Option"] = 1
    scaling_table.loc[idx_Dv, "New Base Unit Value"] = bv_225

    idx_Dp = df_big.index[df_big["Method"] == "Detailed pool"]
    scaling_table.loc[idx_Dp, "Option"] = 0
    scaling_table.loc[idx_Dp, "New Base Unit Value"] = df_big.loc[idx_Dp, "Value"]
    scaling_table.loc[idx_Dp, "Count per plant"] = df_big.loc[
        idx_Dp, "Count per plant (DI)"
    ]

    idx_Dce = df_big.index[df_big["Method"] == "Detailed (CE)"]
    scaling_table.loc[idx_Dce, "Option"] = 0
    scaling_table.loc[idx_Dce, "New Base Unit Value"] = df_big.loc[idx_Dce, "Value"]
    scaling_table.loc[idx_Dce, "Count per plant"] = df_big.loc[
        idx_Dce, "Count per plant (DI)"
    ]

    idx_DCI = df_big.index[df_big["Method"] == "Direct cost input"]
    scaling_table.loc[idx_DCI, "Option"] = 3
    scaling_table.loc[idx_DCI, "New Base Unit Value"] = df_big.loc[
        idx_DCI, "Direct cost per RX (2018 USD)"
    ]
    scaling_table.loc[idx_DCI, "Count per plant"] = df_big.loc[
        idx_DCI, "Count per plant (DCI)"
    ]

    idx = df_big.index
    scaling_table = cost_multipliers(scaling_table, scalars_dict, plant_characteristics)
    scaling_table = material_use_uncertainty(scaling_table, scalars_dict)

    # --------------------------------------------- Scaling/evaluating new costs -----------------------------------#
    scaling_table["Scaling Factor"] = 0
    accounts_0 = scaling_table.index[scaling_table["Option"] == 0]
    accounts_1 = scaling_table["Option"] == 1
    accounts_2 = scaling_table["Option"] == 2
    accounts_3 = scaling_table["Option"] == 3
    accounts_4 = scaling_table["Option"] == 4

    scaling_table.loc[accounts_1, "Scaling Factor"] = (
        scaling_table.loc[accounts_1, "New Base Unit Value"]
        / scaling_table.loc[accounts_1, "EEDB Base Unit Value 1"]
    ) ** scaling_table.loc[accounts_1, "Option 1 Exponent"]
    scaling_table.loc[accounts_2, "Scaling Factor"] = (
        scaling_table.loc[accounts_2, "New Base Unit Value"]
        / scaling_table.loc[accounts_2, "EEDB Base Unit Value 2"]
    ) ** scaling_table.loc[accounts_2, "Option 2 Exponent"]
    scaling_table.loc[accounts_3, "Scaling Factor"] = (
        scaling_table.loc[accounts_3, "New Base Unit Value"]
        / scaling_table.loc[accounts_3, "EEDB Base Unit Value 3"]
    )
    scaling_table.loc[accounts_4, "Scaling Factor"] = 1.0

    for account in accounts_0:
        if not isinstance(scaling_table.at[account, "Option 0 Formula"], list):
            varz = (
                scaling_table.at[account, "Option 0 Formula"]
                .replace("[", "")
                .replace("]", "")
                .split(",")
            )
        else:
            varz = scaling_table.at[account, "Option 0 Formula"]
        varz = [float(x) for x in varz]
        if len(varz) == 4:
            scaling_table.at[account, "Scaling Factor"] = (
                (
                    varz[0]
                    + varz[1]
                    * scaling_table.at[account, "New Base Unit Value"] ** varz[2]
                )
                * varz[3]
                / scaling_table.at[account, "EEDB Base Unit Value 3"]
            )
        elif len(varz) == 1:
            scaling_table.at[account, "Scaling Factor"] = (
                varz[0]
                * scaling_table.at[account, "New Base Unit Value"]
                / scaling_table.at[account, "EEDB Base Unit Value 3"]
            )

    # --------------------------------------------- Accounting for # per plant -------------------------------------#
    scaling_table["Scaling Factor"] *= scaling_table["Count per plant"]
    # scaling_table.to_csv('./out/out_'+ fname[10:-5] +'_scaling_table.csv')

    # --------------------------------------------- Add interior concrete to SC1 concrete ------------------------------------#
    plant_characteristics["sc1_concrete"] += (
        scaling_table.at["A.212.140", "Scaling Factor"] * 8000 / 1.1 ** 3
    )  # 8000 CY of interior concrete in EEDB
    concrete += (
        scaling_table.at["A.212.140", "Scaling Factor"] * 8000 / 1.1 ** 3
    )  # 8000 CY of interior concrete in EEDB
    print("Concrete total: {:.0F}".format(concrete))
    print("SC1 Concrete: {:.0F}".format(plant_characteristics["sc1_concrete"]))
    # print(scaling_table.at['A.212.140', 'Scaling Factor']*8000/1.1**3)

    return scaling_table, plant_characteristics
