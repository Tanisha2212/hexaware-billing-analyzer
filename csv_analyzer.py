#csv_analyzer.py
import pandas as pd
from datetime import datetime

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

DEPUTATION_HOURS = {
    "ONSITE": 8,
    "OFFSHORE": 8.75,
    "NEARSHORE": 9
}

DEFAULT_WORKING_DAYS = 21
REQUIRED_COLUMNS_VARIANTS = [
    ["Resource", "Deputation", "Average/Flat-lined Rate"],
    ["NAME", "DEPUTATION", "Rate"],
    ["Name", "Deputation", "Rate"]
]


def normalize_column_names(df):
    """Map common column name variations to standard names"""
    column_mapping = {
        "NAME": "Resource", "Name": "Resource", "name": "Resource", "RESOURCE": "Resource",
        "NEW_EMP_ID": "Hexaware ID's", "Hexaware ID's": "Hexaware ID's", "Employee ID": "Hexaware ID's",
        "Rate": "Average/Flat-lined Rate", "RATE": "Average/Flat-lined Rate", "Average Rate": "Average/Flat-lined Rate",
        "DEPUTATION": "Deputation", "deputation": "Deputation",
        "Proj Desc": "Project", "PROJECT": "Project", "project": "Project",
        "STATUS": "Empl Status", "Status": "Empl Status", "Employee Status": "Empl Status",
        # Keep TSR column as is - don't rename it
        "TSR code": "TSR", "tsr": "TSR", "TSR Code": "TSR"
    }
    return df.rename(columns=column_mapping)


def validate_csv_columns(df, csv_name="Main CSV"):
    """Validate that required columns exist (with some flexibility)"""
    has_resource = "Resource" in df.columns
    has_deputation = "Deputation" in df.columns
    has_rate = "Average/Flat-lined Rate" in df.columns

    if not has_resource:
        raise ValueError(f"{csv_name} is missing 'Resource' or 'NAME' column")
    if not has_deputation:
        raise ValueError(f"{csv_name} is missing 'Deputation' column")
    if not has_rate:
        raise ValueError(f"{csv_name} is missing 'Average/Flat-lined Rate' or 'Rate' column")


