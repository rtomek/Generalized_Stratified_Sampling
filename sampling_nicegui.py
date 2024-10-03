from nicegui import ui
import pandas as pd
import os
import json
from stratified_sampling import stratified_sampling
from data_preprocessing import midrc_clean
from CONFIG import SamplingData
import asyncio

# Variables to store data
uploaded_data = None
sampled_data = None
columns = []


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


# Asynchronous function to perform sampling
async def perform_sampling(dataset_column, features, datasets, numeric_cols, uid_col):
    global uploaded_data, sampled_data

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

        # Show the sampled DataFrame in a new table view
        ui.table.from_pandas(sampled_data).classes('w-full')
        ui.notify('Sampling completed successfully', color='positive')
    except Exception as e:
        processing_dialog.close()
        ui.notify(f'Error during sampling: {str(e)}', color='negative')


# UI Setup
with ui.column().classes('items-center w-full'):
    ui.label('MIDRC Stratified Sampling Application').classes('text-3xl mb-4')

    # File upload section
    ui.label('Upload a CSV, TSV, or Excel file to proceed').classes('mb-2')


    def handle_upload(file):
        file_path = os.path.join('./uploads', file.name)
        os.makedirs('./uploads', exist_ok=True)
        with open(file_path, 'wb') as f:
            f.write(file.content.read())  # Corrected to use file.content.read()
        load_file(file_path)


    ui.upload(on_upload=handle_upload).classes('mb-4')

    # Dataset Column Input
    dataset_column_input = ui.input('Dataset Column', value='dataset').props('outlined').classes('mb-4')

    # Features Input with Selection Button
    features_input = ui.input('Features (comma-separated)').props('outlined').classes('mb-4')


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


    ui.button('Select Columns', on_click=show_features_selector).classes('mb-4')

    # Dataset Configuration
    datasets_input = ui.input('Datasets (JSON format)',
                              value='{"Fold 1": 20, "Fold 2": 20, "Fold 3": 20, "Fold 4": 20, "Fold 5": 20}').props(
        'outlined').classes('mb-4')


    def set_folds():
        datasets_input.set_value('{"Fold 1": 20, "Fold 2": 20, "Fold 3": 20, "Fold 4": 20, "Fold 5": 20}')


    def set_train_validation():
        datasets_input.set_value('{"Train": 0.8, "Validation": 0.2}')


    ui.button('Set Folds', on_click=set_folds).classes('mb-2')
    ui.button('Set Train/Validation', on_click=set_train_validation).classes('mb-4')

    # Numeric Column Selector with Binning Parameters
    numeric_cols_input = ui.input('Numeric Columns (JSON format)').props('outlined').classes('mb-4')


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
                        {'min': e.value}) if col in selected_numeric_cols else None).props(
                        'outlined').bind_visibility_from(checkbox, 'value')
                    max_input = ui.number('Max', on_change=lambda e, col=column: selected_numeric_cols[col].update(
                        {'max': e.value}) if col in selected_numeric_cols else None).props(
                        'outlined').bind_visibility_from(checkbox, 'value')
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


    ui.button('Select Numeric Columns', on_click=show_numeric_selector).classes('mb-4')

    # UID Column Input
    uid_col_input = ui.input('Unique Identifier Column', value='submitter_id').props('outlined').classes('mb-4')

    # Perform Sampling Button
    ui.button('Perform Sampling', on_click=lambda: perform_sampling(
        dataset_column_input.value,
        features_input.value,
        datasets_input.value,
        numeric_cols_input.value,
        uid_col_input.value)).classes('mb-4')


    # Download Button
    def download_sampled_data():
        if sampled_data is not None:
            sampled_data.to_csv('./uploads/sampled_data.csv', index=False)
            ui.download('./uploads/sampled_data.csv')
        else:
            ui.notify('No sampled data available', color='negative')


    ui.button('Download Sampled Data', on_click=download_sampled_data).classes('mb-4')

# Run the NiceGUI app
ui.run()
