import sys

import os
import pandas as pd
import numpy as np
import math
import datetime as date
import random
import copy
cwd = os.getcwd()


##########################################################
#Define all parameters below#
##########################################################

filepath = '' #path NOT including file name
filename = 'MIDRC_Stratified_Sampling_Example_5000_Patient_Subset.xlsx'  #File name in either .csv or .xlsx format
output_filepath = ""  #location to save output file


uid_column_number = 0   #Zero-based column number with unique identifiers
include_cols = [1, 2, 3, 4, 5]   #Zero-based column numbers that should be utilized for the stratification
numeric_cols = [1]  #Zero-based column numbers for columns which are numeric and/or need to be binned for splitting
numeric_cutoffs = {1:np.arange(0,100,10)}   #Bin cutoff values for the above-defined numeric columns.  Must be formatted following instructions in next line.

#The dict elements for numeric bin cutoffs must be formatted as <numeric_column_1>:<numpy array of bin cutoffs>.  So for example, a possible format given two numeric 
#variables in columns 0 and 4 could be: numeric_cutoffs = {0:np.arange(0, 100, 20), 4:[0, 3, 8, 10, 16]}

seed = 1 #Set random seed at user preference
np.random.seed(seed)

percSeq = 0.2 #Define percentage of data as decimal value that should be placed in sequestered/test set

view_stats = True #True if you want a printout of the number and percentage of patients fitting each variable criteria.  For numeric variables, it shows bin grouping, not the actual numeric value.

###########################################################


def groupcounts(df, col_name):
    df_out = df[col_name].value_counts().reset_index(name='GroupCount')
    df1 = df[col_name].value_counts(normalize =True).reset_index(name='Percent')
    df_out['Percent'] = df1['Percent']*100
    df_out = df_out.sort_values(['index'])
    df_out = df_out.rename(columns={'index': col_name}).reset_index(drop=True)
    return df_out


numeric_cols = [i-1 if i>uid_column_number else i for i in numeric_cols] #correct numeric column numbers after removing uid column

#Load data and format column information
inputfile = filepath + filename

if '.xlsx' in inputfile:
    data = pd.read_excel(inputfile)
elif '.csv' in inputfile:
    data = pd.read_csv(inputfile, sep = '\t')

cols = data.keys()
uid_col = cols[uid_column_number]
cols = cols[include_cols]

data[uid_col] = data[uid_col].astype(str)


#format numeric columns
for num_cols in numeric_cols:
    data[cols[num_cols]] = pd.to_numeric(data[cols[num_cols]])


#Check for duplicates - If warning presents, go to merge batch
ptcount = np.unique(data[uid_col])
if len(ptcount) != len(data.index):
    dupes_n = len(data.index)-len(ptcount)
    print("WARNING: " + str(dupes_n) + " duplicate patients in batch \n")
    
    
    
    
#Clean Data
for i in range(0, len(data.index)):
    for j, col_name in enumerate(cols):
        if j in numeric_cols:
            if math.isnan(data.loc[i, cols[j]]) or pd.isnull(data.loc[i, cols[j]]):
                if data.loc[i, cols[j]] > 89:
                    data.loc[i, cols[j]] = 89
                else:
                    data.loc[i, cols[j]] = 9999

        elif data.loc[i, cols[j]] == "":
            data.loc[i, cols[j]] = 'Not Reported'
    
    

   
#Format some column info
for i in range(len(cols)):
    if i not in numeric_cols:
        data[cols[i]] = data[cols[i]].astype(str)

data['dataset'] = ""

FinalTable = copy.copy(data)



# Separate numeric groups into categories based on bin cutoff values
for i in numeric_cols:
    data[str(cols[i])+"c"] = 0
    for index in data.index:
        
        for j, cutoff in enumerate(numeric_cutoffs[i]):
            if data.loc[index, cols[i]] == 9999:
                data.loc[index, str(cols[i])+"c"] = 9999
            elif cutoff == numeric_cutoffs[i][-1]:
                if data.loc[index, cols[i]] > numeric_cutoffs[i][-1]:
                    data.loc[index, str(cols[i])+"c"] = len(numeric_cutoffs[i])
            elif data.loc[index, cols[i]] > numeric_cutoffs[i][j] and data.loc[index, cols[i]] <= numeric_cutoffs[i][j+1]:
                data.loc[index, str(cols[i])+"c"] = j


## Stratified sampling process

# Gather stats
stats_dict = {}
for i,c in enumerate(cols):
    if i in numeric_cols:
        stats_dict[str(c)+"c"] = groupcounts(data, str(c)+"c")
    else:
        stats_dict[c] = groupcounts(data, cols[i])

