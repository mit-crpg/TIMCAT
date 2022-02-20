import numpy as np
from os.path import join as pjoin
import pandas as pd
import os
import pdb
from ncet import fill_scaling_table
from ncet import scale_direct_costs
from ncet import modularize
from ncet import learn
from ncet import get_indirect_costs
from ncet import sum_accounts
from ncet import get_sub_account_iloc
import cProfile
import datetime


def update_input_scaling(fname, case="Base"):
    # Read in the two tabs of inputs and ranges
    df_inputs = pd.read_excel(fname, sheet_name="input_scaling")
    df_scalars = pd.read_excel(fname, sheet_name="param_ranges")

    # Create dictionary of parameters for the specific case
    scalars_dict = df_scalars.set_index("Parameter")[case + " value"].to_dict()

    print(df_inputs)
    # Map the new values to the input df
    options = [0, 1, 2]
    for option in options:
        if option == 0:
            for idx in df_inputs.index:
                if df_inputs["Option 0"].iloc[idx] is not np.nan:
                    varz = (
                        df_inputs["Option 0 Formula"]
                        .iloc[idx]
                        .replace("[", "")
                        .replace("]", "")
                        .split(",")
                    )
                    varz = [x.strip() for x in varz]
                    if len(varz) == 4:
                        varz[2] = scalars_dict[varz[2]]
                        varz[3] = scalars_dict[varz[3]]
                    else:
                        varz[0] = scalars_dict[varz[0]]
                    varz = [float(x) for x in varz]
                    df_inputs.at[idx, "Option 0 Formula"] = varz
        else:
            aux = (
                df_inputs["Option " + str(option) + " Exponent"]
                .astype(str)
                .str.isnumeric()
            )
            numbers = df_inputs["Option " + str(option) + " Exponent"].loc[aux].values
            df_inputs["Option " + str(option) + " Exponent"] = df_inputs[
                "Option " + str(option) + " Exponent"
            ].map(scalars_dict)
            df_inputs.loc[aux, "Option " + str(option) + " Exponent"] = numbers

    return df_inputs, scalars_dict


def build_schedule_table(plant_list, id, scheduler_table):
    for i, dfNP in enumerate(plant_list):
        labor_df = dfNP["Site Labor Hours"]
        scheduler_table = scheduler_table.merge(labor_df, how="left", on="Account")
        scheduler_table.rename(
            columns={"Site Labor Hours": "Hours run" + str(id) + "_unit" + str(i)},
            inplace=True,
        )

    return scheduler_table


def rand_input_scaling(fname):
    # Read in the two tabs of inputs and ranges
    df_inputs = pd.read_excel(fname, sheet_name="input_scaling")
    df_scalars = pd.read_excel(fname, sheet_name="param_ranges", index_col="Parameter")

    df_scalars["New value"] = 0
    for param in df_scalars.index:
        if df_scalars.loc[param, "Distribution"] == "lognormal":
            df_scalars.loc[param, "New value"] = np.random.lognormal(
                df_scalars.at[param, "mu/lambda"], df_scalars.at[param, "sigma"]
            )
        elif df_scalars.loc[param, "Distribution"] == "exponential":
            df_scalars.loc[param, "New value"] = np.random.exponential(
                1 / df_scalars.at[param, "mu/lambda"]
            )
        elif df_scalars.loc[param, "Distribution"] == "normal":
            df_scalars.loc[param, "New value"] = np.random.normal(
                df_scalars.at[param, "mu/lambda"], df_scalars.at[param, "sigma"]
            )
        elif df_scalars.loc[param, "Distribution"] == "uniform":
            df_scalars.loc[param, "New value"] = np.random.uniform(
                df_scalars.at[param, "Min value"], df_scalars.at[param, "Max value"]
            )

    # Create dictionary of parameters for the specific case
    scalars_dict = df_scalars["New value"].to_dict()

    # Map the new values to the input df
    options = [0, 1, 2]
    for option in options:
        if option == 0:
            for idx in df_inputs.index:
                if df_inputs["Option 0"].iloc[idx] is not np.nan:
                    varz = (
                        df_inputs["Option 0 Formula"]
                        .iloc[idx]
                        .replace("[", "")
                        .replace("]", "")
                        .split(",")
                    )
                    varz = [x.strip() for x in varz]
                    if len(varz) == 4:
                        varz[2] = scalars_dict[varz[2]]
                        varz[3] = scalars_dict[varz[3]]
                    else:
                        varz[0] = scalars_dict[varz[0]]
                    varz = [float(x) for x in varz]
                    df_inputs.at[idx, "Option 0 Formula"] = varz
        else:
            aux = (
                df_inputs["Option " + str(option) + " Exponent"]
                .astype(str)
                .str.isnumeric()
            )
            numbers = df_inputs["Option " + str(option) + " Exponent"].loc[aux].values
            df_inputs["Option " + str(option) + " Exponent"] = df_inputs[
                "Option " + str(option) + " Exponent"
            ].map(scalars_dict)
            df_inputs.loc[aux, "Option " + str(option) + " Exponent"] = numbers

    return df_inputs, scalars_dict


