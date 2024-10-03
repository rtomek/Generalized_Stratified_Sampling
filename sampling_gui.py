from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QProgressDialog,
    QFileDialog, QTableView, QMessageBox, QFormLayout, QHBoxLayout
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItemModel, QStandardItem, QColor
import pandas as pd
import sys
import colorsys

from stratified_sampling import stratified_sampling
from data_preprocessing import midrc_clean
from CONFIG import SamplingData


class SamplingApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sampling Data Application")
        self.setGeometry(100, 100, 1200, 800)

        # Initialize UI components
        self.layout = QVBoxLayout()

        form_layout = QFormLayout()

        # Filename input with QFileDialog
        filename_layout = QHBoxLayout()
        self.filename_input = QLineEdit()
        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self.browse_file)
        filename_layout.addWidget(self.filename_input)
        filename_layout.addWidget(self.browse_button)
        form_layout.addRow(QLabel("Filename:"), filename_layout)

        self.dataset_column_input = QLineEdit('dataset')
        self.dataset_column_input.setToolTip("The name of the column in the data file that contains the dataset names.")
        form_layout.addRow(QLabel("Dataset Column:"), self.dataset_column_input)

        self.features_input = QLineEdit('sex,age_at_index,race,ethnicity,covid19_positive')
        self.features_input.setToolTip(
            "The features (columns) to use for the calculation. The features should be comma-separated.")
        form_layout.addRow(QLabel("Features (comma-separated):"), self.features_input)

        self.datasets_input = QLineEdit(
            "{\"Fold 1\": 20, \"Fold 2\": 20, \"Fold 3\": 20, \"Fold 4\": 20, \"Fold 5\": 20}")
        self.datasets_input.setToolTip(
            "The datasets to use for the calculation. The keys are the dataset names and the values are the fractions of the data to use for each dataset.")
        form_layout.addRow(QLabel("Datasets (JSON format, e.g., {\"Train\": 0.8, \"Validation\": 0.2}):"),
                           self.datasets_input)

        self.numeric_cols_input = QLineEdit(
            "{\"age_at_index\": {\"bins\": [0, 10, 20, 30, 40, 50, 60, 70, 80, 89, 100], \"labels\": None}}")
        self.numeric_cols_input.setToolTip(
            "The numeric columns to use for the calculation. The keys are the column names and the values are dictionaries containing the bins and labels for the column.")
        form_layout.addRow(QLabel(
            "Numeric Columns (JSON format, e.g., {\"age_at_index\": {\"bins\": [0, 10, 20, 30, 40, 50, 60, 70, 80, 89, 100], \"labels\": None}, \"col2\": {\"bins\": None, \"labels\": None}}):"),
            self.numeric_cols_input)

        self.uid_col_input = QLineEdit("submitter_id")
        self.uid_col_input.setToolTip(
            "The name of the column in the data file that contains the unique identifier for each row.")
        form_layout.addRow(QLabel("Unique Identifier Column:"), self.uid_col_input)

        self.layout.addLayout(form_layout)

        self.load_button = QPushButton("Perform Sampling")
        self.load_button.setToolTip("Perform the sampling based on the loaded data.")
        self.load_button.clicked.connect(self.perform_sampling)
        self.layout.addWidget(self.load_button)

        self.table_view = QTableView()
        self.layout.addWidget(self.table_view)

        self.save_button = QPushButton("Save Output to CSV/TSV")
        self.save_button.setToolTip("Save the output to a CSV/TSV file.")
        self.save_button.clicked.connect(self.save_output)
        self.layout.addWidget(self.save_button)

        self.setLayout(self.layout)

        self.df = None
        self.sampled_df = None

    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open File", "", "Supported Files (*.csv *.tsv *.xlsx *.xls);;"
                                                                          "TSV Files (*.tsv);;"
                                                                          "CSV Files (*.csv);;"
                                                                          "Excel Files (*.xlsx *.xls)")
        if file_path:
            self.filename_input.setText(file_path)
            self.load_data(file_path)

    def load_data(self, file_path):
        try:
            # Map file extensions to corresponding pandas read functions
            read_functions = {
                '.xlsx': pd.read_excel,
                '.xls': pd.read_excel,
                '.csv': pd.read_csv,
                '.tsv': lambda file: pd.read_csv(file, sep='\t')
            }

            # Get the file extension
            file_ext = file_path[file_path.rfind('.'):]

            # Check if the extension is supported and read the file
            if file_ext in read_functions:
                self.df = read_functions[file_ext](file_path)
                self.display_dataframe(self.df)
            else:
                QMessageBox.critical(self, "Invalid File", "Please select a valid TSV, CSV, or Excel file.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred while loading the file: {str(e)}")

    def perform_sampling(self):
        try:
            # Create a "Please wait..." dialog
            wait_dialog = QProgressDialog("Please wait...", None, 0, 0, self)
            wait_dialog.setWindowTitle("Processing")
            wait_dialog.setWindowModality(Qt.WindowModal)
            wait_dialog.setCancelButton(None)
            wait_dialog.show()
            QApplication.processEvents()

            if self.df is None:
                QMessageBox.warning(self, "No Data", "No data has been loaded. Please load a file first.")
                wait_dialog.close()
                return

            # Get user input to create SamplingData instance
            filename = self.filename_input.text()
            dataset_column = self.dataset_column_input.text()
            features = tuple(self.features_input.text().split(',')) if self.features_input.text() else ()
            title = ''
            datasets = eval(self.datasets_input.text()) if self.datasets_input.text() else {}
            numeric_cols = eval(self.numeric_cols_input.text()) if self.numeric_cols_input.text() else {}
            uid_col = self.uid_col_input.text()

            sampling_data = SamplingData(
                filename=filename,
                dataset_column=dataset_column,
                features=features,
                title=title,
                datasets=datasets,
                numeric_cols=numeric_cols,
                uid_col=uid_col
            )

            # Clean the data
            df_cleaned = midrc_clean(self.df, sampling_data)

            # Run the stratified sampling function
            self.sampled_df = stratified_sampling(df_cleaned, sampling_data)

            # Close the "Please wait..." dialog
            wait_dialog.close()

            # Display the sampled DataFrame in the table view with rows highlighted
            if self.sampled_df is not None:
                self.display_dataframe(self.sampled_df, dataset_column)
            else:
                QMessageBox.warning(self, "Sampling Error", "No data to display after sampling.")

        except Exception as e:
            wait_dialog.close()
            QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")

    def generate_color_map(self, unique_values):
        """Generate a color map for unique values using different hues."""
        num_values = len(unique_values)
        hues = [i / num_values for i in range(num_values)]
        colors = [
            QColor(*[int(c * 255) for c in colorsys.hsv_to_rgb(hue, 0.5, 0.9)]) for hue in hues
        ]
        return dict(zip(unique_values, colors))

    def display_dataframe(self, df, dataset_column=None):
        model = QStandardItemModel(df.shape[0], df.shape[1])
        model.setHorizontalHeaderLabels(df.columns)

        # Generate color map for unique values in the dataset column
        color_map = None
        if dataset_column and dataset_column in df.columns:
            unique_values = df[dataset_column].unique()
            color_map = self.generate_color_map(unique_values)

        for row in range(df.shape[0]):
            background_color = None
            if color_map and dataset_column in df.columns:
                value = df.at[row, dataset_column]
                background_color = color_map.get(value, None)

            for column in range(df.shape[1]):
                item = QStandardItem(str(df.iat[row, column]))

                # Highlight the entire row with the color based on the dataset column value
                if background_color:
                    item.setBackground(background_color)

                model.setItem(row, column, item)

        self.table_view.setModel(model)

    def save_output(self):
        if self.sampled_df is not None:
            file_path, _ = QFileDialog.getSaveFileName(self, "Save File", "", "TSV Files (*.tsv);;"
                                                                              "CSV Files (*.csv);;"
                                                                              "Excel Files (*.xlsx *.xls)")
            # Map file extensions to corresponding pandas write functions
            write_functions = {
                '.xlsx': lambda file: self.sampled_df.to_excel(file, index=False),
                '.xls': lambda file: self.sampled_df.to_excel(file, index=False),
                '.csv': lambda file: self.sampled_df.to_csv(file, index=False),
                '.tsv': lambda file: self.sampled_df.to_csv(file, index=False, sep='\t')
            }

            # Get the file extension
            file_ext = file_path[file_path.rfind('.'):]

            # Check if the extension is supported and save the file
            if file_ext in write_functions:
                write_functions[file_ext](file_path)
                QMessageBox.information(self, "File Saved", "File has been saved successfully.")
            else:
                QMessageBox.critical(self, "Invalid File Extension", "Please select a valid file extension.")
        else:
            QMessageBox.warning(self, "No Data", "There is no data to save.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SamplingApp()
    window.show()
    sys.exit(app.exec())
