import pandas as pd
import numpy as np
import math
import copy
import itertools
from datetime import datetime
import os

from CONFIG import CONFIG, SamplingData
from data_preprocessing import bin_dataframe_column, midrc_clean


def group_counts(df_in, col_name):
    """
    Calculate the value counts and normalize to get percentages for a given column.

    Parameters:
    - df (pandas.DataFrame): The DataFrame containing the column to be counted.
    - col_name (str): The name of the column to be counted.

    Returns:
    - pandas.DataFrame: A DataFrame containing the counts of the column.
    """
    # Calculate the value counts and normalize to get percentages
    counts = df_in[col_name].value_counts()

    # Create the output DataFrame
    df_out = pd.DataFrame({
        col_name: counts.index,
        'GroupCount': counts.values,
    })

    # Sort the DataFrame by the original column values
    df_out = df_out.sort_values(by=col_name).reset_index(drop=True)

    return df_out

def check_for_duplicates(df_in: pd.DataFrame, uid_col: str) -> bool:
    """
    Check for duplicates in the 'uid_col' column.

    Parameters:
    - df_in (pandas.DataFrame): The DataFrame containing the column to be checked.
    - uid_col (str): The name of the column to be checked.

    Returns:
    - bool: True if there are duplicates, False otherwise.
    """
    # Check for duplicates in the 'uid_col' column
    dupes = df_in[uid_col].duplicated(keep=False)  # Mark all duplicates, including first occurrences

    # If there are duplicates
    if dupes.any():
        # Count the number of duplicates
        num_dupes = dupes.sum()
        print(f"WARNING: {num_dupes} duplicate cases in batch \n")

        # Get the duplicate rows
        datadup = df_in[dupes]
        print(f"Duplicate rows: {datadup.shape[0]}")

        # Get the unique values in the 'uid_col' column
        uid_list = datadup[uid_col].unique()

        # Create a dictionary to store the counts of each unique value
        counts = dict(zip(uid_list, datadup[uid_col].value_counts().to_list()))

        # Print the counts
        for uid, count in counts.items():
            print(f"{uid}: {count}")

    return dupes.any()


def stratified_sampling(data_in: pd.DataFrame, sampling_data: SamplingData, view_stats=False) -> pd.DataFrame:
    """
    Perform stratified sampling on a DataFrame.

    Parameters:
    - data (pandas.DataFrame): The DataFrame to be sampled.
    - sampling_data (SamplingData): The sampling configuration.
    - view_stats (bool): Whether to view the statistics of the sampling.

    Returns:
    - pandas.DataFrame: The sampled DataFrame.
    """
    numeric_cols = sampling_data.numeric_cols
    """ 
    # I don't think this is necessary anymore
    if len(sampling_data.numeric_cols) == 0:
        numeric_cols = {'age_at_index':
                            {'bins': None,
                             'labels': None}}
    """

    uid_col = sampling_data.uid_col
    cols = sampling_data.features

    data_in[uid_col] = data_in[uid_col].astype(str)

    # Check for duplicates - If warning presents, go to merge batch
    check_for_duplicates(data_in, uid_col)

    # Convert numeric columns to numeric type and non-numeric columns to string type
    for col_name in cols:
        if col_name in numeric_cols:
            data_in[col_name] = pd.to_numeric(data_in[col_name], errors='coerce')
        else:
            data_in[col_name] = data_in[col_name].astype(str)

    # Copy the original data to a new dataframe
    final_table = copy.copy(data_in)

    # Separate numeric groups into categories based on bin cutoff values
    cut_suffix = "_CUT" if len(numeric_cols) > 0 else ""
    for col_name, bin_info in numeric_cols.items():
        data_in = bin_dataframe_column(data_in,
                                       column_name=col_name,
                                       cut_column_name=col_name + cut_suffix,
                                       bins=bin_info['bins'],
                                       labels=bin_info['labels'])
        # We can use this to check the distribution of the binned column
        # print(data[col_name + cut_suffix].value_counts(dropna=False))

    ## Stratified sampling process

    # Gather stats using a dictionary comprehension
    stats_dict = {
        (f"{col_name}{cut_suffix}" if col_name in numeric_cols else col_name): group_counts(data_in,
         f"{col_name}{cut_suffix}" if col_name in numeric_cols else col_name)
        for col_name in cols
    }

    if view_stats:
        for val in stats_dict.values():
            print(val)
            print('\n')

    # Generate all possible combinations of variables in the dataset
    possible_combos = list(itertools.product(*(stats_dict[stat].iloc[:, 0].to_list() for stat in stats_dict)))

    # print(f'There are a total of {len(possible_combos)} combinations of variables in this dataset.')
    # print('Beginning stratified sampling.')

    for var_selections in possible_combos:
        # Filter the data based on the current combination of variable selections
        temp_df = data_in
        for j, col_name in enumerate(cols):
            filter_col = col_name + cut_suffix if col_name in numeric_cols else col_name
            temp_df = temp_df.loc[temp_df[filter_col] == var_selections[j]]

        if not temp_df.empty:
            total_fraction = sum(sampling_data.datasets.values())
            dataset_split_dict = {}
            for dataset, fraction in sampling_data.datasets.items():
                item_split = fraction * len(temp_df) / total_fraction
                dataset_split_dict[dataset] = {'num_items': math.floor(item_split),
                                               'remainder': item_split - math.floor(item_split),
                                               }

            # Shuffle the DataFrame
            temp_df_shuffled = temp_df.sample(frac=1).reset_index(drop=True)
            start_index = 0
            for dataset, split_dict in dataset_split_dict.items():
                split_index = start_index + split_dict['num_items']
                dataset_ids = temp_df_shuffled.iloc[start_index:split_index][uid_col]

                # Vectorized assignment to final_table based on dataset_ids
                final_table.loc[final_table[uid_col].isin(dataset_ids), sampling_data.dataset_column] = dataset
                start_index = split_index

            # Handle the remainder of the dataset if any items are left
            while start_index < len(temp_df_shuffled):
                total_remainder = sum([v['remainder'] for v in dataset_split_dict.values()])
                single_choice = np.random.choice(
                                     list(dataset_split_dict.keys()),
                                     p=[v['remainder']/total_remainder for v in dataset_split_dict.values()]
                                     )
                final_table.loc[final_table[uid_col] == temp_df_shuffled.iloc[start_index][uid_col], sampling_data.dataset_column] = single_choice
                dataset_split_dict.pop(single_choice)
                start_index += 1


    # print('Sampling complete. Saving Results...')
    # print(FinalTable[sampling_data.dataset_column].value_counts(dropna=False))

    # Check for unassigned cases
    idx = final_table.index[final_table[sampling_data.dataset_column] == ""].tolist()
    if len(idx) > 0:
        first_dataset = list(sampling_data.datasets.keys())[0]
        print("Warning: " + str(len(idx)) + " cases did not fall in sequestration criteria \n")
        print("Assigning to " + first_dataset + " dataset \n")
        final_table.loc[idx, sampling_data.dataset_column] = first_dataset

        print('Total number of cases in this category after assignment: ',
              str(len(final_table[final_table[sampling_data.dataset_column] == first_dataset])))

    return final_table