def build_mc_output_series(df):
    output_rows = ["A.1", "A.2", "A.9", "A.21", "A.22", "A.23", "A.24", "A.25", "A.26"]
    output_cols = [
        "Factory Equipment Cost",
        "Site Labor Cost",
        "Site Material Cost",
        "Total Cost",
    ]
    output_dict = {}  # pd.DataFrame(columns=['Description', 'Value'])

    for i in output_rows:
        for j in output_cols:
            output_dict[i + " " + j] = df.at[i, j]

    return output_dict


def get_building_table(plant_characteristics, scaling_table):
    bldg_template = pd.read_csv("building_template.csv", index_col="Account")
    bldg_template["Area"] = bldg_template.index
    bldg_template["Area"] = bldg_template["Area"].map(plant_characteristics)
    for account in bldg_template.index:
        if pd.isna(bldg_template.at[account, "Area"]):
            aux = bldg_template.at[account, "Scaling Account"]
            bldg_template.at[account, "Area"] = (
                scaling_table.at[aux, "Scaling Factor"]
                * bldg_template.at[account, "Area - PWR12"]
            )

    bldg_template["Staff Limit"] = (
        352.82 * (bldg_template["Area"].values / 1534) ** 0.7
    )  # this was a data fit on workers/m^2

    # Scale the site prep by the reference staff limit because the above equation breaks down for open areas
    bldg_template.at["A.211.", "Staff Limit"] = np.min(
        [
            bldg_template.at["A.211.", "Staff Limit - PWR12"],
            bldg_template.at["A.211.", "Staff Limit"],
        ]
    )

    # Add the map for where SSCs may have moved from one building to another
    bldg_template["New Building"] = plant_characteristics["New Bldg"]

    bldg_template["Staff Limit"] = bldg_template["Staff Limit"].astype(float).round(0)

    return bldg_template


