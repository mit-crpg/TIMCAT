import pandas as pd
import numpy as np
import copy
import pdb

import numpy as np
from pymoo.core.problem import Problem

class sub_scheduler(Problem):

    def __init__(self, inputs):
        """ Inputs should be a dictionary with: , started_tl; 
            started_dl, sub_status, sub_months, sub_parallel, 
            bldg_lim, task_length, delay, launched_nonstarted, min_delay, df """
        for key in inputs:
            setattr(self, key, inputs[key])

        dim = len(self.launched_nonstarted)

        task_length_min = np.ones(dim, dtype=int)*1
        task_length_max = np.ones(dim, dtype=int)*60

        delay_min = np.ones(dim, dtype=int)*0
        delay_max = np.ones(dim, dtype=int)*36

        super().__init__(n_var=2*dim,
                         n_obj=1,
                         xl=np.append(task_length_min, delay_min),
                         xu=np.append(task_length_max, delay_max))

    def _evaluate(self, x0, out, *args, **kwargs):
        out["F"] = self.vect_eval_sched(x0)
        return out

    def vect_eval_sched(self, x0):
        "Vectorized version"
        runs = x0.shape[0]
        task_length         = np.tile(self.task_length, (runs,1))
        delay               = np.tile(self.delay, (runs,1))
        launched_nonstarted = self.launched_nonstarted
    
        task_length[:, launched_nonstarted] = x0[:, :x0.shape[1]//2]
        delay[:, launched_nonstarted]       = x0[:, x0.shape[1]//2:] + np.tile(self.min_delay, (runs,1)) #delay parameter can't be less than the current month

        delay       = np.round(np.maximum(delay, 0))
        task_length = np.round(np.maximum(task_length,1))

        df = self.df.copy()
        T = 500

        #Turn the dataframe into numpy arrays
        launched = np.tile(df['Launched'].values, (runs,1))
        dep_idx  = df['dep_idx'].values #integer index of the dependencies
        fract1   = np.tile(df['Fraction 1'].values, (runs,1))
        start    = np.tile(df['Start'].values, (runs,1))
        status   = np.tile(df['Status'].values , (runs,1))
        active   = np.zeros_like(start)
        staff    = np.tile(self.months, (runs,1))/task_length

        staffing   = np.zeros((runs, T))
        derivative = np.zeros((runs, T))
        bldg_staffing= np.zeros((runs, T))

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
            bldg_staffing[:, i] = (active_staff[:, self.idxs]/self.parallelism[self.idxs]).sum(axis=1) 

            i+=1
        
        total_months = (start + delay + task_length).max(axis=1)
        derivative = staffing[:, 1:] - staffing[:, :-1]
        if self.max_monthly_hires < 300:
            d_avg = (derivative[:, :-2] + derivative[:, 1:-1] + derivative[:, 2:])/3
            derivative_penalty = np.sum(np.maximum(np.absolute(d_avg) - self.max_monthly_hires,0), axis=1)
        else:
            derivative_penalty = np.sum(np.maximum(np.absolute(derivative) - self.max_monthly_hires,0), axis=1)
        
        max_staffing_penalty = np.maximum(staffing.max(axis=1) - self.peak_site_staff,0)
        subproblem_time = np.max((task_length[:,launched_nonstarted] + delay[:,launched_nonstarted] + start[:,launched_nonstarted]), axis=1)
        overstaffed = np.sum(np.maximum(bldg_staffing - self.bldg_lim,0), axis=1)

        return total_months + derivative_penalty**2 + subproblem_time + overstaffed**2 + max_staffing_penalty**2

        
