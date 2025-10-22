import pandas as pd

MONTHS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
]

DEPUTATION_FACTORS = {
    "OFFSHORE": 0.88,
    "ONSITE": 0.95,
    "NEARSHORE": 0.90
}

STANDARD_HOURS = 21 * 8  # 21 working days, 8 hours
REQUIRED_COLUMNS = ["Resource", "Deputation", "Average/Flat-lined Rate"]


def normalize_column_names(df):
    # Keep existing column names; no changes
    return df


def validate_csv_columns(df, csv_name="Main CSV"):
    missing_columns = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_columns:
        raise ValueError(f"{csv_name} is missing required columns: {', '.join(missing_columns)}")


def analyze_csv_bulk(main_csv, employee_params, aug_csv=None):
    import io

    # Read main CSV/Excel
    main_csv.seek(0)
    if main_csv.name.endswith(".xlsx"):
        df = pd.read_excel(main_csv)
    else:
        df = pd.read_csv(io.StringIO(main_csv.getvalue().decode("utf-8")))
    df.columns = df.columns.str.strip()
    df = normalize_column_names(df)
    validate_csv_columns(df)

    # Read optional updated CSV/Excel
    aug_df = None
    if aug_csv is not None:
        aug_csv.seek(0)
        if aug_csv.name.endswith(".xlsx"):
            aug_df = pd.read_excel(aug_csv)
        else:
            aug_df = pd.read_csv(io.StringIO(aug_csv.getvalue().decode("utf-8")))
        aug_df.columns = aug_df.columns.str.strip()
        aug_df = normalize_column_names(aug_df)

    output_columns = [
        "Hexaware ID's", "PPM ID", "Resource", "Project",
        "Start Date", "End date", "Empl Status", "Average/Flat-lined Rate", "Deputation"
    ]

    final_data = []

    for _, row in df.iterrows():
        resource = row["Resource"]
        deputation = str(row.get("Deputation", "")).upper()
        deput_factor = DEPUTATION_FACTORS.get(deputation, 1)

        record = {col: row.get(col, "") for col in output_columns}
        record["Updated From CSV2"] = "No"

        params = employee_params.get(resource, {
            "employee_left": False,
            "left_in_month": "",
            "left_day": 0,
            "leave_month": "",
            "leave_days": 0,
            "replacement_info": {}
        })

        if params["employee_left"]:
            record["Empl Status"] = "Inactive"

        total_planned_hours = 0
        total_actual_hours = 0

        for month in MONTHS:
            planned_col = f"{month} Planned"
            actual_col = f"{month} Actual"

            planned = STANDARD_HOURS
            actual = STANDARD_HOURS
            if actual_col in row and not pd.isna(row[actual_col]):
                try:
                    actual = float(row[actual_col])
                except (ValueError, TypeError):
                    actual = STANDARD_HOURS

            # Adjust for leave or exit
            if params["employee_left"]:
                if month == params["left_in_month"]:
                    actual = round(STANDARD_HOURS * (params["left_day"] / 21), 2)
                elif MONTHS.index(month) > MONTHS.index(params["left_in_month"]):
                    actual = 0
            elif params["leave_month"] and month == params["leave_month"]:
                actual = round(STANDARD_HOURS * ((21 - params["leave_days"]) / 21), 2)

            record[planned_col] = planned
            record[actual_col] = actual
            total_planned_hours += planned
            total_actual_hours += actual

        # Totals
        record["Total Planned Hrs"] = total_planned_hours
        record["Total Actual Hrs"] = total_actual_hours
        record["Total Planned Vs Actual Diff"] = round(total_planned_hours - total_actual_hours, 2)
        record["Utilization %"] = round((total_actual_hours / total_planned_hours) * 100, 2) if total_planned_hours else 0
        try:
            avg_rate = float(record.get("Average/Flat-lined Rate", 0) or 0)
        except (ValueError, TypeError):
            avg_rate = 0
        record["Billing Amount"] = round(total_actual_hours * deput_factor * avg_rate, 2)

        final_data.append(record)

        # ✅ Replacement employee
        rep_info = params.get("replacement_info", {})
        if rep_info.get("replacement"):
            new_record = record.copy()
            new_record["Resource"] = rep_info["replacement_name"]
            new_record["Empl Status"] = "Active"
            new_record["Updated From CSV2"] = "No"

            total_planned_hours_new = 0
            total_actual_hours_new = 0

            for month in MONTHS:
                planned_col = f"{month} Planned"
                actual_col = f"{month} Actual"

                new_record[planned_col] = STANDARD_HOURS

                actual = 0
                if month == rep_info["join_month"]:
                    actual = round(STANDARD_HOURS * ((21 - (rep_info["join_day"] - 1)) / 21), 2)

                elif MONTHS.index(month) > MONTHS.index(rep_info["join_month"]):
                    actual = STANDARD_HOURS
                new_record[actual_col] = actual

                total_planned_hours_new += STANDARD_HOURS
                total_actual_hours_new += actual

            new_record["Total Planned Hrs"] = total_planned_hours_new
            new_record["Total Actual Hrs"] = total_actual_hours_new
            new_record["Total Planned Vs Actual Diff"] = round(total_planned_hours_new - total_actual_hours_new, 2)
            new_record["Utilization %"] = round((total_actual_hours_new / total_planned_hours_new) * 100, 2) if total_planned_hours_new > 0 else 0
            try:
                avg_rate_new = float(new_record.get("Average/Flat-lined Rate", 0) or 0)
            except (ValueError, TypeError):
                avg_rate_new = 0
            new_record["Billing Amount"] = round(total_actual_hours_new * deput_factor * avg_rate_new, 2)

            final_data.append(new_record)

    # Columns order
    month_cols = []
    for m in MONTHS:
        month_cols.append(f"{m} Planned")
        month_cols.append(f"{m} Actual")

    final_df = pd.DataFrame(final_data)
    final_df = final_df[output_columns + month_cols + [
        "Total Planned Hrs", "Total Actual Hrs",
        "Total Planned Vs Actual Diff", "Utilization %",
        "Billing Amount", "Updated From CSV2"
    ]]

    return final_df
