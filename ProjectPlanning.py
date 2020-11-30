
__author__ = 'Andrea Chiappo'
__email__ = 'chiappo.andrea@gmail.com'

import numpy as np
import matplotlib.dates as mdates
from datetime import datetime
from scipy.integrate import quad
from more_itertools import random_combination

from scipy.interpolate import InterpolatedUnivariateSpline

###############################################################################

def dataframe_to_dictionary(projects_df, scale=1):
    """ 
    function to cast a pandas dataframe to a dictionary
     
     input
      - projects pandas DataFrame
      - scale factor to rescale data (optional)
     
     output
     - dictionary of dictionaries
       (keys of father dictionary are the projects' name
        while values contains a dictionary with the projects' data)
    
    """
    # initialise empty dictionary
    projects = {}
    # get years list
    ind = [ln for ln in projects_df.index.values[2:]]
    Dyears = [datetime(int(idx.split(' ')[-1]),1,1).date() for idx in ind]
    # convert years list to number representation - for interpolation purposes
    Nyears = np.array([mdates.date2num(yy) for yy in Dyears])
    # extract each project's data
    for p in projects_df.columns.values:
        # get project data
        project = projects_df[p].to_numpy(dtype=float)
        # initialise individual project dictionary
        project_dict = {}
        # get earliest spud year
        project_dict['spud'] = int(project[0])
        # get drilling duration
        project_dict['drill'] = int(project[1])
        # get production profile
        prod_profile = project[2:] 
        # retain only non-zero years
        non_zero_years = np.nonzero(prod_profile)
        prod_profile = prod_profile[non_zero_years]
        # rescale production profile
        prod_profile *= scale
        project_dict['profile'] = prod_profile
        # get effective production years
        years = Nyears[non_zero_years]
        project_dict['years'] = years
        # interpolate yearly production profile
        curve = InterpolatedUnivariateSpline(years, prod_profile)
        # save interpolation object
        project_dict['curve'] = curve
        # append to father dictionary
        projects[p] = project_dict
    
    return projects

###############################################################################

class Projects(object):
    """
     Projects base class  
     
     Contains methods to calculate useful metrics of the considered projects:  
      - maximum production profiles' value
      - projects' effective production (over the considered time range)
      - projects' total production (integrated over the considered time range)
      - projects' peak production absolute ordering and relative to global mean
     
    """
    
    def __init__(self, period, projects, **kwargs):
        self.period = period
        self.projects = projects
        self.projects_names = np.array(list(projects.keys()))
        
        # indices selecting the projects' operation period
        # (to calculate effective and total productions)
        self.min_year = kwargs['min_year'] if 'min_year' in kwargs else 0
        self.max_year = kwargs['max_year'] if 'max_year' in kwargs else -1
        
        # attributes for possible alternative project planning algorithms
        self.first_project = kwargs['first_project'] if 'first_project' in kwargs else 'mean'
        self.next_project = kwargs['next_project'] if 'next_project' in kwargs else 'mean'
        self.initial_iters = kwargs['initial_iters'] if 'initial_iters' in kwargs else 1000
        
        # call local methods to estimate metrics
        self.projects_max_prod()
        self.projects_total_prod() 
        self.projects_effective_prod()
        self.global_mean = self.total_prod / period
        self.projects_prod_diff()
        
    def projects_max_prod(self):
        """
         Function to calculate peak production of all projects  
         (achieved on the first operation day)
        """
        max_prod = []
        for project in self.projects.values():
            max_prod_profile = project['profile']
            project['max'] = max_prod_profile[0] 
            max_prod.append(max_prod_profile[0])
        self.max_project_prod = np.array(max_prod)
    
    def projects_effective_prod(self):
        """
         Function to calculate effective production of all projects  
         (calculating interpolation object over operation period)
        """
        for project in self.projects.values():
            years = project['years']
            prof_curve = project['curve']
            iyear = years[self.min_year]
            fyear = years[self.max_year]
            yrange = np.arange(iyear,fyear)
            effective_prod = prof_curve(yrange)
            project['effective'] = effective_prod
    
    def projects_total_prod(self):
        """
         Function to calculate each project's total production 
         (integrating interpolation object over operation period)
         and the cumulative portfolio total production
        """
        T = 0 
        for project in self.projects.values():
            years = project['years']
            iyear = years[self.min_year]
            fyear = years[self.max_year]
            prof_curve = project['curve']
            proj_tot_prod = quad(prof_curve, iyear, fyear)[0]
            project['total'] = proj_tot_prod
            T += proj_tot_prod
        self.total_prod = T
    
    def projects_prod_diff(self):
        """
        Function to calculate the projects ordering 
         - relative to the global production averaged over the whole period 
         - absolute ordering
        """
        # get projects ordering relative the global mean
        prod_diffs_rel = np.abs(self.max_project_prod - self.global_mean)
        order_indxs_rel = np.argsort(prod_diffs_rel)
        order_projects_names_rel = self.projects_names[order_indxs_rel]
        self.order_projects_names_rel = order_projects_names_rel
        # get projects absolute ordering for max production
        prod_diffs_abs = self.max_project_prod
        order_indxs_abs = np.argsort(prod_diffs_abs)
        order_projects_names_abs = self.projects_names[order_indxs_abs]
        self.order_projects_names_abs = order_projects_names_abs

