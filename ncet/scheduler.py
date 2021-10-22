import numpy as np
import pandas as pd
import pdb
import matplotlib.pyplot as plt
import pygmo as pg
import bottleneck as bn
import time

class scheduler:
	def __init__(self, case, new_plant=False):
		fname = case + '.csv'
		df = pd.read_csv(fname, dtype={'Hours':float,'Fraction 1':float,'Staffing':float,'Delay':float,'Start':float,'Status':float,'Derivative':float})
		#Precompute
		self.months = df['Hours'].values/160
		# Tasks that have zero hours set to launched/finished
		df.loc[(df['Hours']==0), 'Launched'] = True
		df.loc[(df['Hours']==0), 'Status']   = 1
		# Define a period as one month
		self.T = 250 #define max number of months
		df['Start'] = self.T #all accounts start at the end until launched

		#Create an integer index arrary of the dependencies
		df['num'] = df.index.values
		dep = df['Dependency 1'].values
		df.set_index('Account', inplace=True)
		df['dep_idx'] = df.loc[dep, 'num'].values

		#Load the building worker limit constraint df
		fname = case + '_buildings.csv'
		bldg_df = pd.read_csv(fname, dtype={'Account': str, 'Area': float, 'Staff limit': float})
		bldg_list = []
		for bldg in bldg_df['Account']:
			bldg_list.append(list(df.loc[df['Building']==bldg, 'num'].values))
		# accounts_212 = df.index.str.contains('A.212')
		self.idx_212     = np.where(bldg_df['Account']== 'A.212.')[0][0]
		self.idx_212_142 = np.where(df.index== 'A.212.142')[0][0]

		# Some activities are done in parallel then placed with very heave lift crane
		self.parallelism = df['Parallelism'].values

		self.df = df
		self.dim = len(df)
		self.bldg_df = bldg_df
		self.bldg_list = bldg_list

		self.counter = 0
		self.x0_hist = []

		self.new_plant = new_plant

	def get_bounds(self):
		
		dim = self.dim
		task_length_min = np.ones(dim, dtype=int)*1
		task_length_max = np.ones(dim, dtype=int)*48

		delay_min = np.ones(dim, dtype=int)*0
		delay_max = np.ones(dim, dtype=int)*36

		return (np.ravel(tuple(zip(task_length_min,delay_min))), np.ravel(tuple(zip(task_length_max,delay_max))))
		
	def get_nix(self):
		return 2*self.dim

	def eval_sched(self, task_length, delay, return_df):
		df = self.df.copy()
		bldg_list = self.bldg_list
		bldg_lims = self.bldg_df['Staff Limit'].values
		bldg_overstaffed = np.zeros(len(bldg_list))
		#Precompute
		months = self.months
		parallelism = self.parallelism
		
		T = self.T
		staffing   = np.zeros(T)
		c_staff    = np.zeros(T)
		m_staff    = np.zeros(T)
		e_staff    = np.zeros(T)
		derivative = np.zeros(T)

		#Turn the dataframe into numpy arrays
		launched = df['Launched'].values
		dep_idx  = df['dep_idx'].values #integer index of the dependencies
		fract1   = df['Fraction 1'].values
		start    = df['Start'].values
		status   = df['Status'].values 
		civil    = df['Civil'].values
		mech     = df['Mech'].values
		elect    = df['Elect'].values
		active   = np.zeros_like(start)
		staff    = months/task_length

		tstart = start

		# Loop through each time period
		i = 0
		while status.min()<1.0 and i<T:
			# Get account lists for launched and not_launched
			not_launched = ~launched
			# Check non-launched accounts
			dep_1_status = (status[dep_idx] >= fract1)
			start[not_launched & dep_1_status] = i
			launched[not_launched] = dep_1_status[not_launched]

			# Setup active staffing based on launched and incomplete tasks
			active = (launched) & ((i - start) >= delay) & (status < 1) # boolean, 0 for not running, 1, for running
			active_staff = active * staff
			
			# Advance launched accounts
			old_status = status
			progress = (i - start - delay) / task_length
			status[active] = progress[active] 

			staffing[i] = active_staff.sum()
			derivative[i] = staffing[i] - staffing[max(i-1, 0)]
			# pdb.set_trace()
			c_staff[i] = bn.nansum(active_staff*civil)
			m_staff[i] = bn.nansum(active_staff*mech)
			e_staff[i] = bn.nansum(active_staff*elect)

			for j, idxs in enumerate(bldg_list):
				bldg_staffing = bn.nansum(active_staff[idxs]/parallelism[idxs])
				if bldg_staffing > bldg_lims[j]:
					# if j==18:
					# 	pdb.set_trace()
					# 	print(bldg_staffing - bldg_lims[j])
					bldg_overstaffed[j] += bldg_staffing - bldg_lims[j]
				
			i+=1
		
		if return_df:
			df['Status']     = status
			df['Start']      = start
			df['Staffing']   = staff
			df['Delay']      = delay
			df['Task Length']= task_length
			
			return df, staffing, derivative, bldg_overstaffed, c_staff, m_staff, e_staff
		else:
			return status, staffing, derivative, bldg_overstaffed, c_staff, m_staff, e_staff


	def fitness(self, x0, return_df=False):
		x0 = np.round(x0, decimals=0)
		task_length  = x0[::2]
		delay  = x0[1::2]

		# df_mebe = pd.read_csv('ME_over_BE.csv')
		# mult = df_mebe['ME/BE'].values
		# task_length = np.ceil(task_length * mult)
        
		if return_df:
			df, staffing, derivative, bldg_overstaffed, c_staff, m_staff, e_staff = self.eval_sched(task_length, delay, return_df)
			status = df['Status'].values
		else:
			status, staffing, derivative, bldg_overstaffed, c_staff, m_staff, e_staff = self.eval_sched(task_length, delay, return_df)
		
        # Objective function - minimize time
		t_end = np.max(np.nonzero(staffing)) #should be index (month) of the last working month
		f = t_end**2

		# Penalty for hiring/firing workers too quickly
		max_derivative = np.abs(derivative[2:]).max() #don't include the first month
		if max_derivative > 800:
			f += (max_derivative-800.)**2
		
		# # Penalty for overstaffing the site
		# max_staffing   = staffing.max()
		# if max_staffing > 2500:
		# 	f += (max_staffing-1500.)

		# Penalty for not finishing buildings
		not_finished = self.dim - status.sum()
		if not_finished > 0: 
			f += (10*not_finished)**2 #10x mult is to get it on equal scale with objective function

		# Apply building staffing constraint
		overstaffed = np.sum(bldg_overstaffed)
		f += 20*overstaffed

		if return_df:
			pdb.set_trace()
			return f, df, staffing, derivative, c_staff, m_staff, e_staff
		else:
			return np.array([f])

