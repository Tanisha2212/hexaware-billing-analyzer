#tsr_processor.py
import pandas as pd
import io

# Country mapping for deputation types
DEPUTATION_TO_COUNTRY = {
    "ONSITE": "USA",  # Fixed
    "NEARSHORE": "India",  # Fixed
    "OFFSHORE": "Mexico"  # User-configurable, default Mexico
}

# Default exchange rates (1 local currency = X USD)
DEFAULT_EXCHANGE_RATES = {
    "INR": 0.012,  # 1 INR = 0.012 USD
    "MXN": 0.058,  # 1 MXN = 0.058 USD
    "USD": 1.0  # 1 USD = 1 USD
}

# Currency mapping by country
COUNTRY_TO_CURRENCY = {
    "India": "INR",
    "Mexico": "MXN",
    "USA": "USD",
    "Philippines": "PHP",
    "Poland": "PLN",
    "Canada": "CAD",
    "Brazil": "BRL",
    "Argentina": "ARS"
}


def load_tsr_file(tsr_file):
    """
    Load TSR file (CSV or Excel) and return DataFrame
    """
    tsr_file.seek(0)
    if tsr_file.name.endswith('.xlsx'):
        tsr_df = pd.read_excel(tsr_file)
    else:
        tsr_df = pd.read_csv(io.StringIO(tsr_file.getvalue().decode("utf-8")))

    tsr_df.columns = tsr_df.columns.str.strip()

    # Validate required columns
    required_cols = ["TSR Code", "TSR Name"]
    missing = [col for col in required_cols if col not in tsr_df.columns]
    if missing:
        raise ValueError(f"TSR file missing required columns: {', '.join(missing)}")

    return tsr_df


def normalize_tsr_columns(tsr_df):
    """
    Normalize TSR column names
    """
    column_mapping = {
        "TSR code": "TSR Code",
        "Tsr Code": "TSR Code",
        "tsr code": "TSR Code",
        "TSR name": "TSR Name",
        "Tsr Name": "TSR Name",
        "tsr name": "TSR Name"
    }
    return tsr_df.rename(columns=column_mapping)


def convert_exchange_rate(rate_value, conversion_method):
    """
    Convert exchange rate based on method

    Args:
        rate_value: The rate value entered by user
        conversion_method: "multiply" or "divide"

    Returns:
        Multiply rate (1 local currency = X USD)
    """
    if conversion_method == "divide":
        # User entered: 1 USD = X local currency
        # Convert to: 1 local currency = (1/X) USD
        return 1 / rate_value if rate_value != 0 else 0
    else:
        # User entered: 1 local currency = X USD
        return rate_value


def get_tsr_amount_for_employee(tsr_df, tsr_code, deputation, offshore_country, exchange_rates):
    """
    Get TSR amount in USD for an employee based on deputation type

    Args:
        tsr_df: TSR DataFrame
        tsr_code: Employee's TSR code
        deputation: Employee's deputation type (OFFSHORE/ONSITE/NEARSHORE)
        offshore_country: Selected offshore country
        exchange_rates: Dictionary of exchange rates (multiply method)

    Returns:
        tuple: (tsr_amount_usd, tsr_name, currency_used)
    """
    if pd.isna(tsr_code) or tsr_code == "":
        return 0, "", ""

    # Extract numeric part from TSR code (e.g., "102 B" -> 102)
    tsr_code_str = str(tsr_code).strip()
    tsr_numeric = tsr_code_str.split()[0] if ' ' in tsr_code_str else tsr_code_str

    # Try to convert to int for matching
    try:
        tsr_numeric = int(tsr_numeric)
    except (ValueError, TypeError):
        return 0, "", ""

    # Find TSR record - try both numeric and string matching
    tsr_record = tsr_df[tsr_df["TSR Code"] == tsr_numeric]
    if tsr_record.empty:
        # Try string matching
        tsr_record = tsr_df[tsr_df["TSR Code"].astype(str) == str(tsr_numeric)]
    if tsr_record.empty:
        return 0, "", ""

    tsr_record = tsr_record.iloc[0]
    tsr_name = tsr_record.get("TSR Name", "")

    # Determine country based on deputation
    deputation = str(deputation).upper()
    if deputation == "OFFSHORE":
        country = offshore_country
    else:
        country = DEPUTATION_TO_COUNTRY.get(deputation, "USA")

    # Get currency for the country
    currency = COUNTRY_TO_CURRENCY.get(country, "USD")

    # Get TSR amount in local currency
    if currency not in tsr_record or pd.isna(tsr_record[currency]):
        return 0, tsr_name, currency

    try:
        tsr_local = float(tsr_record[currency])
    except (ValueError, TypeError):
        return 0, tsr_name, currency

    # Convert to USD
    exchange_rate = exchange_rates.get(currency, 1.0)
    tsr_usd = tsr_local * exchange_rate

    return round(tsr_usd, 2), tsr_name, currency


