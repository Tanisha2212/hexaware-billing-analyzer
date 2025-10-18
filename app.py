import streamlit as st
from csv_analyzer import analyze_csv_bulk, validate_csv_columns
import pandas as pd
import io

MONTHS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
]


def main():
    # Clean header
    st.image("logo.png", width=80)
    st.title("Hexaware Monthly Billing Analyzer")

    st.markdown("---")

    # File upload section
    st.subheader("Upload Files")
    uploaded_file = st.file_uploader("Main CSV File", type=["csv"], help="Upload the main resource allocation file")
    uploaded_file2 = st.file_uploader("Optional Update CSV", type=["csv"],
                                      help="Optional file with updated actual hours")

    if uploaded_file is not None:
        try:
            # Validate file quickly
            uploaded_file.seek(0)
            df = pd.read_csv(io.StringIO(uploaded_file.getvalue().decode("utf-8")))
            df.columns = df.columns.str.strip()
            validate_csv_columns(df, "Main CSV")

            st.success("Main CSV validated successfully")
            resource_options = df['Resource'].dropna().unique().tolist()

            # Employee adjustments section
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
                        employee_params[emp] = {
                            "employee_left": True,
                            "left_in_month": left_month,
                            "left_day": left_day,
                            "leave_month": "",
                            "leave_days": 0
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
                            "leave_days": leave_days
                        }
                    else:
                        employee_params[emp] = {
                            "employee_left": False,
                            "left_in_month": "",
                            "left_day": 0,
                            "leave_month": "",
                            "leave_days": 0
                        }

            # Process button
            st.markdown("---")
            if st.button("Process Data", type="primary"):
                with st.spinner("Processing CSV files..."):
                    try:
                        result_df = analyze_csv_bulk(uploaded_file, employee_params, uploaded_file2)

                        # Format numeric columns
                        numeric_cols = [
                                           "Total Planned Hrs", "Total Actual Hrs",
                                           "Total Planned Vs Actual Diff", "Utilization %", "Billing Amount"
                                       ] + [f"{m} Planned" for m in MONTHS] + [f"{m} Actual" for m in MONTHS]

                        for col in numeric_cols:
                            if col in result_df.columns:
                                result_df[col] = result_df[col].round(0).astype(int)

                        # Display results
                        st.subheader("Processed Results")


                        # Highlight function
                        def highlight_updates(row):
                            return ['background-color: #e6f3ff' if row['Updated From CSV2'] == 'Yes' else '' for _ in
                                    row]

                        st.dataframe(result_df.style.apply(highlight_updates, axis=1), use_container_width=True)

                        # Download section
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
                "Please check that your CSV file contains the required columns: Resource, Deputation, Average/Flat-lined Rate, and month columns (can use full names like 'January Planned' or abbreviations like 'Jan Planned')")


if __name__ == "__main__":
    main()