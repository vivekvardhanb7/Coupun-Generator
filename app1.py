import sys
import asyncio
import nest_asyncio
nest_asyncio.apply()


# Windows fix for Playwright + Streamlit
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import streamlit as st
import pandas as pd
import re
import os
import zipfile
import datetime
import base64

# ================= CONFIG =================
COUPONS_PER_CUSTOMER = 20
OUTPUT_DIR = "output"
PDF_DIR = os.path.join(OUTPUT_DIR, "pdfs")
os.makedirs(PDF_DIR, exist_ok=True)

PAGE_WIDTH = "700px"
PAGE_HEIGHT = "950px"

# ================= UI =================
st.set_page_config(page_title="Coupon Generator", layout="centered")
st.title("🎟️ Coupon Generator")

people_file = st.file_uploader("Upload People Excel", type=["xlsx"])
coupon_file = st.file_uploader("Upload Coupons Excel", type=["xlsx"])
expiry_date = st.date_input("Expiry Date", value=datetime.date(2025, 12, 31))

col1, col2 = st.columns(2)
with col1:
    preview = st.button("👀 Open HTML Preview")
with col2:
    generate = st.button("🚀 Generate Coupons (PDF)")

progress_bar = st.progress(0)
status_text = st.empty()

# ================= HELPERS =================
def extract_customer_ids(df):
    ids = []
    for _, row in df.iterrows():
        for cell in row.astype(str):
            if re.fullmatch(r"\d{4,8}", cell.strip()):
                ids.append(cell.strip())
    return ids

def extract_coupon_codes(df):
    codes = []
    for _, row in df.iterrows():
        for cell in row.astype(str):
            if re.fullmatch(r"\d{8,}", cell.strip()):
                codes.append(cell.strip())
    return codes

# ================= HTML TEMPLATE =================
def build_html(customer_id, coupons, expiry):
    expiry = expiry.strftime("%d.%m.%Y")
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    with open(os.path.join(BASE_DIR, "assets", "background.png"), "rb") as f:
        bg_base64 = base64.b64encode(f.read()).decode()

    with open(os.path.join(BASE_DIR, "assets", "naf-logo.png"), "rb") as f:
        logo_base64 = base64.b64encode(f.read()).decode()

    coupons_html = "".join(
        f"<div class='coupon-box'>{c}</div>" for c in coupons
    )

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Voucher Sheet</title>

<link href="https://fonts.googleapis.com/css2?family=Darker+Grotesque:wght@700;800;900&family=Orbitron:wght@400;500;600;700;900&display=swap" rel="stylesheet">

<style>
@page {{
    size: 700px 950px;
    margin: 0;
}}

* {{
    box-sizing: border-box;
}}

html, body {{
    margin: 0;
    padding: 0;
    width: 700px;
    height: 950px;
    font-family: 'Darker Grotesque', sans-serif;
}}

.page-container {{
    width: 700px;
    height: 950px;
    position: relative;
    overflow: hidden;
    background-image: url("data:image/png;base64,{bg_base64}");
    background-size: cover;
    background-position: center;
    background-repeat: no-repeat;
}}

.header-row {{
    position: absolute;
    top: 40px;
    left: 45px;
    right: 45px;
    height: 80px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}}

.header-left {{
    display: flex;
    align-items: center;
    gap: 4px;
}}

.logo {{
    width: 120px;
}}

.main-id {{
    font-size: 49px;
    font-weight: 800;
    color: #B88A00;
}}

.header-right {{
    font-family: 'Orbitron', sans-serif;
    font-size: 24px;
    font-weight: 700;
    color: #B88A00;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-top: 20px;
}}

.grid-container {{
    position: absolute;
    top: 150px;
    left: 45px;
    right: 45px;
    bottom: 80px;
}}

.coupon-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    column-gap: 30px;
    row-gap: 16px;
}}

.coupon-box {{
    background-color: #ffffff;
    border: 3px dashed #FF9900;
    border-radius: 10px;
    height: 55px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    font-weight: 800;
    color: #333333;
}}

.footer {{
    position: absolute;
    bottom: 40px;
    left: 45px;
    right: 45px;
    display: flex;
    justify-content: space-between;
}}

