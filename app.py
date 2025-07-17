import streamlit as st
import pandas as pd
from rapidfuzz import fuzz
from io import BytesIO
import re

st.set_page_config(page_title="UPS Australia Matching Tool", page_icon="🇦🇺")
st.title("🇦🇺 UPS Australia Recipient Matching Tool")

# --- Parameters ---
similarity_threshold = st.slider("Select similarity threshold (%)", 70, 100, 90, step=1)
max_suggestions = 3

# --- Normalize company name ---
def normalize_name(name):
    if pd.isna(name):
        return ""
    name = str(name).lower()
    name = re.sub(r'[^a-z0-9 ]', ' ', name)
    name = re.sub(r'\b(pty|ltd|limited|aust|australia|co|corp|inc|the|and|&)\b', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

# --- Determine if personal name ---
def is_personal_name(name):
    if pd.isna(name):
        return False
    tokens = str(name).strip().split()
    return len(tokens) <= 2

# --- Matching logic ---
def match_account(recipient_name, accounts_df):
    if is_personal_name(recipient_name):
        return "Cash", []

    norm_recipient = normalize_name(recipient_name)
    scores = []
    for _, row in accounts_df.iterrows():
        acct_name = row['Customer Name']
        acct_number = row['Account Number']
        norm_account = normalize_name(acct_name)
        score = fuzz.partial_ratio(norm_recipient, norm_account)
        first_two_words_match = norm_recipient.split()[:2] == norm_account.split()[:2]
        if first_two_words_match:
            score += 5  # bonus for first-two-word match
        scores.append((acct_number, acct_name, min(score, 100), first_two_words_match))

    # Sort by first_two_words match, then by score
    scores = sorted(scores, key=lambda x: (x[3], x[2]), reverse=True)
    top_matches = scores[:max_suggestions]

    if not top_matches or top_matches[0][2] < similarity_threshold:
        return "Cash", top_matches

    return top_matches[0][0], top_matches

# --- Upload Files ---
st.subheader("Step 1: Upload Files")
upload_ship = st.file_uploader("Upload Shipment File (Excel)", type=["xlsx"])
upload_acct = st.file_uploader("Upload Account List (Excel)", type=["xlsx"])

if upload_ship and upload_acct:
    try:
        ship_df = pd.read_excel(upload_ship)
        acct_df = pd.read_excel(upload_acct)

        if 'Recipient Company Name' not in ship_df.columns or 'Tracking Number' not in ship_df.columns:
            st.error("Shipment file must contain 'Recipient Company Name' and 'Tracking Number' columns.")
        elif 'Customer Name' not in acct_df.columns or 'Account Number' not in acct_df.columns:
            st.error("Account file must contain 'Customer Name' and 'Account Number' columns.")
        else:
            st.subheader("Step 2: Matching Results")
            results = []
            for _, row in ship_df.iterrows():
                recipient = row['Recipient Company Name']
                tracking = row['Tracking Number']
                matched_account, suggestions = match_account(recipient, acct_df)
                results.append({
                    "Tracking Number": tracking,
                    "Recipient Company Name": recipient,
                    "Matched Account": matched_account,
                    "Top Suggestions": "; ".join([f"{s[1]} ({s[2]}%)" for s in suggestions])
                })

            result_df = pd.DataFrame(results)
            st.dataframe(result_df)

            def to_excel(df):
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False)
                return output.getvalue()

            st.download_button("📥 Download Matching Results", data=to_excel(result_df),
                               file_name="ups_matching_result.xlsx")
    except Exception as e:
        st.error(f"Error processing file: {e}")
else:
    st.info("Please upload both files to start matching.")