if __name__ == '__main__':

	start_time = time.time()
	"---------------------------------Run the optimizer for new plant---------------------------------"
	# case = 'SMR160_20-OAK'
	# case = 'ABWR_10-OAK'
	# case = 'PWR12ME'
	case = 'AP1000_1-OAK'
	run = '_4'

    # Build the problem
	prob = pg.problem(scheduler(case, new_plant=True))
	# algo = pg.algorithm(pg.sga(gen = 701))#, mutation = 'gaussian', crossover = 'binomial', m = 0.02, param_m=.125))
	algo = pg.algorithm(pg.gwo(gen = 1500))
	algo.set_verbosity(50)
	pop = pg.population(prob, size=450)

	# Load previous population
	# df = pd.read_csv('best_runs.csv')
	# for i in range(len(df.columns)-1):
	# 	pop.set_x(i, df[str(i)].iloc[:-1])

    # Evolve the population
	pop = algo.evolve(pop)
	
    # Save the output
	f = pop.get_f()
	f_df = pd.DataFrame.from_dict(dict(zip(np.arange(0, len(f), 1), f)))
	x = pop.get_x()
	x_df = pd.DataFrame.from_dict(dict(zip(np.arange(0, len(x), 1), x)))
	pd.concat([x_df, f_df]).to_csv('./' + case + '/' + case + run + 'last_gen.csv')

	print("--- %s seconds ---" % (time.time() - start_time))

	"---------------------------------Run & visualize last generation---------------------------------"

	sched = scheduler(case, new_plant=True)
	df = pd.read_csv('./' + case + '/' + case + run + 'last_gen.csv')
	x0 = df['0'].values[0:-1]
	f, df, staffing, derivative, c_staff, m_staff, e_staff = sched.fitness(x0, return_df=True)

	fig = plt.figure(figsize=(7, 4))
	plt.plot(staffing, label='Total Staffing'); plt.plot(c_staff, label='Civil Staffing')
	plt.plot(m_staff, label='Mechanical Staffing');	plt.plot(e_staff, label='Electrical Staffing')
	plt.legend(); plt.ylabel('Staffing'); plt.xlabel('Months'); plt.grid(True)
	plt.xlim(0,110); plt.ylim(0,4500)
	

	plt.savefig('./' + case + '/' + case + run + '.png')
	df.to_csv('./' + case + '/' + case + run + '_out.csv')
	pd.DataFrame({'Civil':c_staff, 'Mechanical':m_staff, 'Electrical':e_staff}).to_csv('./' + case + '/' + 'out_staffing_' + case + run + '.csv')


	# fig, (ax1, ax2) = plt.subplots(2, figsize=(7, 5))
	# ax1.plot(staffing, label='Total Staffing')
	# ax1.plot(c_staff, label='Civil Staffing');	ax1.plot(m_staff, label='Mechanical Staffing');	ax1.plot(e_staff, label='Electrical Staffing')
	# ax1.legend(); ax1.set_ylabel('Staffing'); ax1.grid(True)
	# ax1.set_xlim(0,110)
	# ax1.set_ylim(0,3000)
	# ax2.plot(derivative); ax2.set_xlabel('Months'); ax2.set_ylabel('Derivative'); ax2.grid(True)
	# ax2.set_xlim(0,110)