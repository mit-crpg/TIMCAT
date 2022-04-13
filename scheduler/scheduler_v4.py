import pandas as pd
import numpy as np
import bottleneck as bn
import time
import copy
import pdb
from pymoo_scheduler import sub_scheduler
from pymoo.algorithms.soo.nonconvex.ga import GA
from pymoo.optimize import minimize
from pymoo.util.termination.default import SingleObjectiveDefaultTermination
from pymoo.core.problem import Problem
import matplotlib.pyplot as plt
from scipy.special import gamma

class scheduler(Problem):
    def __init__(self, plant, unit, max_monthly_hires=800, peak_site_staff=4500):
        # Build the plant dataframe
        df = pd.read_csv('base_input.csv', dtype={'Task Length':float, 'Delay':float,'Start':float,'Status':float})
        assumption_df = pd.read_csv('./task_assumptions/' + plant + '.csv', dtype={'Fraction 1':float, 'Parallelism':float})
        df = df.merge(assumption_df, on='Account')
        hours_df = pd.read_csv('./scheduler_tables/' + plant + '_scheduler_table.csv')
        col = 'Hours run0_unit' + str(unit)
        hours_df.rename(columns={col:'Hours'}, inplace=True)
        df = df.merge(hours_df[['Account', 'Hours']], on='Account')
        df.to_csv('./created_inputs/input_df_' + plant + '_unit' + str(unit) + '.csv')
        
        #Precompute
        self.months = df['Hours'].values/160
        # Tasks that have zero hours set to launched/finished
        df['Launched'] = False
        df['Status']   = 0.0 
        df.loc[(df['Hours']<=3.0), 'Launched'] = True
        df.loc[(df['Hours']<=3.0), 'Status']   = 1.0
        
        # THIS IS CAUSING ISSUES IN COMPARING VECT AND EVAL_SCHED
        # Define a period as one month
        self.T = 500 #define max number of months
        df['Start'] = self.T #all accounts start at the end until launched
        df.loc[(df['Hours']<=3.0), 'Start']    = 0.0

        #Create an integer index arrary of the dependencies
        df['num'] = df.index.values
        dep = df['Dependency 1'].values
        df.set_index('Account', inplace=True)
        df['dep_idx'] = df.loc[dep, 'num'].values

        #Load the building worker limit constraint df
        fname = './building_constraints/' + plant + '_buildings.csv'
        bldg_df = pd.read_csv(fname, dtype={'Account': str, 'Area': float, 'Staff limit': float})
        bldg_list = []
        for bldg in bldg_df['Account']:
            bldg_list.append(list(df.loc[df['Building']==bldg, 'num'].values))

        # Some activities are done in parallel then placed with very heave lift crane
        self.parallelism = df['Parallelism'].values

        self.df = df
        dim = len(df)
        self.dim = dim
        self.bldg_df = bldg_df
        self.bldg_list = bldg_list

        self.task_length = df['Task Length'].values
        self.delay = df['Delay'].values

        # Default scheduling parameter
        self.max_monthly_hires = max_monthly_hires
        self.peak_site_staff  = peak_site_staff

        "Setup just for the pymoo full opt"
        task_length_min = np.ones(dim, dtype=int)*1
        task_length_max = np.ones(dim, dtype=int)*60

        delay_min = np.ones(dim, dtype=int)*0
        delay_max = np.ones(dim, dtype=int)*36
        super().__init__(n_var=2*dim, n_obj=1,
            xl=np.append(task_length_min, delay_min),
            xu=np.append(task_length_max, delay_max))

    def eval_sched(self, task_length=None, delay=None, completed_steps=[0,0], opt=False):
        if task_length is None:
            task_length=self.task_length
        if delay is None:
            delay = self.delay
        delay = np.absolute(delay)
        task_length = np.maximum(task_length,1)
        df = self.df.copy()
        bldg_list = self.bldg_list
        bldg_lims = self.bldg_df['Staff Limit'].values
        #Precompute
        months = self.months
        parallelism = self.parallelism

        T = self.T
        staffing   = np.zeros(T)
        derivative = np.zeros(T)
        bldgs      = np.zeros((T, len(bldg_lims)))

        #Turn the dataframe into numpy arrays
        launched = df['Launched'].values
        dep_idx  = df['dep_idx'].values #integer index of the dependencies
        fract1   = df['Fraction 1'].values
        start    = df['Start'].values # np.zeros_like(fract1)
        status   = df['Status'].values #  np.zeros_like(fract1)
        active   = np.zeros_like(start)
        staff    = months/task_length

        civil    = df['Civil'].values
        mech     = df['Mech'].values
        elect    = df['Elect'].values
        c_staff    = np.zeros(T)
        m_staff    = np.zeros(T)
        e_staff    = np.zeros(T)
        
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
            old_status = copy.deepcopy(status)
            progress = (i+1 - start - delay) / task_length
            status[active] = progress[active] 
            staffing[i] = active_staff.sum()
            
            for j, idxs in enumerate(bldg_list):
                bldgs[i,j] = bn.nansum(active_staff[idxs]/parallelism[idxs])
                # Goal is to create a subproblem at each timestep for each building
                #   Decision variables: task_length and delay for launched but nonstarted tasks
                if opt:
                    just_active =  any(start[idxs]==i)# a list of indices of just launched for the first time steps
                    launched_nonstarted = np.intersect1d(np.intersect1d(np.where(launched), idxs), np.where(old_status==0))
                    if (launched_nonstarted.size!=0) & just_active & (completed_steps[0]<=i) & (completed_steps[1]<=j):
                        print("Timestep: " + str(i))
                        # print(bldg_lims[j])
                        x0 = np.append(task_length[launched_nonstarted], (delay[launched_nonstarted] - (i-start[launched_nonstarted])))
                        # print("Length of x0: " + str(len(x0)))
                        " Use GWO from pagmo as I did before"
                        input_dict = {
                            "bldg_lim":            bldg_lims[j],
                            "task_length":         task_length,
                            "delay":               delay,
                            "launched_nonstarted": launched_nonstarted,
                            "min_delay":           (i-start[launched_nonstarted]),
                            "df":                  self.df,
                            "months":              self.months,
                            "idxs":                idxs,
                            "x0":                  x0,
                            "parallelism":         parallelism,
                            "max_monthly_hires":   self.max_monthly_hires,
                            "peak_site_staff":     self.peak_site_staff}
                        prob = sub_scheduler(input_dict)
                        " PYMOO METHOD "
                        algorithm = GA(pop_size=len(launched_nonstarted)*10)
                        pop = np.append(algorithm.setup(prob).ask().get("X"), np.atleast_2d(x0), axis=0)
                        algorithm = GA(pop_size=len(launched_nonstarted)*10+1, sampling=pop, eliminate_duplicates=True)
                        termination = SingleObjectiveDefaultTermination(
                            x_tol=1e-2, cv_tol=1e-2, f_tol=1e-2,n_max_gen=500, n_max_evals=20000)    
                        res = minimize(prob, algorithm, termination=termination, verbose=True)
                        x0 = res.X
                        task_length[launched_nonstarted] = np.round(x0[:len(x0)//2])
                        delay[launched_nonstarted]       = np.round((x0[len(x0)//2:])) + (i-start[launched_nonstarted])
                        # prob.vect_eval_sched_db(np.tile(x0, (1,1)))
                        # pdb.set_trace()
                        return task_length, delay, [i,j+1]
            
            # If we make it through the whole list of buildings, we have to reset j in "completed steps"
            if i>=completed_steps[0]:
                completed_steps = [i+1,0]
            
            c_staff[i] = (active_staff*civil).sum()
            m_staff[i] = (active_staff*mech).sum()
            e_staff[i] = (active_staff*elect).sum()

            i+=1
        derivative = staffing[1:] - staffing[:-1]
        df['Status']     = status
        df['Start']      = start
        df['Staffing']   = staff
        df['Delay']      = delay
        df['Task Length']= task_length
        
        return df, staffing, derivative, bldgs, c_staff, m_staff, e_staff

    def run_opt(self, max_iter=3, task_length=None, delay=None):
        if task_length is None:
            task_length = self.task_length
        if delay is None:
            delay       = self.delay
        iteration = 0
        while iteration < max_iter:
            print("Running iteration: " + str(iteration))
            i=0
            output = (task_length, delay, [0,0])
            while len(output)==3 and i < 200:
                print("Scheduler run: " + str(i))
                task_length, delay, completed_steps = output
                output = sched.eval_sched(task_length, delay, completed_steps, opt=True)
                i+=1
            iteration+=1
            df, staffing, derivative, bldgs, c_staff, m_staff, e_staff = output
            task_length = df['Task Length'].values
            delay = df['Delay'].values

        return df, staffing, derivative, bldgs
        
    def vect_full_sched(self, x0):
        "Vectorized version"
        runs = x0.shape[0]
        x0 = np.round(x0)
        task_length         = np.maximum(x0[:, :x0.shape[1]//2], 1)
        delay               = np.maximum(x0[:, x0.shape[1]//2:], 0)
    
        df = self.df.copy()
        T  = self.T

        #Turn the dataframe into numpy arrays
        launched = np.tile(df['Launched'].values, (runs,1))
        dep_idx  = df['dep_idx'].values #integer index of the dependencies
        fract1   = np.tile(df['Fraction 1'].values, (runs,1))
        start    = np.tile(df['Start'].values, (runs,1))
        status   = np.tile(df['Status'].values , (runs,1))
        active   = np.zeros_like(start)
        staff    = np.tile(self.months, (runs,1))/task_length
        bldg_list = self.bldg_list
        bldg_lims = self.bldg_df['Staff Limit'].values
        parallelism = self.parallelism

        "Comment this out if not evaluating the workloads"
        civil    = df['Civil'].values
        mech     = df['Mech'].values
        elect    = df['Elect'].values
        c_staff    = np.zeros((runs,T))
        m_staff    = np.zeros((runs,T))
        e_staff    = np.zeros((runs,T))
        
        staffing   = np.zeros((runs, T))
        overstaffed = np.zeros(runs)
        # Loop through each time period
        i = 0
        while status.min()<1.0 and i<T:
            # Get account lists for launched and not_launched
            not_launched = ~launched
            # Check non-launched accounts
            dep_1_status = (status[:, dep_idx] >= fract1)
            start[not_launched & dep_1_status] = i
            launched[not_launched] = dep_1_status[not_launched]

            # Setup active staffing based on launched and incomplete tasks
            active = (launched) & ((i - start) >= delay) & (status < 1) # boolean, 0 for not running, 1, for running
            
            # Advance launched accounts
            progress = np.divide((i+1 - start - delay), task_length )
            status[active] = progress[active]
            active_staff =  active * staff
            staffing[:, i] = np.sum(active_staff,axis=1)
            
            for j, idxs in enumerate(bldg_list):
                bldg_staffed = bn.nansum(active_staff[:, idxs]/parallelism[idxs], axis=1)
                overstaffed     += np.maximum(bldg_staffed - bldg_lims[j], 0)

            c_staff[:,i] = (active_staff*civil).sum(axis=1)
            m_staff[:,i] = (active_staff*mech).sum(axis=1)
            e_staff[:,i] = (active_staff*elect).sum(axis=1)

            i+=1
        
        total_months = (start + delay + task_length).max(axis=1)
        derivative = staffing[:, 1:] - staffing[:, :-1]
        # Smooth the derivative penalty
        if self.max_monthly_hires < 300:
            d_avg = (derivative[:, :-2] + derivative[:, 1:-1] + derivative[:, 2:])/3
            derivative_penalty = np.sum(np.maximum(np.absolute(d_avg) - self.max_monthly_hires,0), axis=1)
        else:
            derivative_penalty = np.sum(np.maximum(np.absolute(derivative) - self.max_monthly_hires,0), axis=1)
        max_staffing = staffing.max(axis=1)
        max_staffing_penalty = np.maximum(max_staffing - self.peak_site_staff,0)
        return total_months + derivative_penalty + overstaffed + max_staffing_penalty 

    def _evaluate(self, x0, out, *args, **kwargs):
        out["F"] = self.vect_full_sched(x0)
        return out

    def plot(self, case, fdetails):

        df = pd.read_csv('./subprob/df_'+ case + '_' + fdetails + '.csv')
        task_length = df['Task Length'].values.round()
        delay = df['Delay'].values.round()
        df, staffing, derivative, bldgs, c_staff, m_staff, e_staff = self.eval_sched(task_length, delay)
       
        fig = plt.figure(figsize=(7, 4))
        plt.plot(staffing, label='Total Staffing'); plt.plot(c_staff, label='Civil Staffing')
        plt.plot(m_staff, label='Mechanical Staffing');	plt.plot(e_staff, label='Electrical Staffing')
        plt.xlim(0,110); plt.ylim(0,4500)
        
        plt.legend(); plt.ylabel('Staffing'); plt.xlabel('Months'); plt.grid(True)
        plt.savefig('./plots/' + case + '_' + fdetails + '_simple.png')
        aux = pd.DataFrame()
        aux['Staffing'] = staffing
        aux['Civl']     = c_staff
        aux['Mech']     = m_staff
        aux['Elect']    = e_staff
        aux.to_csv('./subprob/df_'+ case + '_' + fdetails + '_staffing.csv')
        # plt.show()

if __name__ == '__main__':

    start_time = time.time()

    plants = ['MMNC_12_77']
    units  = [0,1,2,3,4,5,6,7,8,9]
    max_monthly_hires=800
    peak_site_staff=4500

    for plant in plants:
        print(plant)
        sched = scheduler(plant, unit=0, max_monthly_hires=max_monthly_hires, peak_site_staff=peak_site_staff)
        case = plant + '_unit0'
        "Full scale GA first"
        fdetails = 'fullGA_4500_800_v2'
        x0 = np.append(sched.task_length, sched.delay)
        algorithm = GA(pop_size=1000, eliminate_duplicates=True)
        termination = SingleObjectiveDefaultTermination(
            x_tol=1e-3, cv_tol=1e-3, f_tol=1e-3,n_max_gen=500, n_max_evals=700000)    
        res = minimize(sched, algorithm, termination=termination, verbose=True)
        df = sched.df
        df['Task Length'] = res.X[:res.X.shape[0]//2]
        df['Delay']       = res.X[res.X.shape[0]//2:]
        df.to_csv('./full_ga/df_' + case + '_' + fdetails + '.csv')
        unit0_task_length = res.X[:res.X.shape[0]//2]
        unit0_delay       = res.X[res.X.shape[0]//2:]
        for unit in units:
            print(plant)
            print(unit)
            case = plant + '_unit' + str(unit)
            sched = scheduler(plant, unit, max_monthly_hires=max_monthly_hires, peak_site_staff=peak_site_staff)

            " Now do the subproblem GA "
            fdetails = 'subprob_4500_800_v2'
            df, staffing, derivative, bldgs = sched.run_opt(max_iter=4, task_length=unit0_task_length, delay=unit0_delay)
            df.to_csv('./subprob/df_' + case + '_' + fdetails + '.csv')
            # pd.DataFrame(data=bldgs, columns=sched.bldg_df['Account'].values).to_csv('df_buildings_' + case + '_' + fdetails + '.csv')
            sched.plot(case, fdetails)
            
            print("--- %s seconds ---" % (time.time() - start_time))