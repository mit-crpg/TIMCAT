import pandas as pd
import numpy as np
from os.path import join as pjoin


def learn(path, fname, dfNewPlant, orders, scalars_dict, idx_modules):

    # -------------------------------------------- APPLYING LEARNING ---------------------------------------------#
    print("Learning accounts")
    learning_table = pd.read_excel(
        pjoin(path, fname), header=0, sheet_name="Learning", index_col="Account"
    )
    newPlant_list = []
    plants = np.arange(orders) + 1
    dfNewPlant["Count per plant"].fillna(1, inplace=True)

    # learning rates and max cost reduction
    fact_rate = scalars_dict["Factory learning rate"]  # 0.16
    fact_N0 = 100
    mat_rate = scalars_dict["Material learning rate"]  # 0.071
    lab_rate = scalars_dict["Labor learning rate"]  # 0.131
    lab_min = scalars_dict["Labor minimum"]  # 0.55
    mat_min = scalars_dict["Material minimum"]  # 0.73
    mat_learning_factor = np.maximum(
        mat_min, plants ** np.log2(1 - mat_rate)
    )  # learning rate at  9%, max reduction 27%
    lab_learning_factor = np.maximum(lab_min, plants**np.log2(1-lab_rate))

    cpp = dfNewPlant["Count per plant"].astype(int)  # count per plant
    dfNewPlant["Initial unit"] = 1
    for account in learning_table.index:
        dfNewPlant.loc[
            dfNewPlant.index.str.match(account), "Initial unit"
        ] = learning_table.at[account, "Initial unit number"]
    i_unit = dfNewPlant["Initial unit"].astype(int)  # initial unit for each col
    dfNewPlant["fact_N0"] = fact_N0
    dfNewPlant.loc[
        idx_modules, "fact_N0"
    ] = 1  # baseline first unit cost reference number (reset to 1 for new modules)
    df_learn = pd.concat([cpp, i_unit, dfNewPlant["fact_N0"]], axis=1)
    df_learn["counts"] = df_learn.apply(
        lambda row: np.linspace(
            row["Initial unit"],
            row["Initial unit"] + row["Count per plant"] - 1,
            row["Initial unit"] + row["Count per plant"] - 1,
        ),
        axis=1,
    )
    newPlant_list = []
    for i in range(orders):
        df = dfNewPlant.copy()

        df["lab_learning_factor"] = df_learn["counts"].apply(
            lambda x: np.mean(np.maximum(lab_min, x ** np.log2(1 - lab_rate)))
        )
        df["mat_learning_factor"] = df_learn["counts"].apply(
            lambda x: np.mean(np.maximum(mat_min, x ** np.log2(1 - mat_rate)))
        )
        df["fact_learning_factor"] = df_learn.apply(
            lambda row: np.mean(
                (row["counts"] + row["fact_N0"] - 1) ** np.log2(1 - fact_rate)
                / (row["fact_N0"]) ** np.log2(1 - fact_rate)
            ),
            axis=1,
        )

        df["Factory Equipment Cost"] *= df["fact_learning_factor"]
        df["Site Labor Cost"] *= df["lab_learning_factor"]
        df["Site Labor Hours"] *= df["lab_learning_factor"]
        df["Site Material Cost"] *= df["mat_learning_factor"]

        df["Total Cost"] = (
            df["Site Material Cost"].values
            + df["Site Labor Cost"].values
            + df["Factory Equipment Cost"].values
        )
        df_learn["counts"] += cpp
        newPlant_list.append(df)

    return newPlant_list, lab_learning_factor
