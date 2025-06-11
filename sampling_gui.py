#This work was supported in part by The Medical Imaging and Data Resource Center (MIDRC), 
#which is funded by the National Institute of Biomedical Imaging and Bioengineering (NIBIB) 
#of the National Institutes of Health under contract 75N92020D00021/5N92023F00002 and 
#through the Advanced Research Projects Agency for Health (ARPA-H).

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QProgressDialog,
    QFileDialog, QTableView, QMessageBox, QFormLayout, QHBoxLayout, QDialog, QCheckBox, QDialogButtonBox,
    QVBoxLayout, QSpinBox, QDoubleSpinBox, QButtonGroup, QGridLayout, QScrollArea, QAbstractScrollArea, QWidget
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItemModel, QStandardItem, QColor
import pandas as pd
import sys
import colorsys

from stratified_sampling import stratified_sampling
from data_preprocessing import midrc_clean
from CONFIG import SamplingData


def _update_scroll_width(content_widget: QWidget, scroll_area: QScrollArea):
    """Resize scroll_area width based on content layout’s minimum width."""
    # ensure layouts are recalculated
    content_widget.updateGeometry()
    # get content minimum width
    content_min_w = content_widget.layout().minimumSize().width()
    # width of vertical scrollbar
    vbar_w = scroll_area.verticalScrollBar().sizeHint().width()
    # account for frame
    frame = scroll_area.frameWidth() * 2
    total_w = content_min_w + vbar_w + frame
    # apply and force geometry update
    scroll_area.setMinimumWidth(total_w)
    scroll_area.updateGeometry()


class NumericColumnSelectorDialog(QDialog):
    def __init__(self, columns, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Numeric Columns and Binning Parameters")
        main_layout = QVBoxLayout()

        # filter input
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter columns...")
        self.filter_edit.textChanged.connect(self.apply_filter)
        main_layout.addWidget(self.filter_edit)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        # make scroll area size hint follow its content
        scroll_area.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        content_layout = QVBoxLayout(content)

        # Add a checkbox and min/max/step input for each column
        self.column_settings = {}
        for column in columns:
            # wrap row for filtering
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)

            checkbox = QCheckBox(column)
            min_input = QDoubleSpinBox()
            min_input.setPrefix("Min: ")
            min_input.setMaximum(1e6)
            min_input.setValue(0)
            min_input.setVisible(False)  # Hidden by default

            max_input = QDoubleSpinBox()
            max_input.setPrefix("Max: ")
            max_input.setMaximum(1e6)
            max_input.setValue(100)
            max_input.setVisible(False)  # Hidden by default

            step_input = QDoubleSpinBox()
            step_input.setPrefix("Step: ")
            step_input.setMaximum(1e6)
            step_input.setValue(10)
            step_input.setVisible(False)  # Hidden by default

            # Connect the checkbox to show/hide the min, max, and step inputs
            checkbox.toggled.connect(
                lambda checked, min_in=min_input, max_in=max_input, step_in=step_input:
                self.toggle_inputs(checked, min_in, max_in, step_in)
            )

            self.column_settings[column] = {
                'checkbox': checkbox,
                'min_input': min_input,
                'max_input': max_input,
                'step_input': step_input,
                'row_widget': row_widget
            }

            row_layout.addWidget(checkbox)
            row_layout.addWidget(min_input)
            row_layout.addWidget(max_input)
            row_layout.addWidget(step_input)
            content_layout.addWidget(row_widget)

        # finalize scroll area and main layout
        scroll_area.setWidget(content)
        self.content_widget = content
        main_layout.addWidget(scroll_area)
        self.scroll_area = scroll_area

        # Add OK and Cancel buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

        self.setLayout(main_layout)
        # auto‐adjust dialog width/height to content
        self.adjustSize()

    def apply_filter(self, text):
        """Show only numeric rows matching filter text."""
        text = text.lower()
        for col, settings in self.column_settings.items():
            settings['row_widget'].setVisible(text in col.lower())

    def toggle_inputs(self, checked: bool, min_input: QDoubleSpinBox, max_input: QDoubleSpinBox, step_input: QDoubleSpinBox):
        """Toggle the visibility of the min, max, and step inputs based on the checkbox state."""
        min_input.setVisible(checked)
        max_input.setVisible(checked)
        step_input.setVisible(checked)
        # adjust dialog size to fit newly visible widgets
        self.adjustSize()
        if checked:
            _update_scroll_width(self.content_widget, self.scroll_area)

    def get_selected_columns_with_bins(self):
        """Return a dictionary of selected columns with their bin settings."""
        selected_columns = {}
        for column, settings in self.column_settings.items():
            if settings['checkbox'].isChecked():
                min_value = settings['min_input'].value()
                max_value = settings['max_input'].value()
                step_value = settings['step_input'].value()
                if min_value < max_value and step_value > 0:
                    bins = list(range(int(min_value), int(max_value) + 1, int(step_value)))
                    selected_columns[column] = {'bins': bins}
        return selected_columns