def run_ncet(
    plant,
    path,
    orders,
    plant_fname,
    param_fname,
    BASIS_FNAME,
    mc_runs=1,
    make_building_table=False,
    save_all=False,
):
    scheduler_table = pd.read_csv("scheduler_table.csv", index_col=0)

    # Make the directories if they don't exist (use the timestamp to avoid overwriting anythingS)
    if not os.path.isdir(path + "/out"):
        os.mkdir(path + "/out")
    if not os.path.isdir(path + "/out/" + plant):
        os.mkdir(path + "/out/" + plant)
    time_folder = "/" + datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    os.mkdir(path + "/out/" + plant + time_folder)
    os.mkdir(path + "/out/" + plant + time_folder + "/raw")
    os.mkdir(path + "/out/" + plant + time_folder + "/scaling_tables")

    # Run the cost modeling functions
    mc_dict_list = [[] for _ in range(orders)]
    for i in range(mc_runs):
        # Get the scaling table parameters
        if mc_runs == 1:
            df_scalars, scalars_dict = update_input_scaling(param_fname)
        else:
            df_scalars, scalars_dict = rand_input_scaling(param_fname)

        # Fill out the scaling table with the input file data
        scaling_table, plant_characteristics = fill_scaling_table.fill_scaling_table(
            path,
            plant_fname,
            base=BASIS_FNAME,
            scaling_table=df_scalars,
            scalars_dict=scalars_dict,
        )
        if mc_runs == 1:
            scaling_table.to_csv(
                path
                + "/out/"
                + plant
                + time_folder
                + "/base_"
                + plant
                + "scaling_inputs.csv"
            )
        elif save_all:
            scaling_table.to_csv(
                path
                + "/out/"
                + plant
                + time_folder
                + "/scaling_tables/mc_output_"
                + plant
                + "scaling_inputs_"
                + str(i)
                + ".csv"
            )

        # Build the input file for construction scheduler if needed
        if make_building_table:
            bldg_table = get_building_table(plant_characteristics, scaling_table)
            bldg_table.to_csv(
                path
                + "/out/"
                + plant
                + time_folder
                + "/base_"
                + plant
                + "buildingtable.csv"
            )

        # Scale the direct costs based on the scaling table
        dfNP = scale_direct_costs.scale_direct_costs(
            BASIS_FNAME, scaling_table, plant_characteristics, scalars_dict
        )

        # Get the subaccount indices to accelerate the summing process below
        idx_dict = get_sub_account_iloc.get_sub_account_iloc(dfNP)

        # Modularize, learn, and build the scheduler table
        dfNP, idx_modules = modularize.modularize(
            path, plant_fname, dfNP, orders, scalars_dict
        )
        newPlant_list, learning_rate = learn.learn(
            path, plant_fname, dfNP, orders, scalars_dict, idx_modules
        )
        scheduler_table = build_schedule_table(newPlant_list, i, scheduler_table)

        # Get the indirect costs, sum all costs, and save files
        for j, dfNP in enumerate(newPlant_list):
            dfNP = get_indirect_costs.get_indirect_costs(
                dfNP, plant_characteristics, learning_rate[j], scalars_dict
            )
            dfNP = sum_accounts.sum_accounts(dfNP, idx_dict)

            # Build an output dictionary of all the results for monte carlo
            if mc_runs != 1:
                if save_all:
                    dfNP.to_csv(
                        path
                        + "/out/"
                        + plant
                        + time_folder
                        + "/raw/mc_"
                        + plant
                        + "_run"
                        + str(i)
                        + "_unit"
                        + str(j + 1)
                        + ".csv"
                    )
                output_dict = build_mc_output_series(dfNP)
                output_dict["Run"] = i
                mc_dict_list[j].append(output_dict)
            else:
                dfNP.to_csv(
                    path
                    + "/out/"
                    + plant
                    + time_folder
                    + "/new"
                    + plant
                    + "_Base_"
                    + str(j)
                    + ".csv"
                )

    # Save all the output dictionaries from montecarlo
    if mc_runs != 1:
        for i, dict_list in enumerate(mc_dict_list):
            pd.DataFrame(dict_list).to_csv(
                path
                + "/out/"
                + plant
                + time_folder
                + "/mc_output_"
                + plant
                + "_unit"
                + str(i + 1)
                + ".csv"
            )
        scheduler_table.to_csv(
            path
            + "/out/"
            + plant
            + time_folder
            + "/mc_"
            + plant
            + "_scheduler_table.csv"
        )
    else:
        scheduler_table.to_csv(
            path + "/out/" + plant + time_folder + "/" + plant + "_scheduler_table.csv"
        )


