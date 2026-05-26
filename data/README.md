# OULAD Dataset — Download Instructions

## How to Download

1. Go to: <https://analyse.kmi.open.ac.uk/open_dataset>
2. Click **Download the dataset** and save the ZIP file.
3. Extract **all CSV files** into `data/raw/` in this project.

## Required Files

After extraction, `data/raw/` must contain exactly these seven files:

| File | Description |
|------|-------------|
| `courses.csv` | Module and presentation metadata |
| `assessments.csv` | Assessment metadata (type, weight, due date) |
| `vle.csv` | Virtual Learning Environment resource metadata |
| `studentInfo.csv` | Student demographics and final results |
| `studentRegistration.csv` | Registration and unregistration dates |
| `studentVle.csv` | Daily click counts per VLE resource |
| `studentAssessment.csv` | Per-student assessment scores and submission dates |

## Citation

> Kuzilek, J., Hlosta, M., & Zdrahal, Z. (2017).
> *Open University Learning Analytics dataset*.
> Scientific Data, 4, 170171.
> <https://doi.org/10.1038/sdata.2017.171>