class ColumnSelectorDialog(QDialog):
    def __init__(self, columns, parent=None, exclusive=False):
        super().__init__(parent)
        self.setWindowTitle("Select Features")
        main_layout = QVBoxLayout()

        # filter input
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter columns...")
        self.filter_edit.textChanged.connect(self.apply_filter)
        main_layout.addWidget(self.filter_edit)

        # optional exclusivity
        button_group = QButtonGroup(self)
        button_group.setExclusive(exclusive)

        # scrollable grid container
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        content = QWidget()
        grid = QGridLayout(content)
        self.checkboxes = {}
        cols_per_row = 4  # number of checkbox columns
        for idx, column in enumerate(columns):
            cb = QCheckBox(column)
            self.checkboxes[column] = cb
            button_group.addButton(cb)
            r, c = divmod(idx, cols_per_row)
            grid.addWidget(cb, r, c)
        scroll_area.setWidget(content)
        # store for width prediction and set initial width
        self.content_widget = content
        self.scroll_area = scroll_area
        _update_scroll_width(self.content_widget, self.scroll_area)
        main_layout.addWidget(scroll_area)

        # Add OK / Cancel
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

        self.setLayout(main_layout)
        # auto-adjust dialog size
        self.adjustSize()

    def apply_filter(self, text):
        """Show only checkboxes matching filter text."""
        text = text.lower()
        for col, cb in self.checkboxes.items():
            cb.setVisible(text in col.lower())
        # resize scroll area and dialog
        _update_scroll_width(self.content_widget, self.scroll_area)
        self.adjustSize()

    def get_selected_columns(self):
        """Return a list of selected columns."""
        return [col for col, checkbox in self.checkboxes.items() if checkbox.isChecked()]

class SamplingApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MIDRC Stratified Sampling")
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

        # Features input with button to open column selector dialog
        features_layout = QHBoxLayout()
        self.features_input = QLineEdit()
        self.select_columns_button = QPushButton("Select Columns")
        self.select_columns_button.clicked.connect(lambda: self.show_column_selector(self.features_input))
        features_layout.addWidget(self.features_input)
        features_layout.addWidget(self.select_columns_button)
        form_layout.addRow(QLabel("Features (comma-separated):"), features_layout)

        self.dataset_column_input = QLineEdit('dataset')
        self.dataset_column_input.setToolTip("The name of the column in the data file that contains the dataset names.")
        form_layout.addRow(QLabel("Dataset Column:"), self.dataset_column_input)

        # Datasets input with buttons to quickly set values
        datasets_layout = QHBoxLayout()
        self.datasets_input = QLineEdit(
            "{\"Fold 1\": 20, \"Fold 2\": 20, \"Fold 3\": 20, \"Fold 4\": 20, \"Fold 5\": 20}")
        self.datasets_input.setToolTip(
            "The datasets to use for the calculation. The keys are the dataset names and the values are the fractions of the data to use for each dataset.")
        self.set_folds_button = QPushButton("Set Folds")
        self.set_folds_button.clicked.connect(self.set_folds)
        self.set_train_val_button = QPushButton("Set Train/Validation")
        self.set_train_val_button.clicked.connect(self.set_train_validation)
        datasets_layout.addWidget(self.datasets_input)
        datasets_layout.addWidget(self.set_folds_button)
        datasets_layout.addWidget(self.set_train_val_button)
        form_layout.addRow(QLabel("Datasets (JSON format, e.g., {\"Train\": 0.8, \"Validation\": 0.2}):"),
                           datasets_layout)

        # Numeric columns input with button to open numeric column selector dialog
        numeric_cols_layout = QHBoxLayout()
        self.numeric_cols_input = QLineEdit()
        self.select_numeric_columns_button = QPushButton("Select Numeric Columns")
        self.select_numeric_columns_button.clicked.connect(self.show_numeric_column_selector)
        numeric_cols_layout.addWidget(self.numeric_cols_input)
        numeric_cols_layout.addWidget(self.select_numeric_columns_button)
        form_layout.addRow(QLabel("Numeric Columns (JSON format):"), numeric_cols_layout)

        # Features input with button to open column selector dialog
        uid_col_layout = QHBoxLayout()
        self.uid_col_input = QLineEdit("")
        self.select_uid_column_button = QPushButton("Select Columns")
        self.select_uid_column_button.clicked.connect(lambda: self.show_column_selector(self.uid_col_input, exclusive=True))
        uid_col_layout.addWidget(self.uid_col_input)
        uid_col_layout.addWidget(self.select_uid_column_button)
        form_layout.addRow(QLabel("Unique Identifier Column:"), uid_col_layout)
        self.uid_col_input.setToolTip(
            "The name of the column in the data file that contains the unique identifier for each row.")

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
        self.columns = []  # Will hold the columns of the loaded file

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
                self.columns = list(self.df.columns)  # Store the columns for column selector
                self.display_dataframe(self.df)
            else:
                QMessageBox.critical(self, "Invalid File", "Please select a valid TSV, CSV, or Excel file.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred while loading the file: {str(e)}")

    def show_column_selector(self, text_edit_widget: QLineEdit, *, exclusive=False):
        if self.columns:
            dialog = ColumnSelectorDialog(self.columns, self, exclusive=exclusive)
            if dialog.exec():
                selected_columns = dialog.get_selected_columns()
                text_edit_widget.setText(','.join(selected_columns))
        else:
            QMessageBox.warning(self, "No Data", "Please load a file first to select columns.")

    def show_numeric_column_selector(self):
        if self.columns:
            dialog = NumericColumnSelectorDialog(self.columns, self)
            if dialog.exec():
                selected_columns_with_bins = dialog.get_selected_columns_with_bins()
                self.numeric_cols_input.setText(str(selected_columns_with_bins))
        else:
            QMessageBox.warning(self, "No Data", "Please load a file first to select columns.")

    def set_folds(self):
        self.datasets_input.setText("{\"Fold 1\": 20, \"Fold 2\": 20, \"Fold 3\": 20, \"Fold 4\": 20, \"Fold 5\": 20}")

    def set_train_validation(self):
        self.datasets_input.setText("{\"Train\": 0.8, \"Validation\": 0.2}")

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

            # Ensure labels are set to None
            for col in numeric_cols:
                numeric_cols[col]['labels'] = None

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