if __name__ == "__main__":
    start_time = datetime.datetime.now()
    path = os.path.dirname(__file__)  # Get the path to the project directory
    print(path)
    # Setup parameters:
    # plant_fname: name of the plant input file
    # BASIS_FNAME: ME or BE (choosing BE starts at NOAK), this is EEDB basis table <---- depends on user
    # plant_fname: the EXCEL file containing design inputs. good to use plant variable to define the name.
    # param_fname: of the EXCEL sheet with two tabs: input_scaling and param_ranges
    # cases: match those on param_ranges
    # orders: how many plants to run the learning model out to and capitalize the factory costs over

    plant = "PWR12ME"
    BASIS_FNAME = (
        "/Users/nitwit/Dropbox/hans/Omega-13/OMEGA14DATA/PWR12_ME_inflated_reduced.csv"
    )
    plant_fname = "inputfile_" + plant + ".xlsx"

    param_fname = "input_scaling_exponents.xlsx"
    orders = 10

    mc_runs = 1  # choose 1 to run the reference values
    # cProfile.run('run_ncet(plant, path, orders, plant_fname, param_fname, BASIS_FNAME, mc_runs=mc_runs, make_building_table=True, save_all=True)')
    run_ncet(
        plant,
        path,
        orders,
        plant_fname,
        param_fname,
        BASIS_FNAME,
        mc_runs=mc_runs,
        make_building_table=True,
        save_all=True,
    )

    # mc_runs = 300 # choose 1 to run the reference values
    # run_ncet(plant, path, orders, plant_fname, param_fname, BASIS_FNAME, mc_runs=mc_runs, make_building_table=False, save_all=True)

    print("--- %s seconds ---" % (datetime.datetime.now() - start_time))

    " Old way of running the code"
    # -------------------------------------------- Monte carlo run ---------------------------------------------#
    # mc_dict_list = [ [] for _ in range(orders)]

    # for i in range(monte_carlo_runs):
    #     df_scalars, scalars_dict = rand_input_scaling(param_fname, i, plant)

    #     # Get the direct costs
    #     scaling_table, plant_characteristics = fill_scaling_table.fill_scaling_table(path, plant_fname, base=BASIS_FNAME,
    #         scaling_table=df_scalars, scalars_dict=scalars_dict)

    #     dfNP = scale_direct_costs.scale_direct_costs(BASIS_FNAME, scaling_table, plant_characteristics, scalars_dict)

    #     dfNP, idx_modules = modularize.modularize(path, plant_fname, dfNP, orders, scalars_dict)
    #     newPlant_list, learning_rate = learn.learn(path, plant_fname, dfNP, orders, scalars_dict, idx_modules)
    #     scheduler_table = build_schedule_table(newPlant_list, i, scheduler_table)

    #     for j, dfNP in enumerate(newPlant_list):
    #         dfNP = get_indirect_costs.get_indirect_costs(dfNP, plant_characteristics, learning_rate[j], scalars_dict)
    #         dfNP = sum_accounts.sum_accounts(dfNP)
    #         dfNP.to_csv('./out/' + plant + '/raw/mc_' + plant + '_run' + str(i) + '_unit' + str(j+1) + '.csv')

    #         output_dict = build_mc_output_series(dfNP)
    #         output_dict['Run'] = i
    #         mc_dict_list[j].append(output_dict)

    # for i, dict_list in enumerate(mc_dict_list):
    #     pd.DataFrame(dict_list).to_csv('./out/' + plant + '/mc_output_' + plant + '_unit' + str(i+1) + '.csv')

    # scheduler_table.to_csv('./out/' + plant + '/mc_' + plant + '_scheduler_table.csv')
    # print("--- %s seconds ---" % (datetime.datetime.now() - start_time))

    # #-------------------------------------------- Case by case run ---------------------------------------------#
    # # Get direct costs for each case
    # for case in cases:
    #     # Create the input params df
    #     df_scalars, scalars_dict = update_input_scaling(param_fname, case)

    #     # Get the direct costs
    #     scaling_table, plant_characteristics = fill_scaling_table.fill_scaling_table(path, plant_fname, base=BASIS_FNAME,
    #         scaling_table=df_scalars, scalars_dict=scalars_dict)

    #     dfNP = scale_direct_costs.scale_direct_costs(BASIS_FNAME, scaling_table, plant_characteristics, scalars_dict)

    #     dfNP, idx_modules = modularize.modularize(path, plant_fname, dfNP, orders, scalars_dict)
    #     newPlant_list, learning_rate = learn.learn(path, plant_fname, dfNP, orders, scalars_dict, idx_modules)
    #     scheduler_table = build_schedule_table(newPlant_list, case, scheduler_table)

    #     for i, dfNP in enumerate(newPlant_list):
    #         dfNP = get_indirect_costs.get_indirect_costs(dfNP, plant_characteristics, learning_rate[i], scalars_dict)
    #         dfNP = sum_accounts.sum_accounts(dfNP)

    #         dfNP.to_csv('./out/' + plant + '/new' + plant + '_' + case + '_' + str(i) + '.csv')

    # scheduler_table.to_csv('./out/' + plant + '/' + plant + '_scheduler_table.csv')
