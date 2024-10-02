import numpy as np
import pandas as pd


def open_and_clean_data(sampling_data, df=None):
    """
    Opens and cleans the data for a given sampling data object.

    Parameters:
    - sampling_data (SamplingData): The sampling data object.
    - df (pandas.DataFrame): The DataFrame containing the data.

    Returns:
    - pandas.DataFrame: The cleaned DataFrame.
    """
    if df is None or sampling_data.filename != df.source_file.iloc[0]:
        try:
            df = pd.read_csv(sampling_data.filename, sep='\t')
            df = midrc_clean(df, sampling_data)
            df['source_file'] = sampling_data.filename
        except FileNotFoundError as e:
            print(f"Error reading file: {sampling_data.filename}. {e}")
            return None
    return df

def bin_dataframe_column(df_to_bin, column_name, cut_column_name='CUT', bins=None, labels=None, *, right=False):
    """
    Cuts the age column into bins and adds a column with the bin labels.

    Parameters:
    - df_to_bin: pandas DataFrame containing the data
    - column_name: name of the column to be binned
    - cut_column_name: name of the column to be added with the bin labels
    - bins: list of bins to be used for the binning
    - labels: list of labels for the bins
    - right: whether to use right-inclusive intervals

    Returns:
    - df: pandas DataFrame with the binned column and the labels
    """
    if column_name in df_to_bin.columns:
        if bins is None:
            bins = np.arange(0, 100, 10)  # Default bins
            # print("Generated bins:", bins)  # Uncomment to see the generated bins

        if labels is None:
            labels = []
            for i in range(len(bins) - 1):
                if isinstance(bins[i], int) and isinstance(bins[i + 1], int):
                    if i < len(bins) - 2:
                        # Adjust the upper limit for integer values
                        labels.append(f"{bins[i]}-{bins[i + 1] - 1}")
                    else:
                        # Last bin with '>=' format
                        labels.append(f">={bins[i]}")
                else:
                    # Use raw values for non-integer bins
                    labels.append(f"{bins[i]}-{bins[i + 1]}")
            # print("Generated labels:", labels)  # Uncomment to see the generated labels

        df_out = df_to_bin.assign(**{
            cut_column_name: pd.cut(
                df_to_bin[column_name],
                bins=bins,
                labels=labels,
                right=right  # Use right=False for left-inclusive intervals
            ).astype('string')
        })

        # Check for outliers and assign them to a new category
        if df_out[cut_column_name].isna().any():
            new_text = "Outlier"
            low_text = new_text + "_Low"
            high_text = new_text + "_High"
            print(f"WARNING: There are values outside the bins specified for the '{column_name}' column.")
            df_out.loc[df_out[cut_column_name].isna() & (df_out[column_name] < bins[0]), cut_column_name] = low_text
            df_out.loc[df_out[cut_column_name].isna() & (df_out[column_name] >= bins[-1]), cut_column_name] = high_text
            df_out.loc[df_out[cut_column_name].isna(), cut_column_name] = new_text
            if (df_out[cut_column_name] == low_text).sum() > 0:
                print(f"         {(df_out[cut_column_name] == low_text).sum()} values are below the minimum bin value.\n" 
                      f"         These will be placed in a new '{low_text}' category.")
            if (df_out[cut_column_name] == high_text).sum() > 0:
                print(f"         {(df_out[cut_column_name] == high_text).sum()} values are above the maximum bin value.\n" 
                      f"         These will be placed in a new '{high_text}' category.")
            if (df_out[cut_column_name] == new_text).sum() > 0:
                print(f"         {(df_out[cut_column_name] == new_text).sum()} values are outside the specified bins.\n" 
                      f"         These will be placed in a new '{new_text}' category.")

        return df_out

def convert_empty_strings(df, cols, numeric_cols, new_text="Not Reported"):
    """
    Replace empty strings in the non-numeric columns with a new text.

    Parameters:
    - df (pandas.DataFrame): The DataFrame containing the columns to be converted.
    - cols (list): A list of column names to be converted.
    - numeric_cols (list): A list of numeric column names.
    - new_text (str): The text to replace empty strings with.

    Returns:
    - pandas.DataFrame: A DataFrame with the empty strings replaced.
    """
    # Create a set of non-numeric columns by subtracting numeric_cols from cols
    non_numeric_cols = [col for col in cols if col not in numeric_cols]

    # Replace empty strings in the non-numeric columns
    df[non_numeric_cols] = df[non_numeric_cols].replace('', new_text)

    return df


def fix_midrc_age(midrc_df):
    """
    Fix the age column in the MIDRC dataset.

    Parameters:
    - midrc_df (pandas.DataFrame): The DataFrame containing metadata from the MIDRC dataset.

    Returns:
    - pandas.DataFrame: A DataFrame with the age column fixed.
    """
    col_name = 'age_at_index'
    col_name_gt89 = 'age_at_index_gt89'

    if col_name in midrc_df.columns:
        # Check if 'age_at_index_gt89' exists and process accordingly
        if col_name_gt89 in midrc_df.columns:
            # Find rows where 'age_at_index' is NaN
            is_na = midrc_df[col_name].isna()

            # Set 'age_at_index' to 89 where 'age_at_index_gt89' is 'Yes'
            midrc_df.loc[is_na & (midrc_df[col_name_gt89] == "Yes"), col_name] = 89

            # Set 'age_at_index' to 9999 where 'age_at_index_gt89' is not 'Yes'
            midrc_df.loc[is_na & (midrc_df[col_name_gt89] != "Yes"), col_name] = 9999

        # Set the maximum age to 89 if it is greater than 89 but not unknown
        midrc_df.loc[(midrc_df[col_name] > 89) & (midrc_df[col_name] < 9999), col_name] = 89

    return midrc_df

def midrc_clean(midrc_df: pd.DataFrame, sampling_data) -> pd.DataFrame:
    """
    Clean up the MIDRC dataset.

    Parameters:
    - midrc_df (pandas.DataFrame): The DataFrame containing data from the MIDRC dataset.
    - sampling_data (SamplingData): The sampling configuration.

    Returns:
    - pandas.DataFrame: A DataFrame with the MIDRC dataset cleaned up.
    """
    midrc_df = convert_empty_strings(midrc_df, sampling_data.features, list(sampling_data.numeric_cols.keys()))
    midrc_df = fix_midrc_age(midrc_df)

    return midrc_df