class Projects_Planner(Projects):
    """
     Project Planner class
     
     This class collects the methods to operate with the portfolio projects
     Specifically, the moethods contained can be used to  
      - search for a candidate first or collection of projects
      - search a successive project to execute 
      - find the projects' optimal ordering
      - add projects to the execution list
      - add projects to the execution sequence
      - remove projects from the execution lists
      - clear projects execution lists
      - update projects execution lists
      - calculate daily production (using active projects)
    
    """
    
    def __init__(self, first_day, period, projects, **kwargs):
        super(Projects_Planner, self).__init__(period, projects, **kwargs)   
        
        # ascertain that projects is a dictionary
        assert isinstance(projects, dict), "projects must be a dictionary!"
        
        # define operational attributes
        self.call = 0
        self.projects_length = len(projects)
        self.used_projects = np.array([])
        self.projects_time_sequence = []
        self.active_projects = np.array([])
        self.projects_first_day = np.array([])
        
        # time reference attributes
        self.first_day = first_day
        first_year = mdates.num2date(self.first_day).date().year
        self.first_year = first_year
    
    def search_first_project(self):
        """
         Function to search for the first project to execute and 
         add it to the execution list
         
         Three possible scenarios avaialable, controlled by the 
         argument 'first_project':
          - 'mean' = search for the combinations of projects whose sum of  
                     maximum (initial) values is closest to the global mean
                     (default option)
          - 'minmax' = search for the project which yields the highest 
                       maximum (initial) value
          - None = simpy return a project randomly chosen
         
         All three cases allow for iteration over the list of proposed 
         projects in search for the candidate complying with the requirement 
         that the project's spud year must be smaller than the initial year
        """
        if self.first_project=='mean':
            # get portfolio project's indices list
            initial_indx = range(self.projects_length)

            # calculate N=initial_iters possible combinations of possible
            # initial projects
            combs_sum = []
            combs_ind = []
            for it in range(self.initial_iters):
                random_length = np.random.choice(self.projects_length)
                indxs = random_combination(initial_indx,random_length)
                combs_ind.append(indxs)
                combs_sum.append(self.max_project_prod[list(indxs)].sum())

            # search for projects' combination summing closest to global mean
            combs_mean_diff = np.abs(np.array(combs_sum) - self.global_mean)
            sort_indxs = combs_mean_diff.argsort()
            
            # iteratively search for compliance with spud year requirement
            n = 0
            found = False
            while not found:
                projects_indxs = combs_ind[sort_indxs[n]]
                projects = [self.projects_names[ind] for ind in projects_indxs]
                spud_years = [self.projects[p]['spud'] for p in projects]
                if all(np.array(spud_years) < self.first_year):
                    found = True
                n += 1 
            
        elif self.first_project=='minmax':
            # sort proejcts' production maxima
            max_project_prod_sort = self.max_project_prod.argsort()
            
            # iteratively search for compliance with spud year requirement
            n = -1
            found = False
            while not found:
                ind = max_project_prod_sort[n]
                projects = self.order_projects_names_abs[ind]
                if self.projects[projects]['spud'] <= self.first_year:
                    found = True
                n -= 1
            
        else:
            # iteratively search for compliance with spud year requirement
            found = False
            while not found:
                n = np.random.choice(self.projects_length)
                projects = self.projects_names[n]
                if self.projects[projects]['spud'] < self.first_year:
                    found = True
        
        first_day = 0
        self.add_projects(projects, first_day)

    def search_next_project(self, day, last_prod):
        """
         Function to search for successive project to execute. 
         Analogously to search_first_project(), three options are available
          - 'mean' = search for project whose initial top production is 
                     closest to the last daily portfolio production
          - 'minmax' = alternate between the project having the smallest 
                       and highest initial porduction
          - None = randomdly select a project from the available ones
         
         All three cases allow for iteration over the list of proposed 
         projects in search for the candidate complying with the requirement 
         that the project's spud year must be smaller or equal to the initial  
         year. The present iteration allows for the possibility that 
         a project's spud year is the current one, but checks that the 
         drilling occured within the present year.
        """
        current_day = self.first_day+day
        current_year = mdates.num2date(current_day).date().year
        # determine available (unused) projects 
        left_projects_ind = ~np.in1d(self.projects_names, self.used_projects)
        left_projects_name = self.projects_names[left_projects_ind]
        
        if self.next_project=='mean':
            # determine difference of last production point from global mean
            last_mean_diff = last_prod - self.global_mean
            last_prod_diffs = self.max_project_prod + last_mean_diff
            # order remaining projects using the difference between
            # their max production, the last production and the mean
            new_project_prod = last_prod_diffs[left_projects_ind]
            new_project_prod_ind = new_project_prod.argsort()[::-1]
            new_project_name_ord = left_projects_name[new_project_prod_ind]

            # iteratively search for compliance with spud year requirement
            n = 0
            found = False
            while not found:
                project = new_project_name_ord[n]
                spud_year = self.projects[project]['spud']
                drill = self.projects[project]['drill']
                spud_date = mdates.num2date(current_day-drill).date().year
                if spud_year <= current_year <= spud_date:
                    found = True
                n += 1 
            self.add_projects(project, day)
            
        elif self.next_project=='minmax':
            self.call += 1 
            # determine peak production of left projects
            new_project_prod = self.max_project_prod[left_projects_ind]
            new_project_prod_ind = new_project_prod.argsort()
            new_project_name_ord = left_projects_name[new_project_prod_ind]
            
            # return a maximum in the peak production list
            if self.call % 2 == 0: 
                # iteratively search for compliance with spud year requirement
                n = -1
                found = False
                while not found:
                    project = new_project_name_ord[n]
                    drill = self.projects[project]['drill']
                    spud_date = mdates.num2date(current_day-drill).date().year
                    if spud_year <= current_year <= spud_date:
                        found = True
                    n -= 1 
            
            # return a minimum in the peak production list
            else:
                # iteratively search for compliance with spud year requirement
                n = 0
                found = False
                while not found:
                    project = new_project_name_ord[n]
                    drill = self.projects[project]['drill']
                    spud_date = mdates.num2date(current_day-drill).date().year
                    if spud_year <= current_year <= spud_date:
                        found = True
                    n += 1 
            self.add_projects(project, day)
            
        else:
            # iteratively search for compliance with spud year requirement
            found = False
            left_porjects_num = range(len(left_projects_name))
            while not found:
                n = np.random.choice(left_porjects_num)
                project = left_projects_name[n]
                if self.projects[project]['spud'] <= year:
                    found = True
            self.add_projects(project, day)
    
    def projects_ordering(self):
        """
         Function to search for the projects' order leading to the maximum 
         production during the operation phase. 
         Returns the sequence of projects and their execution day
         
         Scheme:
          - split portfolio projects based on earlier spud year
          - consider projects with spud year earlier than period start
          - order resulting projects in decreasing total production 
          - order resulting projects in decreasing drill duration
          - starting from longest drilling project(s), populate the 
            projects sequence including the new projects and subtracting 
            the drilling time from the period start date
          - consider projects with spud year later or equal than period start
          - order resulting projects in decreasing total production
          - order resulting projects in decreasing drill duration
          - starting from longest drilling project(s), populate the 
            projects sequence inclduing the new projects and adding 
            the drilling time to the period start date
          - combine to the sequences
        
        """
        # get initial lists of indices, spud years, drilling time and totals
        indxs = np.arange(self.projects_length)
        spuds = np.array([pr['spud'] for pr in self.projects.values()])
        drill = np.array([pr['drill'] for pr in self.projects.values()])
        totals = np.array([pr['total'] for pr in self.projects.values()])
        
        # consider only projects with spud year earlier than period start
        before = np.where(spuds<self.first_year)[0]
        indxs_before = indxs[before]
        drill_before = drill[before]
        totals_before = totals[before]

        # order projects in decreasing total production
        order = totals_before.argsort()[::-1]
        indxs_order = indxs_before[order]
        drill_order = drill_before[order]

        # order projects in decreasing drill duration
        unique_drills = np.unique(drill_order)
        days_before = max(unique_drills)
        ind_sequence_before = []
        for dr in np.sort(unique_drills)[::-1]:
            ind_drill = np.where(drill_order==dr)[0]
            ind_sequence_before.append(indxs_order[ind_drill])

        proj_sequence_before = []
        # build sequence of projects than can execute before period start
        n = 0
        for day in range(days_before):
            for ind in ind_sequence_before:
                if (days_before-day) == drill[ind[0]]:
                    for dd,ii in enumerate(ind):
                        exec_day = days_before-day-dd
                        proj_sequence_before.append((-exec_day, ii))
        #----------------------------------------------------------------------
        # consider only projects with spud year later/equal than period start
        after = np.where(spuds>=self.first_year)[0]
        indxs_after = indxs[after]
        drill_after = drill[after]
        totals_after = totals[after]

        # order projects in decreasing total production
        new_order = totals_after.argsort()[::-1]
        indxs_new_order = indxs_after[new_order]
        drill_new_order = drill_after[new_order]

        # order projects in decreasing drill duration
        unique_drills = np.unique(drill_new_order)
        days_after = len(drill_new_order)
        ind_sequence_after = []
        for dr in np.sort(unique_drills)[::-1]:
            ind_drill = np.where(drill_new_order==dr)[0]
            ind_sequence_after.append(indxs_new_order[ind_drill])

        ind_sequence_after = np.hstack(ind_sequence_after)
        
        proj_sequence_after = []
        # build sequence of projects than can execute after period start
        n = 0
        for day in range(days_after):
            exec_day = day
            ii = ind_sequence_after[n]
            proj_sequence_after.append((exec_day, ii))
            n += 1
        
        # combine two sequences to obtain complete projects' sequence
        self.projects_sequence = [*proj_sequence_before,*proj_sequence_after]
        
    def add_projects(self, projects, first_day):
        """
         Function to add projects to the lists of executable projects on 
         a given day. 
          input:
           - project(s) name (can be a list or a string)
           - first operations day of the project(s) added
         
         Three operational lists:
          - used_projects = collects all projects used over entire period
          - active_projects = collects only projects currently active 
          - projects_first_day = collects the projects' operation starting day
        
        """
        if not isinstance(projects, list):
            projects = [projects]
        
        for project in projects:
            assert project not in self.used_projects, "Project already used!"
            self.add_project_sequence(project, first_day)
            self.used_projects = np.append(self.used_projects, project)
            self.active_projects = np.append(self.active_projects, project)
            self.projects_first_day = np.append(self.projects_first_day, first_day)
    
    def add_project_sequence(self, project, first_day):
        """
         Function to populate the list of executed projects
         including the execution day and the project name
         
         input: 
           - project name
           - first operations day
        """
        drill = self.projects[project]['drill']
        exec_date_num = self.first_day + first_day - drill
        exec_date = mdates.num2date(exec_date_num).date()
        self.projects_time_sequence.append((exec_date, project))
    
    def clear_projects(self):
        """
         Function to clear the content of the executable projects lists
        """
        self.used_projects = np.array([])
        self.active_projects = np.array([])
        self.projects_first_day = np.array([])
    
    def remove_projects(self, indxs):
        """
         Function to delete a project from the list of active projects 
         and the list of first project operations day
         
         input: 
           - project index
        """
        self.projects_first_day = np.delete(self.projects_first_day, indxs)
        self.active_projects = np.delete(self.active_projects, indxs)
    
    def update_simulatenous_projects(self, day):
        """
         Function to update the operational lists of active projects
         
         input: 
           - operations day
        """
        removed_projects_indxs = []
        for p,project in enumerate(self.active_projects):
            first_day = self.projects_first_day[p]
            drill_duration = self.projects[project]['drill']
            effective_prod = self.projects[project]['effective']
            if day-first_day == len(effective_prod):
                removed_projects_indxs.append(p)
        self.remove_projects(removed_projects_indxs)
        
    def project_production(self, day):
        """
         Function to calculate the cumulative production of the 
         projects active on a given day
         
         input: 
           - operations day
           
         output:
          - cumulative (active) project(s) production
        """
        # update the list of currently active projects
        self.update_simulatenous_projects(day)
        
        temp = 0
        for p,project in enumerate(self.active_projects):
            first_day = int(self.projects_first_day[p])
            temp += self.projects[project]['effective'][day-first_day]
        
        return temp
    
    def __call__(self):
        """
         Function to calculate the cumulative production profile 
         of all utilisable portfolio projects over the defined period
        """
        self.projects_ordering()
        
        production = []
        execution = np.arange(self.period)

        n = 0
        for start,ind in self.projects_sequence:
            if start<0:
                self.add_projects(self.projects_names[ind], 0)
                n += 1
        
        P = self.project_production(0)
        production.append(P)
        
        for day in execution[1:]:
            if n < self.projects_length:
                start,ind = self.projects_sequence[n]
                self.add_projects(self.projects_names[ind], day)
                n += 1

            P = self.project_production(day)
            production.append(P)
    
        return production
