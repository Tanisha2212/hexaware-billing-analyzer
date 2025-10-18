import pandas as pd

MONTHS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
]

FULL_MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]

MONTH_MAPPING = {
    "January": "Jan", "February": "Feb", "March": "Mar", "April": "Apr",
    "May": "May", "June": "Jun", "July": "Jul", "August": "Aug",
    "September": "Sep", "October": "Oct", "November": "Nov", "December": "Dec"
}

DEPUTATION_FACTORS = {
    "OFFSHORE": 0.88,
    "ONSITE": 0.95,
    "NEARSHORE": 0.90
}

STANDARD_HOURS = 21 * 8  # Total hours per month

REQUIRED_COLUMNS = ["Resource", "Deputation", "Average/Flat-lined Rate"]


def normalize_column_names(df):
    """Normalize month column names to standard format"""
    new_columns = {}

    for col in df.columns:
        original_col = col
        col_lower = col.lower().strip()

        # Check for full month names
        for full_month, short_month in MONTH_MAPPING.items():
            if full_month.lower() in col_lower:
                if "planned" in col_lower:
                    new_columns[original_col] = f"{short_month} Planned"
                elif "actual" in col_lower:
                    new_columns[original_col] = f"{short_month} Actual"
                break

        # Check for abbreviated month names
        for month in MONTHS:
            if month.lower() in col_lower:
                if "planned" in col_lower:
                    new_columns[original_col] = f"{month} Planned"
                elif "actual" in col_lower:
                    new_columns[original_col] = f"{month} Actual"
                break

    # Rename columns
    if new_columns:
        df = df.rename(columns=new_columns)

    return df


def validate_csv_columns(df, csv_name="Main CSV"):
    """Validate required columns exist in the dataframe"""
    missing_columns = []
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            missing_columns.append(col)

    if missing_columns:
        raise ValueError(f"{csv_name} is missing required columns: {', '.join(missing_columns)}")

    # Check for at least some month columns
    month_columns_found = [col for col in df.columns if any(month in col for month in MONTHS)]
    if not month_columns_found:
        # Also check for full month names
        full_month_columns_found = [col for col in df.columns if
                                    any(full_month.lower() in col.lower() for full_month in FULL_MONTHS)]
        if not full_month_columns_found:
            raise ValueError(f"{csv_name} has no month columns (Jan/January, Feb/February, etc.)")


def analyze_csv_bulk(main_csv, employee_params, aug_csv=None):
    """
    main_csv: file-like object for main CSV
    employee_params: dict of employee leave/exit info
    aug_csv: optional file-like object containing updated Actuals (like Aug)
    """
    import io

    try:
        # --- Read main CSV ---
        main_csv.seek(0)
        df = pd.read_csv(io.StringIO(main_csv.getvalue().decode("utf-8")))
        df.columns = df.columns.str.strip()  # Clean column names

        # Normalize month column names
        df = normalize_column_names(df)

        # Validate main CSV
        validate_csv_columns(df, "Main CSV")

        # --- Read second CSV if provided ---
        aug_df = None
        if aug_csv is not None:
            aug_csv.seek(0)
            aug_df = pd.read_csv(io.StringIO(aug_csv.getvalue().decode("utf-8")))
            aug_df.columns = aug_df.columns.str.strip()
            aug_df = normalize_column_names(aug_df)

            # Validate second CSV has Resource column
            if "Resource" not in aug_df.columns:
                raise ValueError("Second CSV must contain 'Resource' column")

            # Check if second CSV has any actual month columns
            actual_cols = [col for col in aug_df.columns if "Actual" in col]
            if not actual_cols:
                raise ValueError("Second CSV has no 'Actual' month columns")

    except UnicodeDecodeError:
        raise ValueError("File encoding error. Please upload a valid UTF-8 CSV file.")
    except pd.errors.EmptyDataError:
        raise ValueError("The uploaded file is empty.")
    except pd.errors.ParserError:
        raise ValueError("Unable to parse CSV file. Please check the file format.")

    output_columns = [
        "Hexaware ID's", "PPM ID", "Resource", "Project",
        "Start Date", "End date", "Empl Status", "Average/Flat-lined Rate", "Deputation"
    ]

    final_data = []

    for _, row in df.iterrows():
        resource = row["Resource"]

        # Handle missing deputation
        deputation = str(row.get("Deputation", "")).upper()
        deput_factor = DEPUTATION_FACTORS.get(deputation, 1)

        record = {col: row.get(col, "") for col in output_columns}
        record["Updated From CSV2"] = "No"

        params = employee_params.get(resource, {
            "employee_left": False,
            "left_in_month": "",
            "left_day": 0,
            "leave_month": "",
            "leave_days": 0
        })

        if params["employee_left"]:
            record["Empl Status"] = "Inactive"

        total_planned_hours = 0
        total_actual_hours = 0

        for month in MONTHS:
            planned_col = f"{month} Planned"
            actual_col = f"{month} Actual"

            # Planned hours
            planned = STANDARD_HOURS
            record[planned_col] = planned

            # Default Actual hours
            actual = STANDARD_HOURS
            if actual_col in row and not pd.isna(row[actual_col]):
                try:
                    actual = float(row[actual_col])
                except (ValueError, TypeError):
                    actual = STANDARD_HOURS

            # Override from aug_csv if available
            if aug_df is not None and actual_col in aug_df.columns:
                match_row = aug_df[aug_df["Resource"] == resource]
                if not match_row.empty and not pd.isna(match_row.iloc[0][actual_col]):
                    try:
                        actual = float(match_row.iloc[0][actual_col])
                        record["Updated From CSV2"] = "Yes"
                    except (ValueError, TypeError):
                        # Keep existing actual if conversion fails
                        pass

            # Adjust for leave or employee exit
            if params["employee_left"]:
                if month == params["left_in_month"]:
                    actual = round(STANDARD_HOURS * (params["left_day"] / 21), 2)
                elif MONTHS.index(month) > MONTHS.index(params["left_in_month"]):
                    actual = 0
            else:
                if month == params["leave_month"] and params["leave_days"] > 0:
                    actual = round(STANDARD_HOURS * ((21 - params["leave_days"]) / 21), 2)

            record[actual_col] = actual
            total_planned_hours += planned
            total_actual_hours += actual

        # Summary calculations
        record["Total Planned Hrs"] = total_planned_hours
        record["Total Actual Hrs"] = total_actual_hours
        record["Total Planned Vs Actual Diff"] = round(total_planned_hours - total_actual_hours, 2)

        # Handle division by zero for utilization
        utilization = 0
        if total_planned_hours > 0:
            utilization = round((total_actual_hours / total_planned_hours) * 100, 2)
        record["Utilization %"] = utilization

        # Handle missing rate for billing
        try:
            avg_rate = float(record.get("Average/Flat-lined Rate", 0) or 0)
        except (ValueError, TypeError):
            avg_rate = 0

        record["Billing Amount"] = round(total_actual_hours * deput_factor * avg_rate, 2)

        final_data.append(record)

    final_df = pd.DataFrame(final_data)

    # Columns order
    month_cols = []
    for m in MONTHS:
        month_cols.append(f"{m} Planned")
        month_cols.append(f"{m} Actual")

    final_df = final_df[output_columns + month_cols + [
        "Total Planned Hrs", "Total Actual Hrs",
        "Total Planned Vs Actual Diff", "Utilization %",
        "Billing Amount", "Updated From CSV2"
    ]]

    return final_df