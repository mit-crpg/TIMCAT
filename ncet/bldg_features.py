import numpy as np

def get_bldg(aux, dimensions):
	dimensions = [float(i) for i in dimensions]
	shape = aux['Shape']
	tf    = aux['Foundation thickness (meters)']
	tw    = aux['Superstructure thickness (meters)']

	#-----Superstucture-----
	superArea = {
		'Cylinder':	        lambda d, h, u: np.pi*d*h,          			  #u for unused
		'Rectangular':      lambda x, y, h: x*h*2 + y*h*2,
		'Cylinder w/ dome': lambda d, h, u: 4*np.pi * d**2/4 / 2 + np.pi*d*h #u for unused
		}[shape](*dimensions)
	superVol = superArea * tw

	#-----Building Volume-----
	bv = {
		'Cylinder':	        lambda d, h, u: np.pi*d**2/4*h,                        #u for unused
		'Rectangular':      lambda x, y, h: x*y*h,
		'Cylinder w/ dome': lambda d, h, u: np.pi * 1/6 * d**3 /2 + np.pi*d**2/4*h #u for unused
		}[shape](*dimensions)

	#-----Substructure-----
	subArea = {
		'Cylinder':	        lambda d, h, u: np.pi*d**2/4, #u for unused
		'Cylinder w/ dome': lambda d, h, u: np.pi*d**2/4, #u for unused
		'Rectangular':      lambda x, y, h: x*y
		}[shape](*dimensions)
	subVol = subArea * tf

	return subArea, subVol, superArea, superVol, bv

def eval_bldg(portions, aux):
	if portions==1:
		dimensions = aux['Dimensions (meters)'].replace('[','').replace(']','').split(',')
		tot_subArea, tot_subVol, tot_superArea, tot_superVol, tot_bv = get_bldg(aux, dimensions)
	else:
		tot_subArea = 0; tot_subVol = 0; tot_superArea = 0; tot_superVol = 0; tot_bv = 0
		dimension_list = aux['Dimensions (meters)'].split(';')
		for i in range(portions):
			dimensions = dimension_list[i].replace('[','').replace(']','').split(',')
			subArea, subVol, superArea, superVol, bv = get_bldg(aux, dimensions)
			tot_subArea   = tot_subArea + subArea
			tot_subVol    = tot_subVol + subVol
			tot_superArea = tot_superArea + superArea
			tot_superVol  = tot_superVol + superVol
			tot_bv        = tot_bv + bv 
				
	return tot_subArea, tot_subVol, tot_superArea, tot_superVol, tot_bv