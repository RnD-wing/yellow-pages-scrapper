import sys
import streamlit as st
import pandas as pd
import subprocess
import json
import os
import io

# Page Configuration
st.set_page_config(page_title="Yellow Pages Scraper", page_icon="🔍", layout="wide")
st.title("🔍 Yellow Pages Web Scraper")
st.write("Search Yellow Pages and export business data directly to Excel or CSV.")

# Sidebar Controls
st.sidebar.header("Scraper Settings")

# Default API key from environment variable if available
default_api_key = os.getenv("SCRAPEUNBLOCKER_KEY", "")
api_key = st.sidebar.text_input("API Key", value=default_api_key, type="password")

keyword = st.sidebar.text_input("Search Keyword", value="Plumbers")
location = st.sidebar.text_input("Location", value="New York, NY")
limit = st.sidebar.number_input("Max Results", min_value=5, max_value=300, value=30, step=5)

run_button = st.sidebar.button("🚀 Run Scraper", use_container_width=True)

# Main Execution
if run_button:
    if not api_key:
        st.error("❌ Please provide a valid ScrapeUnblocker API key.")
    elif not keyword or not location:
        st.error("❌ Please enter both a search keyword and location.")
    else:
        # Prepare environment variable for subprocess
        env = os.environ.copy()
        env["SCRAPEUNBLOCKER_KEY"] = api_key

        with st.spinner(f"Scraping '{keyword}' in '{location}'..."):
            # Construct CLI command
            cmd = [
                sys.executable, "-m", "yellow_pages_scraper", "search",
                "-l", location,
                "-n", str(limit),
                "-f", "json",
                keyword
            ]

            # Execute scraper subprocess
            process = subprocess.run(cmd, capture_output=True, text=True, env=env)

            if process.returncode == 0:
                try:
                    data = json.loads(process.stdout)
                    if data:
                        df = pd.DataFrame(data)
                        st.success(f"✅ Found {len(df)} results!")

                        # 1. Display Interactive Table On-Screen
                        st.subheader("Results Overview")
                        st.dataframe(df, use_container_width=True)

                        # 2. Export Buttons Section
                        st.subheader("Export Data")
                        col1, col2 = st.columns(2)

                        # Excel Export (.xlsx)
                        excel_buffer = io.BytesIO()
                        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                            df.to_excel(writer, index=False, sheet_name="Listings")
                        excel_data = excel_buffer.getvalue()

                        col1.download_button(
                            label="📊 Export to Excel (.xlsx)",
                            data=excel_data,
                            file_name=f"{keyword}_{location}.xlsx".replace(" ", "_"),
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )

                        # CSV Export (.csv)
                        csv_data = df.to_csv(index=False).encode('utf-8')
                        col2.download_button(
                            label="📄 Export to CSV (.csv)",
                            data=csv_data,
                            file_name=f"{keyword}_{location}.csv".replace(" ", "_"),
                            mime="text/csv",
                            use_container_width=True
                        )

                    else:
                        st.warning("⚠️ No listings found for these search terms.")
                except Exception as e:
                    st.error(f"Failed to process output: {e}")
            else:
                st.error(f"Scraper Error Output:\n```\n{process.stderr}\n```")