def generate_output_filename(input_filename, *, extension: str = 'tsv', use_timestamp: bool = True,
                             prefix: str = 'COMPLETED_', suffix: str = '', timestamp_in_prefix: bool = False) -> str:
    """
    Generate a filename for the output file based on the sampling data and extension.

    Parameters:
    - input_filename (str): The input filename.
    - extension (str): The extension of the output file.
    - use_timestamp (bool): Whether to include a timestamp in the filename.
    - prefix (str): The prefix to be added to the filename.
    - suffix (str): The suffix to be added to the filename.
    - timestamp_in_prefix (bool): Whether to include the timestamp in the prefix instead of the suffix.

    Returns:
    - str: The generated filename.
    """
    # Get the current timestamp in the desired format, e.g., 'YYYYMMDD_HHMMSS' if _use_timestamp is True
    timestamp = '_' + datetime.now().strftime('%Y%m%d_%H%M%S') if use_timestamp else ''

    if timestamp_in_prefix:
        prefix += timestamp
    else:
        suffix += timestamp

    # Split out the folder and filename from the input filename
    folder_name, file_name_no_folder = os.path.split(input_filename)
    # Add the timestamp to the filename before the extension
    base_name, file_extension = file_name_no_folder.rsplit('.', 1)  # Split into base name and extension

    # Construct the new filename with the timestamp inserted before the extension
    output_filename = f"{folder_name}/{prefix}{base_name}{suffix}.{extension}"

    return output_filename

if __name__ == '__main__':
    """
    Run stratified sampling on the data and save the results.
    """
    config = CONFIG()
    # config.set_filename('CONFIG_stratified_sampling.yaml')  # Uncomment to use a different config file
    sampling_dict = config.sampling_dict

    seed = 0  # Set random seed at user preference
    np.random.seed(seed)

    last_filename = None
    df = None
    # Iterate over the sampling configurations
    for key, sampling_data in sampling_dict.items():
        # Check if the DataFrame needs to be read from a file
        if df is None or sampling_data.filename != last_filename:
            try:
                # Map file extensions to corresponding pandas read functions
                read_functions = {
                    '.xlsx': pd.read_excel,
                    '.xls': pd.read_excel,
                    '.csv': pd.read_csv,
                    '.tsv': lambda file: pd.read_csv(file, sep='\t'),
                }

                # Get the file extension
                file_ext = sampling_data.filename[sampling_data.filename.rfind('.'):]

                # Check if the extension is supported and read the file
                if file_ext in read_functions:
                    data = read_functions[file_ext](sampling_data.filename)
                else:
                    raise ValueError(f"Unsupported file format: {sampling_data.filename}")

                # Process the data
                df = midrc_clean(data, sampling_data)
                last_filename = sampling_data.filename

            except FileNotFoundError as e:
                print(f"Error reading file: {sampling_data.filename}. {e}")
                continue
            except ValueError as e:
                print(f"ValueError: {e}")
                continue

        # Perform stratified sampling
        df = stratified_sampling(df, sampling_data)

        # We can use this to check the distribution of the dataset column
        # print(df[sampling_data.dataset_column].value_counts(dropna=False))

        prefix = 'COMPLETED_'
        # Add the key to the filename if there are multiple sampling configurations
        suffix = f'_{key}' if len(sampling_dict) > 1 else ''
        use_timestamp = False  # Set to True to add a timestamp to the filename

        # Generate the output filename with the prefix, suffix, and timestamp as specified above
        file_name = generate_output_filename(sampling_data.filename,
                                             extension='tsv',
                                             use_timestamp=use_timestamp,
                                             prefix=prefix,
                                             suffix=suffix,
                                             )

        # Save the DataFrame to a TSV file
        df.to_csv(file_name, sep='\t', encoding='utf-8', index=False)