def add_tsr_to_dataframe(main_df, tsr_df, offshore_country, exchange_rates, months):
    """
    Add TSR data to main DataFrame

    Args:
        main_df: Main billing DataFrame
        tsr_df: TSR DataFrame
        offshore_country: Selected offshore country for OFFSHORE deputation
        exchange_rates: Dictionary of exchange rates
        months: List of month abbreviations

    Returns:
        Enhanced DataFrame with TSR columns
    """
    enhanced_df = main_df.copy()

    # Normalize TSR columns
    tsr_df = normalize_tsr_columns(tsr_df)

    # Debug: Print TSR file info
    print(f"TSR DataFrame columns: {tsr_df.columns.tolist()}")
    print(f"TSR DataFrame shape: {tsr_df.shape}")
    print(f"TSR Codes in file: {tsr_df['TSR Code'].tolist()}")

    # Debug: Print main file columns
    print(f"Main DataFrame columns: {enhanced_df.columns.tolist()}")

    # Add TSR Code and TSR Name columns at the beginning (after basic info)
    tsr_code_col = []
    tsr_name_col = []

    # Store monthly TSR values
    monthly_tsr_data = {}

    # Process each row
    for idx, row in enhanced_df.iterrows():
        # Try to get TSR Code from main data
        tsr_code = ""

        # Check multiple possible column names for TSR
        for col in ["TSR", "TSR Code", "TSR code", "tsr", "PPM ID"]:
            if col in row and not pd.isna(row[col]) and row[col] != "":
                tsr_code = row[col]
                print(f"Row {idx}: Found TSR code '{tsr_code}' in column '{col}'")
                break

        if not tsr_code:
            print(f"Row {idx}: No TSR code found")

        deputation = row.get("Deputation", "")
        print(f"Row {idx}: Deputation = '{deputation}'")

        # Get TSR amount for this employee
        tsr_amount_usd, tsr_name, currency = get_tsr_amount_for_employee(
            tsr_df, tsr_code, deputation, offshore_country, exchange_rates
        )

        print(f"Row {idx}: TSR Amount = {tsr_amount_usd}, TSR Name = '{tsr_name}', Currency = '{currency}'")

        tsr_code_col.append(tsr_code)
        tsr_name_col.append(tsr_name)

        # Store monthly TSR (same amount for each month)
        if idx not in monthly_tsr_data:
            monthly_tsr_data[idx] = {}

        for month in months:
            monthly_tsr_data[idx][month] = tsr_amount_usd

    # Rebuild dataframe with correct column order
    # Get all column names from enhanced_df
    all_columns = list(enhanced_df.columns)

    # Find where to insert TSR Code and TSR Name (after Deputation)
    if "Deputation" in all_columns:
        insert_pos = all_columns.index("Deputation") + 1
    else:
        insert_pos = len([col for col in all_columns if not any(m in col for m in months)])

    # Create new dataframe with reordered columns
    new_df = pd.DataFrame()

    # Add columns before TSR Code/Name
    for col in all_columns[:insert_pos]:
        new_df[col] = enhanced_df[col]

    # Add TSR Code and TSR Name
    new_df["TSR Code"] = tsr_code_col
    new_df["TSR Name"] = tsr_name_col

    # Add monthly columns in order: Planned, Actual, Billing, TSR
    total_tsr_col = []
    for idx in range(len(enhanced_df)):
        total_tsr = 0
        for month in months:
            planned_col = f"{month} Planned"
            actual_col = f"{month} Actual"
            billing_col = f"{month} Billing"
            tsr_col = f"{month} TSR"

            if planned_col in enhanced_df.columns:
                new_df.loc[idx, planned_col] = enhanced_df.loc[idx, planned_col]
            if actual_col in enhanced_df.columns:
                new_df.loc[idx, actual_col] = enhanced_df.loc[idx, actual_col]
            if billing_col in enhanced_df.columns:
                new_df.loc[idx, billing_col] = enhanced_df.loc[idx, billing_col]

            # Add TSR after billing
            tsr_value = monthly_tsr_data[idx][month]
            new_df.loc[idx, tsr_col] = tsr_value
            total_tsr += tsr_value

        total_tsr_col.append(total_tsr)

    # Add remaining columns (totals, etc.)
    remaining_cols = [col for col in all_columns[insert_pos:] if not any(m in col for m in months)]
    for col in remaining_cols:
        new_df[col] = enhanced_df[col]

    # Add Total TSR
    new_df["Total TSR"] = total_tsr_col

    # Calculate DGM columns
    new_df["DGM"] = new_df["Billing Amount"] - new_df["Total TSR"]
    new_df["%DGM"] = new_df.apply(
        lambda row: round((row["DGM"] / row["Billing Amount"]) * 100, 2) if row["Billing Amount"] != 0 else 0,
        axis=1
    )

    print(f"Final DataFrame shape: {new_df.shape}")
    print(f"TSR columns added: {[col for col in new_df.columns if 'TSR' in col]}")

    return new_df


def get_available_currencies(tsr_df):
    """
    Get list of currency columns available in TSR file
    """
    standard_cols = ["TSR Code", "TSR Name"]
    currency_cols = [col for col in tsr_df.columns if col not in standard_cols]
    return currency_cols