# Split 
# Assumes all unique patients
open1 = pd.DataFrame([])
seq = pd.DataFrame([])
i = 0
feature_list = cols
feature_list.insert(-1, 'N')
indices = 1
for i in stats_dict:
    indices = indices*len(stats_dict[i])
count = pd.DataFrame(0, index=np.arange(indices), columns=feature_list)


###
##identify possible combinations of variables/metadata
tracker = indices
if view_stats:
    for i in stats_dict:
        print(stats_dict[i])
        print('\n')
    
possible_combos = [['a']*len(stats_dict) for i in range(indices)]
number_reps = indices
for i, stat in enumerate(stats_dict):
    counter = 0
    number_reps = number_reps/len(stats_dict[stat])
    number_vars = len(stats_dict[stat])
    number_loops = indices/(number_reps*number_vars)
    options = stats_dict[stat].iloc[:,0].to_list()
    for l in range(int(number_loops)):
        for v in range(int(number_vars)):
            for r in range(int(number_reps)):
                possible_combos[counter][i] = options[v]
                counter += 1


#Split data into Open and Sequestered sets
print('There are a total of ', len(possible_combos), ' combinations of variables in this dataset.')
print('Beginning stratified sampling.')
i_count = 0
for i, var_selections in enumerate(possible_combos):
    temp_df = data
    for j in range(len(var_selections)):
        if j in numeric_cols:
            temp_df = temp_df.loc[temp_df[str(cols[j])+"c"]==var_selections[j]]
        else:
            temp_df = temp_df.loc[temp_df[cols[j]]==var_selections[j]]
        
    temp_count = var_selections

    count.loc[i_count] = temp_count
    i_count = i_count + 1
    if len(temp_df) > 0:
        if len(temp_df) < 5:
            list = np.around(np.random.rand(len(temp_df), 1), decimals=3)
            for n in range(0, len(list)):
                if list[n] > percSeq:
                    add1 = pd.DataFrame(temp_df.loc[temp_df.index[n]]).transpose()
                    open1 = pd.concat([open1, add1])
                else:
                    add2 = pd.DataFrame(temp_df.loc[temp_df.index[n]]).transpose()
                    seq = pd.concat([seq, add2])
        else:
            rows = len(temp_df)
            arr = np.array(range(0, rows))
            idx = np.random.permutation(arr)
            add1 = pd.DataFrame(temp_df.loc[temp_df.index[idx[range(0, round(rows*(1-percSeq)))]]])
            open1 = pd.concat([open1, add1])
            add2 = pd.DataFrame(temp_df.loc[temp_df.index[idx[range(round(rows*(1-percSeq)), len(idx))]]])
            seq = pd.concat([seq, add2])
    
print('Sampling complete. Saving Results...')

# Write results in Final Table
for i in range(0, len(open1)):
    idx = FinalTable.index[FinalTable[uid_col] == open1[uid_col].iloc[i]].tolist()
    FinalTable.loc[idx, 'dataset'] = "Open"


for i in range(0, len(seq)):
    idx = FinalTable.index[FinalTable[uid_col] == seq[uid_col].iloc[i]].tolist()
    FinalTable.loc[idx, 'dataset'] = "Seq"
    

idx = FinalTable.index[FinalTable[uid_col] == "Unassigned"].tolist()
if len(idx) > 0:
    print("Warning: " + str(len(idx)) +" cases did not fall in sequestration criteria \n")
    print("Assigning to open dataset \n")
    FinalTable.loc[idx, 'dataset'] = "Open"

    print('Number of cases in this category: ', str(len(FinalTable[FinalTable['dataset']=='Open'])))
    
    
# Check for duplicate patients
ptcount = pd.unique(FinalTable[uid_col])
if not len(ptcount) == len(FinalTable):
    dupes = len(FinalTable) - len(ptcount)
    print("WARNING: "+str(dupes)+" duplicate cases in batch \n")
    count = pd.DataFrame(0, index=np.arange(len(FinalTable)), columns=['duped'])
    for i in range(0, len(FinalTable)):
        for j in range(0, len(FinalTable)):
            if FinalTable.loc[i,uid_col] == FinalTable.loc[j,uid_col]:
                count.loc[i, 'duped'] = count.loc[i, 'duped'] + 1
    dupidx = count.index[count['duped'] > 1].tolist()
    datadup = FinalTable.loc[dupidx]



Gen3Table = FinalTable
if '.xlsx' in inputfile:
    file_name = output_filepath + "COMPLETED_" + filename[0:len(filename)-5] + ".tsv"
elif '.csv' in inputfile:
    file_name = output_filepath + "COMPLETED_" + filename[0:len(filename)-4] + ".tsv"
Gen3Table.to_csv(file_name, sep='\t', encoding='utf-8', index=False)


