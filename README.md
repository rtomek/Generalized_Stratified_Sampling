# Generalized_Stratified_Sampling

This GitHub entry is meant to be a generalized version of the stratified sampling method used to split incoming datasets between the Open, publicly available MIDRC data (80%) and Sequestered, private data (20%).  This GitHub entry is a variant of our other GitHub repository, [Stratified_Sampling](https://github.com/MIDRC/Stratified_Sampling), which is the initial code used for creating the sequestered data commons.  The difference between these two options is that [Stratified_Sampling](https://github.com/MIDRC/Stratified_Sampling) was written specifically for the COVID-19 use case while this generalized version can be utilized to split any dataset based on specified variables, matching prevalence of all variable combinations.  More generally, it can be used to assign cases to training and independent testing sets.  Read more about the problem definition at [Stratified_Sampling](https://github.com/MIDRC/Stratified_Sampling).

This code is suggested for use in cases where the user would like to split data into multiple subsets in which multiple variables are equally stratified across the subsets.  Note, however, that this code is not intended to be used for scenarios in which there are many variable possibilities and few cases; e.g., 100 cases, 10 variables, 10 possibilities for each variable.  In this scenario, at least one case (and likely many) would have unique combinations of stratification variables and could be incorrectly split between the open and sequestered sets (note, our script is written to assign these cases to the first set in the list, e.g. Open).

Here, we present examples of how to split data using this [Generalized_Stratified_Sampling](https://github.com/MIDRC/Generalized_Stratified_Sampling) repository.  To begin, first acquire the example data spreadsheet [HERE](https://doi.org/10.60701/P67C-YW55) (you will need to be signed into a [data.midrc.org](data.midrc.org) account to access the example data).  This DOI link should open a description of the dataset at [data.midrc.org](data.midrc.org); if you scroll to the bottom of the description window, you can acquire the example data by clicking "Download File" on the right side of the screen.  Once you've downloaded the spreadsheet, there are several parameters/variables that must be set in the main config file, `CONFIG.yaml`.  Below, find brief instructions for how to set each variable. You can also create your own config file by copying the `CONFIG.yaml` file and modifying it to your needs.
### Environment Creation
First, create a conda environment and install packages with 
```bash
conda create --name GenStratSamp python=3.12
conda activate GenStratSamp
pip install -r requirements.txt
```

### Filename Information
```
The filename of the data source to be loaded is specified in the config file with the `filename` key.
The output file is saved as a .tsv file at the specified output location with the name "COMPLETED_"+original filename.
```

### Identify stratification variables
When you open the MIDRC_Stratified_Sampling_Example_5000_Patient_Subset.xlsx file, you will notice that there are 13 columns of data.  The first column, `submitter_id`, serves as our unique ID for the cases in this dataset.  Thus, we now set our uid column variable as
```yaml
uid_col: "submitter_id"
```

Next, we identify the columns for which we would like to have equal prevalence in the open and sequestered sets; in this example, we will use the columns for Age, COVID-19 status, Ethnicity, Race, and Sex.  We identify those columns with 
```yaml
features: ['sex', 'age_at_index', 'race', 'ethnicity', 'covid19_positive']
```

There are kinds of variables which can be used for stratification, 1) categorical and 2) numeric/continuous.  This code splits data by evaluating all combinations of included variables; however, in considering numeric/continuous variables, we would achieve an infinite (or at least, very large) number of possibilities.  To avoid this, we recommend that you batch/bin these variables to categories with reasonable size.  To be clear, a variable with only 5 options labeled (1, 2, 3, 4, 5) should be considered categorical, not numeric.  

As an example, consider Age as a numeric variable and that we want to bin age by 10-year categories.  We first identify the columns which have numeric variables (`numeric_cols`).  The bins can be set a few different ways, three of which are shown below.
```yaml
# Example 1
  numeric_cols:
    age_at_index:
      bins: [0, 18, 50, 65, 1000]  # Using CDC age bins
      labels: ['0-17', "18-49", '50-64', '65+']
      
# Example 2
  numeric_cols:
    age_at_index:
      bins: [0, 10, 20, 30, 40, 50, 60, 70, 80, 89, 100]  # Using 10-year age bins
      labels: null  # Use default-generated labels
      
# Example 3      
  numeric_cols:
    age_at_index:
      bins: null  # The default-generated bins are identical to the 10-year age bins above
      labels: null  # Use default-generated labels
    other_numeric_col:
      bins: [-25, -20, -15, -10, -5, 0, 5, 10, 15, 20, 25]
      labels: null
```

### Stratification Percent and Statistics
Finally, we can identify the amount of data that we want to go to the sequestered set (e.g., 20%=0.2), and also whether we want to split the open data into folds.
```yaml
# Example 1
  datasets:
    Open: 0.8
    Seq: 0.2

# Example 2
  datasets:
    Fold 1: 16
    Fold 2: 16
    Fold 3: 16
    Fold 4: 16
    Fold 5: 16
    Test:   20

# Example 3, identical to example 2. Note that the values do not need to add up to 1 or 100.
  datasets:
    Fold 1: 4
    Fold 2: 4
    Fold 3: 4.0
    Fold 4: 4
    Fold 5: 4.0
    Test:   5
```

### Dataset column in the output file
The dataset column in the output file is set using the dataset_column key in the CONFIG.yaml file.
```yaml
  dataset_column: "dataset"
```

### Running the code
If the `stratified_smapling.py` and file(s) specified in CONFIG.yaml are in the current working directory and the appropriate packages have been installed, then this script can be run with 
```bash
python stratified_sampling.py
```

### Output
The output file is saved as a .tsv file at the specified output location with the name "COMPLETED"+original filename.  This file should be identical to the input file except for an added column, set using dataset_column, which specifies which set that case has been put in.  
