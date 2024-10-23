from dataclasses import dataclass, field
from typing import Tuple

from yaml import load
try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

@dataclass(frozen=True)
class SamplingData:
    """
    Dataclass for storing sampling data information.

    Attributes:
        filename (str): The name of the file.
        dataset_column (str): The name of the dataset column. Use 'random' for random sampling.
        features (Tuple[str, ...]): Tuple of feature names.
        title (str): The title of the sampling data.
        datasets (dict): Dictionary of dataset names and their respective fractions.
        numeric_cols (dict): Dictionary of numeric column names and their respective bins.
        uid_col (str): The name of the unique identifier column.
    """
    filename: str
    dataset_column: str
    features: (Tuple[str, ...])
    title: str
    datasets: dict = field(default_factory=dict)
    numeric_cols: dict = field(default_factory=dict)
    uid_col: str = None


@dataclass
class CONFIG:
    """
    Dataclass for storing the configuration data.

    Attributes:
        filename (str): The name of the file.
        sampling_dict (dict): Dictionary of sampling data.
    """
    filename: str = 'CONFIG.yaml'
    sampling_dict: dict = field(init=False)

    def __post_init__(self):
        self._load_data()

    def _load_data(self):
        """Load the YAML data from the current filename."""
        with open(self.filename, 'r', encoding='utf-8') as stream:
            sampling_data_yaml = load(stream, Loader=Loader)  # type: ignore
        self.sampling_dict = {}
        for key, value in sampling_data_yaml.items():
            sampling_data_instance = SamplingData(
                filename=value['filename'],
                dataset_column=value['dataset_column'],
                features=tuple(value['features']),
                title=value['title'],
                datasets=value['datasets'] if 'datasets' in value else {},
                numeric_cols=value['numeric_cols'] if 'numeric_cols' in value else {},
                uid_col=value['uid_col'] if 'uid_col' in value else None,
            )
            # Add to dictionary with the title as the value from the YAML file
            self.sampling_dict[key] = sampling_data_instance

    def set_filename(self, new_filename: str):
        """Set a new filename and reload the data."""
        self.filename = new_filename
        self._load_data()
