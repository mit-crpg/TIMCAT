import pandas as pd

def material_use_uncertainty(scaling_table, scalars_dict):
	#--------------------------------------------- Scale the baseline database ------------------------------------#
	mat_keys = [x for x in scalars_dict.keys() if '[Material]' in x]

	for mat_key in mat_keys:
		account = mat_key.split(']')[1].split(':')[0].strip()
		idx = scaling_table.index.str.match(account)
		scaling_table.loc[idx, 'New Base Unit Value'] *= scalars_dict[mat_key]

	return scaling_table