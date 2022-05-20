## What is TIMCAT?
TIMCAT hosts Nuclear Cost Estimation Tool (NCET)

Citation: Stewart W.R., Shirvan K., "Capital cost estimation for advanced nuclear power plants," Renewable and Sustainable Energy Reviews, Nov. 2021, 111880 https://doi.org/10.1016/j.rser.2021.111880


For more info and access to other already modeled plants contact: Prof. Koroush Shirvan kshirvan@mit.edu

## Quick Install

Use python 3.9

Be sure to update your pip installer which is a python installer:

``pip3 install --upgrade pip``

To install TIMCAT, git clone this package into your preferred location:

``gh repo clone mit-crpg/TIMCAT``

Installing for the first time use which looks at the setup.py file and installs the packages. Run with sudo. If you use
other packages in the code, add the required package to the setup.py file so it will install.

``pip3 install .``

To update, simply reinstall with pip from the TIMCAT directory:

``pip3 install . --upgrade``

(And to uninstall, simply run: ``pip3 uninstall TIMCAT``)

## Usage
As configured, TIMCAT is run by editing input files and their names in cost_sensitivity.py and running
cost_sensitivity.py. 

You must specify the basis table, and the input files. Edit these lines in cost_sensitivity.py:

```python
plant = "PWR12ME"
BASIS_FNAME = (
    "PATHTOFILE/PWR12_ME_inflated_reduced.csv"
)
plant_fname = "inputfile_" + plant + ".xlsx"
```

## File descriptions
#### "PWR12_ME_inflated_reduced.csv"
This is the reference cost data for the PWR12-ME plant. Costs were inflated from 1987 USD in EEDB to 2018 USD.

#### "inputfile_PWR12ME.xlsx"
This is the input file template for estimating the costs of a new plant. There are 9 tabs: 6 for direct cost categories, 1 for learning inputs, 1 for modularization inputs, and 1 for general plant characteristics. 

#### "input_scaling_exponents.xlsx"
This is the input file for the cost scaling model parameters. The reference values are recommended, but the user is welcome to use their own parameters. 

#### "input_LaborIndices.csv", "input_MaterialIndices.csv", "input_CostOverrun.csv"
These were the scaling matrices used to escalate the EEDB reference costs from 1987 to 2018 USD, and from the PWR12-BetterExperience to the PWR12-Median Experience. They are not called explicitly in the code, except the labor indices are called if steel plate composites are used. Future additions to the code that include new cost items can use this as a sample template.

#### "building_template.csv", "scheduler_table.csv"
These are template files to organize the output data to run the construction scheduler which is a separate code.


## References
The source cost data was from the Economic Energy Data Base published by the US DOE in 1987. The full dataset can be requested here: https://rsicc.ornl.gov/codes/psr/psr5/psr-531.html

Stewart W.R., Shirvan K., "Capital cost estimation for advanced nuclear power plants," Renewable and Sustainable Energy Reviews, Nov. 2021, 111880 https://doi.org/10.1016/j.rser.2021.111880

Preprints:

https://osf.io/erm3g/download

https://osf.io/j45aw/download
