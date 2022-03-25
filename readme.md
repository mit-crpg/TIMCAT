## What is TIMCAT?

See the paper.
"William R Stewart, Koroush Shirvan; Capital cost estimation for advanced nuclear power plants" 2021

https://osf.io/erm3g/download

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

# Usage
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

