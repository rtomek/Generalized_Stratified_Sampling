from nicegui import ui
import pandas as pd
import os
import json
from stratified_sampling import stratified_sampling
from data_preprocessing import midrc_clean
from CONFIG import SamplingData
import asyncio
import itertools

# Variables to store data
uploaded_data = None
sampled_data = None
columns = []
table_container = None  # Container to hold the table element

# Function to load file and extract columns
def load_file(file_path):
    global uploaded_data, columns
    file_ext = os.path.splitext(file_path)[1].lower()

    try:
        if file_ext == '.csv':
            uploaded_data = pd.read_csv(file_path)
        elif file_ext == '.tsv':
            uploaded_data = pd.read_csv(file_path, sep='\t')
        elif file_ext in ['.xlsx', '.xls']:
            uploaded_data = pd.read_excel(file_path)
        else:
            ui.notify('Invalid file type', color='negative')
            return

        columns = list(uploaded_data.columns)
        ui.notify('File loaded successfully', color='positive')
    except Exception as e:
        ui.notify(f'Error loading file: {str(e)}', color='negative')


# Handle file upload
def handle_upload(file):
    file_path = os.path.join('./uploads', file.name)
    os.makedirs('./uploads', exist_ok=True)
    with open(file_path, 'wb') as f:
        f.write(file.content.read())  # Corrected to use file.content.read()
    load_file(file_path)

# Function to generate distinct colors for each unique value
def generate_colors(num_colors):
    colors = itertools.cycle([
        "#87CEFA",  # Light Sky Blue
        "#FFA07A",  # Light Salmon
        "#98FB98",  # Pale Green
        "#FFB6C1",  # Light Pink
        "#FFD700",  # Gold
        "#CD5C5C",  # Indian Red
        "#40E0D0",  # Turquoise
        "#EE82EE",  # Violet
        "#F0E68C",  # Khaki
        "#7B68EE",  # Medium Slate Blue
        "#00CED1",  # Dark Turquoise
        "#FFA500",  # Orange
        "#9ACD32",  # Yellow Green
        "#8FBC8F",  # Dark Sea Green
        "#FF6347",  # Tomato
        "#4682B4",  # Steel Blue
        "#00FA9A",  # Medium Spring Green
        "#FF69B4",  # Hot Pink
        "#D2691E",  # Chocolate
        "#8A2BE2"   # Blue Violet
    ])
    return [next(colors) for _ in range(num_colors)]

# Asynchronous function to perform sampling
async def perform_sampling(dataset_column, features, datasets, numeric_cols, uid_col):
    global uploaded_data, sampled_data, table_container

    if uploaded_data is None:
        ui.notify('Please upload a file first', color='negative')
        return

    # Show a "Processing..." dialog while sampling is performed
    with ui.dialog() as processing_dialog, ui.card():
        ui.label('Processing... Please wait.')
    processing_dialog.open()
    await asyncio.sleep(0)  # Yield control to allow the dialog to render

    try:
        # Parse features, datasets, and numeric columns from input
        features_list = features.split(',') if features else []
        datasets_dict = json.loads(datasets) if datasets else {}
        numeric_cols_dict = json.loads(numeric_cols) if numeric_cols else {}

        # Ensure labels are set to None
        for col in numeric_cols_dict:
            numeric_cols_dict[col]['labels'] = None

        # Create SamplingData instance
        sampling_data = SamplingData(
            filename="",
            dataset_column=dataset_column,
            features=tuple(features_list),
            title='',
            datasets=datasets_dict,
            numeric_cols=numeric_cols_dict,
            uid_col=uid_col
        )

        loop = asyncio.get_event_loop()

        # Clean the data (awaiting to allow UI to respond)
        df_cleaned = await loop.run_in_executor(None, midrc_clean, uploaded_data, sampling_data)

        # Run the stratified sampling function (awaiting to allow UI to respond)
        sampled_data = await loop.run_in_executor(None, stratified_sampling, df_cleaned, sampling_data)

        # Close the "Processing..." dialog
        processing_dialog.close()

        # Show "Generating Table..." dialog while creating the table
        with ui.dialog() as table_dialog, ui.card():
            ui.label('Generating Table... Please wait.')
        table_dialog.open()
        await asyncio.sleep(0)  # Yield control to allow the dialog to render

        # Remove the old table by clearing the container
        table_container.clear()

        # Extract the unique values from the specified dataset column
        unique_values = sampled_data[dataset_column].unique()
        #unique_values = sampled_data['race'].unique()
        colors = generate_colors(len(unique_values))
        color_map = dict(zip(unique_values, colors))

        # Create the table using NiceGUI
        table = ui.table.from_pandas(sampled_data, pagination={'rowsPerPage': 50}).classes('w-full')

        # Add a slot for the specific dataset column to apply conditional formatting
        color_conditions = " : ".join([f"props.row.{dataset_column} == '{value}' ? 'background-color: {color};'" for value, color in color_map.items()])
        slot_string = f'''
            <q-td :props="props" :style="{color_conditions} : 'background-color: grey;'">
                    {'{{ props.value }}'}
            </q-td>
        '''
        # print(slot_string)
        table.add_slot(f'body-cell', slot_string)

        # Close the "Generating Table..." dialog
        table_dialog.close()

        ui.notify('Sampling completed successfully', color='positive')
    except Exception as e:
        processing_dialog.close()
        ui.notify(f'Error during sampling: {str(e)}', color='negative')