def analyze_csv_bulk(main_csv, employee_params, working_days_config, aug_csv=None):
    import io

    main_csv.seek(0)
    if main_csv.name.endswith(".xlsx"):
        df = pd.read_excel(main_csv)
    else:
        df = pd.read_csv(io.StringIO(main_csv.getvalue().decode("utf-8")))

    df.columns = df.columns.str.strip()
    df = normalize_column_names(df)
    validate_csv_columns(df)

    # Read optional updated CSV with actual values
    aug_df = None
    aug_dict = {}
    if aug_csv is not None:
        aug_csv.seek(0)
        if aug_csv.name.endswith(".xlsx"):
            aug_df = pd.read_excel(aug_csv)
        else:
            aug_df = pd.read_csv(io.StringIO(aug_csv.getvalue().decode("utf-8")))
        aug_df.columns = aug_df.columns.str.strip()
        aug_df = normalize_column_names(aug_df)

        # Create a dictionary for quick lookup: {resource: {month: actual_hours}}
        if "Resource" in aug_df.columns:
            for _, aug_row in aug_df.iterrows():
                resource_name = aug_row["Resource"]
                aug_dict[resource_name] = {}
                for month in MONTHS:
                    actual_col = f"{month} Actual"
                    if actual_col in aug_row and not pd.isna(aug_row[actual_col]):
                        try:
                            aug_dict[resource_name][month] = float(aug_row[actual_col])
                        except (ValueError, TypeError):
                            pass

    output_columns = [
        "Hexaware ID's", "PPM ID", "Resource", "Project",
        "Start Date", "End date", "Empl Status", "Average/Flat-lined Rate", "Deputation"
    ]

    # Check if TSR column exists in input and add it to output
    tsr_column_name = None
    for possible_tsr_col in ["TSR", "TSR Code", "TSR code", "tsr"]:
        if possible_tsr_col in df.columns:
            tsr_column_name = possible_tsr_col
            output_columns.append(possible_tsr_col)
            break

    final_data = []

    for _, row in df.iterrows():
        resource = row["Resource"]
        deputation = str(row.get("Deputation", "")).upper()
        deput_factor = DEPUTATION_FACTORS.get(deputation, 1)
        deput_hours = DEPUTATION_HOURS.get(deputation, 8)

        record = {col: row.get(col, "") for col in output_columns}
        record["Updated From CSV2"] = "No"

        # Preserve TSR column if it exists
        if tsr_column_name and tsr_column_name in row:
            record[tsr_column_name] = row[tsr_column_name]

        params = employee_params.get(resource, {
            "employee_left": False,
            "left_in_month": "",
            "left_day": 0,
            "left_year": "",
            "leave_month": "",
            "leave_days": 0,
            "replacement_info": {}
        })

        if params["employee_left"]:
            record["Empl Status"] = "Inactive"
            try:
                month_num = MONTHS.index(params["left_in_month"]) + 1
                end_date_str = f"{params['left_year']}-{month_num:02d}-{params['left_day']:02d}"
                record["End date"] = end_date_str
            except:
                pass

        total_planned_hours = 0
        total_actual_hours = 0

        # Get rate for billing calculation
        try:
            avg_rate = float(record.get("Average/Flat-lined Rate", 0) or 0)
        except (ValueError, TypeError):
            avg_rate = 0

        for month in MONTHS:
            planned_col = f"{month} Planned"
            actual_col = f"{month} Actual"
            billing_col = f"{month} Billing"
            working_days = working_days_config.get(month, DEFAULT_WORKING_DAYS)
            standard_hours = working_days * deput_hours

            # PLANNED is always calculated using formula
            planned = standard_hours

            # ACTUAL: Try to get from CSV first, then calculate
            actual = None
            actual_from_csv = False

            # First, check additional CSV (aug_csv)
            if resource in aug_dict and month in aug_dict[resource]:
                actual = aug_dict[resource][month]
                actual_from_csv = True
                record["Updated From CSV2"] = "Yes"
            # Then check main CSV
            elif actual_col in row and not pd.isna(row[actual_col]):
                try:
                    actual = float(row[actual_col])
                    actual_from_csv = True
                except (ValueError, TypeError):
                    pass

            # If no actual value provided in CSV, calculate it
            if actual is None:
                actual = standard_hours

            # Apply employee adjustments ONLY if actual was not provided in CSV
            if not actual_from_csv:
                # If employee left
                if params["employee_left"]:
                    if month == params["left_in_month"]:
                        # Work partial month until leaving day
                        days_worked = params["left_day"]
                        actual = round((days_worked / working_days) * standard_hours, 2)
                    elif MONTHS.index(month) > MONTHS.index(params["left_in_month"]):
                        # After leaving month: actual = 0
                        actual = 0
                # If on leave
                elif params["leave_month"] and month == params["leave_month"]:
                    actual = round(standard_hours * ((working_days - params["leave_days"]) / working_days), 2)

            # Adjust PLANNED based on employee status
            if params["employee_left"]:
                if month == params["left_in_month"]:
                    # Planned remains full for the leaving month
                    planned = standard_hours
                elif MONTHS.index(month) > MONTHS.index(params["left_in_month"]):
                    # After leaving month: planned = 0
                    planned = 0

            # Calculate monthly billing
            monthly_billing = round(actual * deput_factor * avg_rate, 2)

            record[planned_col] = planned
            record[actual_col] = actual
            record[billing_col] = monthly_billing
            total_planned_hours += planned
            total_actual_hours += actual

        record["Total Planned Hrs"] = total_planned_hours
        record["Total Actual Hrs"] = total_actual_hours
        record["Total Planned Vs Actual Diff"] = round(total_planned_hours - total_actual_hours, 2)
        record["Utilization %"] = round((total_actual_hours / total_planned_hours) * 100,
                                        2) if total_planned_hours else 0
        record["Billing Amount"] = round(total_actual_hours * deput_factor * avg_rate, 2)
        final_data.append(record)

        # Replacement employee logic
        rep_info = params.get("replacement_info", {})
        if rep_info.get("replacement"):
            new_record = record.copy()
            new_record["Resource"] = rep_info["replacement_name"]
            new_record["Hexaware ID's"] = rep_info["replacement_id"]
            new_record["Empl Status"] = "Active"
            new_record["Updated From CSV2"] = "No"

            try:
                join_month_num = MONTHS.index(rep_info["join_month"]) + 1
                join_date_str = f"{rep_info['join_year']}-{join_month_num:02d}-{rep_info['join_day']:02d}"
                new_record["Start Date"] = join_date_str
            except:
                pass

            # Keep original End date from the project
            new_record["End date"] = row.get("End date", "")

            total_planned_hours_new = 0
            total_actual_hours_new = 0

            # Get rate for billing calculation
            try:
                avg_rate_new = float(new_record.get("Average/Flat-lined Rate", 0) or 0)
            except (ValueError, TypeError):
                avg_rate_new = 0

            for month in MONTHS:
                planned_col = f"{month} Planned"
                actual_col = f"{month} Actual"
                billing_col = f"{month} Billing"
                working_days = working_days_config.get(month, DEFAULT_WORKING_DAYS)
                standard_hours = working_days * deput_hours

                # PLANNED: Always calculated
                # Before join month: 0
                if MONTHS.index(month) < MONTHS.index(rep_info["join_month"]):
                    planned = 0
                    actual = 0
                    monthly_billing = 0
                elif month == rep_info["join_month"]:
                    # Full planned for join month
                    planned = standard_hours
                    # Actual: partial based on join day
                    days_worked = working_days - (rep_info["join_day"] - 1)
                    actual = round((days_worked / working_days) * standard_hours, 2)
                    monthly_billing = round(actual * deput_factor * avg_rate_new, 2)
                else:
                    # After join month: full hours
                    planned = standard_hours
                    actual = standard_hours
                    monthly_billing = round(actual * deput_factor * avg_rate_new, 2)

                new_record[planned_col] = planned
                new_record[actual_col] = actual
                new_record[billing_col] = monthly_billing

                total_planned_hours_new += planned
                total_actual_hours_new += actual

            new_record["Total Planned Hrs"] = total_planned_hours_new
            new_record["Total Actual Hrs"] = total_actual_hours_new
            new_record["Total Planned Vs Actual Diff"] = round(total_planned_hours_new - total_actual_hours_new, 2)
            new_record["Utilization %"] = round((total_actual_hours_new / total_planned_hours_new) * 100,
                                                2) if total_planned_hours_new > 0 else 0
            new_record["Billing Amount"] = round(total_actual_hours_new * deput_factor * avg_rate_new, 2)

            final_data.append(new_record)

    # Columns order
    month_cols = []
    for m in MONTHS:
        month_cols.append(f"{m} Planned")
        month_cols.append(f"{m} Actual")
        month_cols.append(f"{m} Billing")

    final_df = pd.DataFrame(final_data)
    final_df = final_df[output_columns + month_cols + [
        "Total Planned Hrs", "Total Actual Hrs",
        "Total Planned Vs Actual Diff", "Utilization %",
        "Billing Amount", "Updated From CSV2"
    ]]

    return final_df