.footer span {{
    font-size: 20px;
    font-weight: 800;
    color: #ffffff;
}}

.footer .validity {{
    text-transform: uppercase;
}}
</style>
</head>

<body>
<div class="page-container">

    <div class="header-row">
        <div class="header-left">
            <img class="logo" src="data:image/png;base64,{logo_base64}">
            <div class="main-id">{customer_id}</div>
        </div>
        <div class="header-right">GUTSCHEIN 2€</div>
    </div>

    <div class="grid-container">
        <div class="coupon-grid">
            {coupons_html}
        </div>
    </div>

    <div class="footer">
        <span>www.naf-halsbach.de</span>
        <span class="validity">GÜLTIG BIS {expiry}</span>
    </div>

</div>
</body>
</html>
"""

# ================= HTML PREVIEW =================
if preview and people_file and coupon_file:
    people_df = pd.read_excel(people_file)
    coupon_df = pd.read_excel(coupon_file)

    html = build_html(
        extract_customer_ids(people_df)[0],
        extract_coupon_codes(coupon_df)[:COUPONS_PER_CUSTOMER],
        expiry_date
    )

    st.download_button("⬇️ Download preview.html", html, "preview.html", "text/html")
    st.stop()

# ================= PDF GENERATION (ASYNC + FAST + ETA) =================
if generate:
    if not people_file or not coupon_file:
        st.error("❌ Upload both Excel files")
        st.stop()

    import time
    import asyncio
    from playwright.async_api import async_playwright

    people_df = pd.read_excel(people_file)
    coupon_df = pd.read_excel(coupon_file)

    ids = extract_customer_ids(people_df)
    codes = extract_coupon_codes(coupon_df)

    # Prepare tasks
    tasks, cursor = [], 0
    for cid in ids:
        chunk = codes[cursor:cursor + COUPONS_PER_CUSTOMER]
        if len(chunk) == COUPONS_PER_CUSTOMER:
            tasks.append((cid, chunk, expiry_date))
            cursor += COUPONS_PER_CUSTOMER

    total = len(tasks)
    if total == 0:
        st.error("❌ No valid coupon batches found")
        st.stop()

    progress_bar.progress(0)
    status_text.info("🚀 Generating PDFs...")

    async def run():
        pdf_paths = []
        start_time = time.time()

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu"
                ]
            )

            context = await browser.new_context()

            semaphore = asyncio.Semaphore(4)  # LIMIT parallelism (SAFE)

            async def generate_pdf(i, task):
                async with semaphore:
                    cid, coupons, expiry = task
                    page = await context.new_page()

                    await page.set_content(
                        build_html(cid, coupons, expiry),
                        wait_until="networkidle"
                    )

                    await page.evaluate("document.fonts.ready")

                    pdf_path = os.path.join(PDF_DIR, f"{cid}.pdf")
                    await page.pdf(
                        path=pdf_path,
                        width=PAGE_WIDTH,
                        height=PAGE_HEIGHT,
                        print_background=True,
                        prefer_css_page_size=True
                    )

                    await page.close()

                    # UI update
                    elapsed = time.time() - start_time
                    avg = elapsed / (i + 1)
                    remaining = avg * (total - i - 1)

                    progress_bar.progress((i + 1) / total)
                    status_text.info(
                        f"📄 {i+1}/{total} PDFs | ⏳ ETA: {int(remaining)} sec"
                    )

                    return pdf_path

            coros = [
                generate_pdf(i, task)
                for i, task in enumerate(tasks)
            ]

            pdf_paths = await asyncio.gather(*coros)

            await context.close()
            await browser.close()

        return pdf_paths

    pdf_paths = asyncio.run(run())

    # -------- ZIP Creation --------
    status_text.info("🗜️ Creating ZIP file...")

    zip_path = os.path.join(OUTPUT_DIR, "NAF_Gutscheine.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in pdf_paths:
            z.write(p, os.path.basename(p))

    status_text.success("✅ All PDFs generated successfully!")

    with open(zip_path, "rb") as f:
        st.download_button(
            "⬇️ Download ZIP",
            f.read(),
            "NAF_Gutscheine.zip",
            mime="application/zip"
        )