# Function to set datasets input to default folds
def set_folds():
    datasets_input.set_value('{"Fold 1": 20, "Fold 2": 20, "Fold 3": 20, "Fold 4": 20, "Fold 5": 20}')


# Function to set datasets input to train/validation split
def set_train_validation():
    datasets_input.set_value('{"Train": 0.8, "Validation": 0.2}')


# Function to show the feature selector dialog
def show_features_selector():
    if not columns:
        ui.notify('Please upload a file first', color='negative')
        return

    selected_columns = []

    with ui.dialog() as dialog, ui.card():
        ui.label('Select Features')
        for column in columns:
            ui.checkbox(column, on_change=lambda e, col=column: selected_columns.append(
                col) if e.value else selected_columns.remove(col))

        def confirm_selection():
            features_input.set_value(','.join(selected_columns))
            dialog.close()

        ui.button('Confirm', on_click=confirm_selection)
    dialog.open()  # Explicitly open the dialog


# Function to show the numeric column selector dialog with binning options
def show_numeric_selector():
    if not columns:
        ui.notify('Please upload a file first', color='negative')
        return

    selected_numeric_cols = {}

    with ui.dialog() as dialog, ui.card():
        ui.label('Select Numeric Columns and Set Bins')
        for column in columns:
            with ui.row():
                checkbox = ui.checkbox(column, on_change=lambda e, col=column: selected_numeric_cols.update(
                    {col: {'bins': [], 'labels': None}}) if e.value else selected_numeric_cols.pop(col, None))
                min_input = ui.number('Min', on_change=lambda e, col=column: selected_numeric_cols[col].update(
                    {'min': e.value}) if col in selected_numeric_cols else None).props('outlined').bind_visibility_from(
                    checkbox, 'value')
                max_input = ui.number('Max', on_change=lambda e, col=column: selected_numeric_cols[col].update(
                    {'max': e.value}) if col in selected_numeric_cols else None).props('outlined').bind_visibility_from(
                    checkbox, 'value')
                step_input = ui.number('Step', on_change=lambda e, col=column: selected_numeric_cols[col].update(
                    {'step': e.value}) if col in selected_numeric_cols else None).props(
                    'outlined').bind_visibility_from(checkbox, 'value')

        def confirm_numeric_columns():
            bins_dict = {}
            for col, settings in selected_numeric_cols.items():
                if 'min' in settings and 'max' in settings and 'step' in settings:
                    bins_dict[col] = {
                        'bins': list(range(int(settings['min']), int(settings['max']) + 1, int(settings['step']))),
                        'labels': None}
            numeric_cols_input.set_value(json.dumps(bins_dict))
            dialog.close()

        ui.button('Confirm', on_click=confirm_numeric_columns)
    dialog.open()  # Explicitly open the dialog


# Function to download the sampled data as CSV
def download_sampled_data():
    if sampled_data is not None:
        file_path = './uploads/sampled_data.csv'
        sampled_data.to_csv(file_path, index=False)
        ui.download(file_path)
    else:
        ui.notify('No sampled data available', color='negative')


# UI Setup
with ui.column().classes('items-center w-full'):

    # Create a grid layout for the inputs with separate columns for labels and inputs/buttons
    with ui.grid(columns=4).classes('w-full gap-4 mb-4'):
        ui.label('MIDRC Stratified Sampling Application').classes('text-3xl mb-4 col-span-2 text-center')
        ui.label('').classes('col-span-2')
        # File upload section
        ui.label('Upload a CSV, TSV, or Excel file to proceed').classes('text-right mr-4')
        ui.upload(on_upload=handle_upload).classes('col-span-3')

        # Dataset Column Input
        ui.label('Dataset Column').classes('text-right mr-2')
        dataset_column_input = ui.input(value='dataset').props('outlined').classes('w-full col-span-3')

        # Features Input with Selection Button
        ui.label('Features (comma-separated)').classes('text-right mr-2')
        with ui.row().classes('w-full col-span-3'):
            features_input = ui.input().props('outlined').classes('w-full')
            ui.button('Select Columns', on_click=show_features_selector).classes('ml-2')

        # Dataset Configuration
        ui.label('Datasets (JSON format)').classes('text-right mr-2')
        with ui.row().classes('w-full col-span-3'):
            datasets_input = ui.input(
                value='{"Fold 1": 20, "Fold 2": 20, "Fold 3": 20, "Fold 4": 20, "Fold 5": 20}').props('outlined').classes('w-full')
            ui.button('Set Folds', on_click=set_folds).classes('ml-2')
            ui.button('Set Train/Validation', on_click=set_train_validation).classes('ml-2')

        # Numeric Column Selector with Binning Parameters
        ui.label('Numeric Columns (JSON format)').classes('text-right mr-2')
        with ui.row().classes('w-full col-span-3'):
            numeric_cols_input = ui.input().props('outlined').classes('w-full')
            ui.button('Select Numeric Columns', on_click=show_numeric_selector).classes('ml-2')

        # UID Column Input
        ui.label('Unique Identifier Column').classes('text-right mr-2')
        uid_col_input = ui.input(value='submitter_id').props('outlined').classes('w-full col-span-3')

    # Perform Sampling Button
    ui.button('Perform Sampling', on_click=lambda: perform_sampling(
        dataset_column_input.value,
        features_input.value,
        datasets_input.value,
        numeric_cols_input.value,
        uid_col_input.value)).classes('mb-4')

    # Download Button
    ui.button('Download Sampled Data', on_click=download_sampled_data).classes('mb-4')

    # Container for the table
    table_container = ui.column().classes('w-full')

# Run the NiceGUI app
ui.run()
