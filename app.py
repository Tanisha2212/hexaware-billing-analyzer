import streamlit as st
from csv_analyzer import analyze_csv_bulk, validate_csv_columns
import pandas as pd
import io

MONTHS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
]


def main():
    st.image("logo.png", width=80)
    st.title("Hexaware Monthly Billing Analyzer")
    st.markdown("---")

    # File upload
    st.subheader("Upload Files")
    uploaded_file = st.file_uploader("Main CSV File", type=["csv", "xlsx"], help="Upload the main resource allocation file")
    uploaded_file2 = st.file_uploader("Optional Update CSV/Excel", type=["csv", "xlsx"],
                                      help="Optional file with updated actual hours")

    if uploaded_file is not None:
        try:
            # Read CSV or Excel
            uploaded_file.seek(0)
            if uploaded_file.name.endswith(".xlsx"):
                df = pd.read_excel(uploaded_file)
            else:
                df = pd.read_csv(io.StringIO(uploaded_file.getvalue().decode("utf-8")))

            df.columns = df.columns.str.strip()
            validate_csv_columns(df, "Main CSV")

            st.success("Main CSV validated successfully ✅")
            resource_options = df['Resource'].dropna().unique().tolist()

            # Employee adjustments
            st.subheader("Employee Adjustments")
            st.write("Select employees who took leave or left the company")
            selected_employees = st.multiselect("Employees", resource_options, help="Select employees to adjust")

            employee_params = {}

            for emp in selected_employees:
                col1, col2 = st.columns(2)
                with col1:
                    leave_type = st.selectbox(
                        f"Adjustment type for {emp}",
                        ["No adjustment", "Employee left", "Leave days"],
                        key=f"type_{emp}"
                    )
                with col2:
                    if leave_type == "Employee left":
                        left_month = st.selectbox(f"Exit month", MONTHS, key=f"left_month_{emp}")
                        left_day = st.number_input(f"Exit day", min_value=1, max_value=30, value=15,
                                                   key=f"left_day_{emp}")

                        # Replacement option
                        replace = st.checkbox(f"Replace {emp} with another employee?", key=f"replace_{emp}")
                        replacement_info = {}
                        if replace:
                            replacement_name = st.text_input(f"Replacement name for {emp}", key=f"replacement_name_{emp}")
                            join_month = st.selectbox(f"Joining month for replacement", MONTHS, key=f"join_month_{emp}")
                            join_day = st.number_input(f"Joining day", min_value=1, max_value=30, value=1, key=f"join_day_{emp}")
                            replacement_info = {
                                "replacement": True,
                                "replacement_name": replacement_name,
                                "join_month": join_month,
                                "join_day": join_day
                            }

                        employee_params[emp] = {
                            "employee_left": True,
                            "left_in_month": left_month,
                            "left_day": left_day,
                            "leave_month": "",
                            "leave_days": 0,
                            "replacement_info": replacement_info
                        }

                    elif leave_type == "Leave days":
                        leave_month = st.selectbox(f"Leave month", MONTHS, key=f"leave_month_{emp}")
                        leave_days = st.number_input(f"Leave days", min_value=0, max_value=30, value=0,
                                                     key=f"leave_days_{emp}")
                        employee_params[emp] = {
                            "employee_left": False,
                            "left_in_month": "",
                            "left_day": 0,
                            "leave_month": leave_month,
                            "leave_days": leave_days,
                            "replacement_info": {}
                        }

                    else:
                        employee_params[emp] = {
                            "employee_left": False,
                            "left_in_month": "",
                            "left_day": 0,
                            "leave_month": "",
                            "leave_days": 0,
                            "replacement_info": {}
                        }

            st.markdown("---")
            # TSR optional file
            st.subheader("Optional TSR File")
            uploaded_tsr = st.file_uploader("Upload TSR File (CSV/Excel)", type=["csv", "xlsx"],
                                            help="Optional TSR file with Employee TSR codes")

            offshore_country = "Mexico"
            onsite_country = "USA"
            onshore_country = "India"

            if uploaded_tsr is not None:
                offshore_country = st.selectbox("Select Offshore Country",
                                                ["Mexico", "Philippines", "Poland", "Brazil", "Argentina"])
                offshore_factor = st.number_input(f"Conversion factor for {offshore_country} to USD", min_value=0.0,
                                                  value=1.0, step=0.01)
            else:
                offshore_factor = 1.0

            # Process button
            if st.button("Process Data", type="primary"):
                with st.spinner("Processing CSV files..."):
                    try:
                        result_df = analyze_csv_bulk(uploaded_file, employee_params, uploaded_file2)

                        numeric_cols = [
                            "Total Planned Hrs", "Total Actual Hrs",
                            "Total Planned Vs Actual Diff", "Utilization %", "Billing Amount"
                        ] + [f"{m} Planned" for m in MONTHS] + [f"{m} Actual" for m in MONTHS]

                        for col in numeric_cols:
                            if col in result_df.columns:
                                result_df[col] = result_df[col].round(0).astype(int)

                        st.subheader("Processed Results")

                        # Highlight updated rows
                        def highlight_updates(row):
                            return ['background-color: #e6f3ff' if row['Updated From CSV2'] == 'Yes' else '' for _ in row]

                        st.dataframe(result_df.style.apply(highlight_updates, axis=1), use_container_width=True)

                        st.subheader("Download Results")
                        csv_data = result_df.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            "Download CSV",
                            csv_data,
                            "processed_output.csv",
                            "text/csv",
                            help="Download the processed data as CSV"
                        )

                    except Exception as e:
                        st.error(f"Processing error: {str(e)}")

        except Exception as e:
            st.error(f"File validation error: {str(e)}")
            st.info(
                "Please check that your CSV/Excel file contains the required columns: Resource, Deputation, Average/Flat-lined Rate, and month columns."
            )


if __name__ == "__main__":
    main()
