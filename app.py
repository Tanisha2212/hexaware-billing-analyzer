#app.py
import streamlit as st
from csv_analyzer import analyze_csv_bulk, validate_csv_columns, DEPUTATION_FACTORS, DEFAULT_WORKING_DAYS
from tsr_processor import (
    load_tsr_file, add_tsr_to_dataframe, convert_exchange_rate,
    DEPUTATION_TO_COUNTRY, COUNTRY_TO_CURRENCY, DEFAULT_EXCHANGE_RATES
)
import pandas as pd
import io

MONTHS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
]

OFFSHORE_COUNTRIES = ["Mexico", "Philippines", "Poland", "Brazil", "Argentina", "Canada"]


def main():
    # Clean header
    st.image("logo.png", width=80)
    st.title("Hexaware Monthly Billing Analyzer")

    st.markdown("---")

    # File upload section
    st.subheader("Upload Files")

    uploaded_file = st.file_uploader(
        "Main CSV/Excel File",
        type=["csv", "xlsx"],
        help="Upload the main resource allocation file"
    )

    uploaded_file2 = st.file_uploader(
        "Optional Update CSV/Excel",
        type=["csv", "xlsx"],
        help="Optional file with updated actual hours"
    )

    tsr_file = st.file_uploader(
        "TSR File (Optional)",
        type=["csv", "xlsx"],
        help="Upload TSR file with TSR Code, TSR Name, and currency columns (INR, MXN, USD, etc.)"
    )

    # TSR Configuration (only show if TSR file uploaded)
    tsr_config = {}
    if tsr_file is not None:
        st.subheader("TSR Configuration")

        col1, col2 = st.columns(2)
        with col1:
            offshore_country = st.selectbox(
                "Select country for OFFSHORE deputation",
                OFFSHORE_COUNTRIES,
                index=0,
                help="ONSITE=USA (fixed), NEARSHORE=India (fixed)"
            )
            tsr_config["offshore_country"] = offshore_country

        with col2:
            conversion_method = st.radio(
                "Exchange rate input method",
                ["Divide (1 USD = X local)", "Multiply (1 local = X USD)"],
                horizontal=True
            )
            tsr_config["conversion_method"] = "divide" if "Divide" in conversion_method else "multiply"

        # Get currency for selected offshore country
        offshore_currency = COUNTRY_TO_CURRENCY.get(offshore_country, "MXN")

        st.write("Exchange Rates Configuration")
        col1, col2, col3 = st.columns(3)

        exchange_rates = {}

        with col1:
            if tsr_config["conversion_method"] == "divide":
                inr_rate = st.number_input(
                    "1 USD = ? INR",
                    min_value=0.0001,
                    value=82.25,
                    step=0.01,
                    format="%.4f"
                )
                exchange_rates["INR"] = convert_exchange_rate(inr_rate, "divide")
            else:
                inr_rate = st.number_input(
                    "1 INR = ? USD",
                    min_value=0.0001,
                    value=0.012,
                    step=0.0001,
                    format="%.4f"
                )
                exchange_rates["INR"] = inr_rate

        with col2:
            if tsr_config["conversion_method"] == "divide":
                offshore_rate = st.number_input(
                    f"1 USD = ? {offshore_currency}",
                    min_value=0.0001,
                    value=17.2 if offshore_currency == "MXN" else 55.5,
                    step=0.01,
                    format="%.4f"
                )
                exchange_rates[offshore_currency] = convert_exchange_rate(offshore_rate, "divide")
            else:
                offshore_rate = st.number_input(
                    f"1 {offshore_currency} = ? USD",
                    min_value=0.0001,
                    value=0.058 if offshore_currency == "MXN" else 0.018,
                    step=0.0001,
                    format="%.4f"
                )
                exchange_rates[offshore_currency] = offshore_rate

        with col3:
            exchange_rates["USD"] = 1.0
            st.metric("USD Rate", "1.0000")

        tsr_config["exchange_rates"] = exchange_rates

    # Working days configuration
    st.subheader("Working Days Configuration")

    use_default_days = st.radio(
        "Working days setup",
        ["Use 21 days for all months", "Customize per month"],
        horizontal=True
    )

    working_days_config = {}

    if use_default_days == "Use 21 days for all months":
        for month in MONTHS:
            working_days_config[month] = 21
    else:
        st.write("Set working days for each month:")
        cols = st.columns(4)
        for idx, month in enumerate(MONTHS):
            with cols[idx % 4]:
                working_days_config[month] = st.number_input(
                    month,
                    min_value=1,
                    max_value=31,
                    value=21,
                    key=f"days_{month}"
                )

    if uploaded_file is not None:
        try:
            # Read and validate file
            uploaded_file.seek(0)
            if uploaded_file.name.endswith('.xlsx'):
                df = pd.read_excel(uploaded_file)
            else:
                df = pd.read_csv(io.StringIO(uploaded_file.getvalue().decode("utf-8")))

            df.columns = df.columns.str.strip()

            # Normalize column names
            column_mapping = {
                "NAME": "Resource", "Name": "Resource", "name": "Resource",
                "NEW_EMP_ID": "Hexaware ID's", "Employee ID": "Hexaware ID's",
                "Rate": "Average/Flat-lined Rate", "RATE": "Average/Flat-lined Rate",
                "DEPUTATION": "Deputation", "deputation": "Deputation",
                "Proj Desc": "Project", "PROJECT": "Project",
                "STATUS": "Empl Status", "Status": "Empl Status"
            }
            df = df.rename(columns=column_mapping)

            validate_csv_columns(df, "Main CSV")

            st.success("Main CSV validated successfully")
            resource_options = df['Resource'].dropna().unique().tolist()

            # Employee adjustments section
            st.subheader("Employee Adjustments")

            selected_employees = st.multiselect(
                "Select Employees",
                resource_options,
                help="Select employees who took leave or left the company"
            )

            employee_params = {}

            for emp in selected_employees:
                st.markdown(f"### {emp}")

                leave_type = st.selectbox(
                    f"Adjustment type",
                    ["No adjustment", "Employee left", "Leave days"],
                    key=f"type_{emp}"
                )

                if leave_type == "Employee left":
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        left_year = st.number_input(
                            "Exit year",
                            min_value=2020,
                            max_value=2030,
                            value=2025,
                            key=f"left_year_{emp}"
                        )
                    with col2:
                        left_month = st.selectbox(
                            f"Exit month",
                            MONTHS,
                            key=f"left_month_{emp}"
                        )
                    with col3:
                        left_day = st.number_input(
                            f"Exit day",
                            min_value=1,
                            max_value=31,
                            value=15,
                            key=f"left_day_{emp}"
                        )

                    employee_params[emp] = {
                        "employee_left": True,
                        "left_in_month": left_month,
                        "left_day": left_day,
                        "left_year": str(left_year),
                        "leave_month": "",
                        "leave_days": 0,
                        "replacement_info": {}
                    }

                    add_replacement = st.checkbox(
                        "Add replacement employee",
                        key=f"replacement_{emp}"
                    )

                    if add_replacement:
                        st.markdown(f"#### Replacement for {emp}")

                        col1, col2 = st.columns(2)
                        with col1:
                            replacement_name = st.text_input(
                                "Replacement employee name",
                                key=f"rep_name_{emp}"
                            )
                            replacement_id = st.text_input(
                                "Replacement employee ID",
                                key=f"rep_id_{emp}"
                            )

                        with col2:
                            join_year = st.number_input(
                                "Join year",
                                min_value=2020,
                                max_value=2030,
                                value=2025,
                                key=f"join_year_{emp}"
                            )
                            join_month = st.selectbox(
                                "Join month",
                                MONTHS,
                                key=f"join_month_{emp}"
                            )

                        join_day = st.number_input(
                            "Join day",
                            min_value=1,
                            max_value=31,
                            value=1,
                            key=f"join_day_{emp}"
                        )

                        if replacement_name and replacement_id:
                            employee_params[emp]["replacement_info"] = {
                                "replacement": True,
                                "replacement_name": replacement_name,
                                "replacement_id": replacement_id,
                                "join_month": join_month,
                                "join_day": join_day,
                                "join_year": str(join_year)
                            }

                elif leave_type == "Leave days":
                    col1, col2 = st.columns(2)
                    with col1:
                        leave_month = st.selectbox(
                            f"Leave month",
                            MONTHS,
                            key=f"leave_month_{emp}"
                        )
                    with col2:
                        leave_days = st.number_input(
                            f"Leave days",
                            min_value=0,
                            max_value=30,
                            value=0,
                            key=f"leave_days_{emp}"
                        )

                    employee_params[emp] = {
                        "employee_left": False,
                        "left_in_month": "",
                        "left_day": 0,
                        "left_year": "",
                        "leave_month": leave_month,
                        "leave_days": leave_days,
                        "replacement_info": {}
                    }
                else:
                    employee_params[emp] = {
                        "employee_left": False,
                        "left_in_month": "",
                        "left_day": 0,
                        "left_year": "",
                        "leave_month": "",
                        "leave_days": 0,
                        "replacement_info": {}
                    }

                st.markdown("---")

            # Process button
            st.markdown("---")
            if st.button("Process Data", type="primary", use_container_width=True):
                with st.spinner("Processing files..."):
                    try:
                        # Step 1: Process main billing data
                        result_df = analyze_csv_bulk(
                            uploaded_file,
                            employee_params,
                            working_days_config,
                            uploaded_file2
                        )

                        # Step 2: Add TSR data if TSR file provided
                        if tsr_file is not None:
                            try:
                                tsr_df = load_tsr_file(tsr_file)
                                result_df = add_tsr_to_dataframe(
                                    result_df,
                                    tsr_df,
                                    tsr_config["offshore_country"],
                                    tsr_config["exchange_rates"],
                                    MONTHS
                                )
                                st.success("TSR data processed successfully")
                            except Exception as e:
                                st.warning(f"TSR processing error: {str(e)}. Continuing without TSR data.")

                        # Format numeric columns
                        for col in result_df.columns:
                            if result_df[col].dtype in ['float64', 'int64']:
                                if "Billing" in col or "TSR" in col or "DGM" in col:
                                    result_df[col] = result_df[col].round(2)
                                else:
                                    result_df[col] = result_df[col].apply(
                                        lambda x: int(x) if x == int(x) else round(x, 2))

                        # Display summary metrics
                        col1, col2, col3, col4 = st.columns(4)

                        with col1:
                            total_employees = len(result_df)
                            st.metric("Total Employees", total_employees)

                        with col2:
                            if "Total TSR" in result_df.columns:
                                with_tsr = len(result_df[result_df["Total TSR"] > 0])
                                st.metric("With TSR Data", with_tsr)
                            else:
                                st.metric("With TSR Data", "N/A")

                        with col3:
                            if "Total TSR" in result_df.columns:
                                total_tsr = result_df["Total TSR"].sum()
                                st.metric("Total TSR Amount", f"${total_tsr:,.2f}")
                            else:
                                st.metric("Total TSR Amount", "N/A")

                        with col4:
                            total_billing = result_df["Billing Amount"].sum()
                            st.metric("Total Billing", f"${total_billing:,.2f}")

                        # Add working days to column headers
                        display_df = result_df.copy()
                        new_columns = {}
                        for col in display_df.columns:
                            for month in MONTHS:
                                if f"{month} Planned" == col:
                                    days = working_days_config.get(month, 21)
                                    new_columns[col] = f"{col} ({days}d)"

                        if new_columns:
                            display_df = display_df.rename(columns=new_columns)

                        # Highlight function
                        def highlight_updates(row):
                            if row.get('Updated From CSV2') == 'Yes':
                                return ['background-color: #e6f3ff'] * len(row)
                            elif row.get('Empl Status') == 'Inactive':
                                return ['background-color: #ffe6e6'] * len(row)
                            else:
                                return [''] * len(row)

                        st.dataframe(
                            display_df.style.apply(highlight_updates, axis=1),
                            use_container_width=True,
                            height=600
                        )

                        st.info("Blue rows = Updated from CSV2 | Red rows = Inactive employees")

                        # Download section
                        st.subheader("Download Results")

                        col1, col2 = st.columns(2)

                        with col1:
                            csv_data = result_df.to_csv(index=False).encode('utf-8')
                            st.download_button(
                                "Download as CSV",
                                csv_data,
                                "processed_output.csv",
                                "text/csv",
                                use_container_width=True
                            )

                        with col2:
                            output = io.BytesIO()
                            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                                result_df.to_excel(writer, index=False, sheet_name='Billing Analysis')
                            excel_data = output.getvalue()

                            st.download_button(
                                "Download as Excel",
                                excel_data,
                                "processed_output.xlsx",
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True
                            )

                    except Exception as e:
                        st.error(f"Processing error: {str(e)}")
                        st.exception(e)

        except Exception as e:
            st.error(f"File validation error: {str(e)}")
            st.info(
                "Please check that your file contains the required columns: "
                "Resource/NAME, Deputation, Average/Flat-lined Rate/Rate, and month columns"
            )
    else:
        st.info("Please upload a CSV or Excel file to begin")


if __name__ == "__main__":
    st.set_page_config(
        page_title="Hexaware Billing Analyzer",
        page_icon="chart_with_upwards_trend",
        layout="wide"
    )
    main()