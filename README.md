# Generalized_Stratified_Sampling

This repository is meant to be a generalized version of the stratified sampling method used to split incoming datasets between the Open, publicly available MIDRC data (80%) and Sequestered, private data (20%).  This is a variant of our other repository, [Stratified_Sampling](https://github.com/MIDRC/Stratified_Sampling).  The difference between these two options is that [Stratified_Sampling](https://github.com/MIDRC/Stratified_Sampling) was written specifically for the COVID-19 use case while this generalized version can be utilized to split any dataset based on specified variables, matching prevalence of all variable combinations.  More generally, it can be used to assign cases to training and independent testing sets.  Read more about the problem definition at [Stratified_Sampling](https://github.com/MIDRC/Stratified_Sampling).

This code is suggested for use in cases where the user would like to split data into 2 subsets in which multiple variables are equally stratified across the subsets.  Note, however, that this code is not intended to be used for scenarios in which there are many variable possibilities and few cases; e.g., 100 cases, 10 variables, 10 possibilities for each variable.  In this scenario, at least one case (and likely many) would have unique combinations of stratification variables and could be incorrectly split between the open and sequestered sets (note, our script is written to assign these cases to the open set).

Here, we present 2 examples of how to split data using this [Generalized_Stratified_Sampling](https://github.com/MIDRC/Generalized_Stratified_Sampling) repository with the example data file, `MIDRC_Sequ_Example_5000_patient.xlsx` and the main data sequestration script, `GeneralDataStratification.py`.  To begin, there are several parameters/variables that must be set in `GeneralDataStratification.py`, all of which are in Lines 13-37.  Below, find brief instructions for how to set each variable.
### Path Information
```
filepath = os.getcwd()+'/' #path to file location.  This could be absolute or relative pathsor acquired with os.getcwd()+'/' 
filename = 'MIDRC_Sequ_Example_5000_patient.xlsx'  #File name in either .csv or .xlsx format
output_filepath = "os.getcwd()+'/TestRun/'  #location to save output file
```

### Identify stratification variables
When you open the MIDRC_Sequ_Example_5000_patient.xlsx file, you will notice that there are 13 columns of data.  The third column, `case_id`, serves as our unique ID for the cases in this dataset.  Thus, we now set our zero-based column variable as
```
uid_column_number = 2
```

Next, we identify the columns for which we would like to have equal prevalence in the open and sequestered sets; in this example, we will use the columns for Age (column 0), COVID-19 status (1), Ethnicity (3), Race (5), and Sex (6).  We identify those columns with 
```
include_cols = [0, 1, 3, 4, 5]
```

There are kinds of variables which can be used for stratification, 1) categorical and 2) numeric/continuous.  This code splits data by evaluating all combinations of included variables; however, in considering numeric/continuous variables, we would achieve an infinite (or at least, very large) number of possibilities.  To avoid this, we require that you batch/bin these variables to categories with reasonable size.  To be clear, a variable with 5 options labeled (1, 2, 3, 4, 5) should be considered categorical, not numeric.  

As an example, consider Age as a numeric variable and that we want to bin age by 10-year categories.  We first identify the columns which have numeric variables (`numeric_cols`).  The bins can be set a few different ways, two of which are shown below.
```
numeric_cols = [0]
numeric_cutoffs = {0:np.arange(0, 100, 10)}
numeric_cutoffs = {0:[0, 10, 20, 30, 40, 50, 60, 70, 80, 90]}
```

While this is not the case for our example data, suppose that we had another numeric variable in column 15 ranging between 0 and 1; our variables would look like:
```
numeric_cols = [0, 15]
numeric_cutoffs = {0:np.arange(0, 100, 10), 15:np.arange(0, 1.0, 0.1)}
```

Or suppose that we had no numeric data, we can address this with 
```
numeric_cols = []
numeric_cutoffs = {}
```

### Stratification Percent and Statistics
Finally, we can identify the amount of data that we want to go to the sequestered set (e.g., 20%=0.2) and if you want a printout of variable combination statistics with
```
percSeq = 0.2
view_stats = True
```

### Running the code
If the `GeneralDataStratification.py` and `MIDRC_Sequ_Example_5000_patient.xlsx' are in the current working directory and the appropriate packages have been installed, then this script can be run with 
```
python GeneralDataStratifiction.py
'''

### Output
The output file is saved as a .tsv file at the specified output location with the name "COMPLETED"+original filename.  This file should be identical to the input file except for an added column, "dataset", which specifies whether that case has been put in the Open/Training or Sequestered/Testing set.  
