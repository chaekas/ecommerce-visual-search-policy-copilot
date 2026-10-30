from __future__ import annotations

import io
import os
import uuid
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from PIL import Image

from core.analysis import assess_listing, image_color_and_histogram
from core.database import add_product, get_product, init_db, list_events, list_products, update_moderation
from core.search import search_products

APP_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = Path(os.getenv("COPILOT_UPLOAD_DIR", "data/uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
init_db()

st.set_page_config(page_title="Visual Search & Compliance Copilot", page_icon="🛍️", layout="wide")
st.markdown("""
<style>
.block-container{padding-top:1.6rem;padding-bottom:2.5rem;max-width:1400px}
.hero{padding:1.5rem 1.8rem;border-radius:18px;background:linear-gradient(120deg,#172554,#1d4ed8);color:white;margin-bottom:1.2rem}
.hero h1{font-size:2rem;margin:0 0 .4rem 0}.hero p{margin:0;color:#dbeafe}
.small-muted{color:#64748b;font-size:.9rem}
.flag{border-left:4px solid #f59e0b;padding:.6rem .8rem;background:#fffbeb;margin:.35rem 0;border-radius:4px}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.title("🛍️ Listing Copilot")
    page = st.radio("Workspace", ["Dashboard", "Product Catalog", "Visual Search", "Compliance Review", "Moderation History", "Settings"])
    st.divider()
    reviewer = st.text_input("Reviewer name", value="reviewer")
    st.caption("Prototype for decision support. Human review is required.")

st.markdown('<div class="hero"><h1>E-Commerce Visual Search & Policy Compliance Copilot</h1><p>Find similar listings, detect review-worthy risks, and make moderation decisions with explainable signals.</p></div>', unsafe_allow_html=True)
products = list_products()


def risk_badge(level: str) -> str:
    return {"High": "🔴 High", "Medium": "🟠 Medium", "Low": "🟢 Low"}.get(level, level)


def product_card(product: dict) -> None:
    cols = st.columns([1, 2, 1])
    with cols[0]:
        path = product.get("image_path", "")
        if path and Path(path).exists():
            st.image(path, use_container_width=True)
        else:
            st.caption("No available image")
    with cols[1]:
        st.markdown(f"**#{product['id']} · {product['title']}**")
        st.caption(f"{product.get('category','')} · Seller: {product.get('seller') or 'Not specified'}")
        st.write((product.get("description") or "No description")[:350])
        st.caption(f"Color estimate: {product.get('image_color','unknown')} · {risk_badge(product.get('risk_level','Low'))} · Risk {product.get('risk_score',0)}/100")
        for flag in (product.get("flags") or "").split("\n"):
            if flag.strip():
                st.markdown(f'<div class="flag">{flag}</div>', unsafe_allow_html=True)
    with cols[2]:
        st.metric("Price", f"{product.get('price',0):,.2f}")
        st.caption(product.get("status", "Pending review"))
        st.caption(str(product.get("created_at", ""))[:16])
    st.divider()


if page == "Dashboard":
    df = pd.DataFrame(products)
    total = len(products)
    flagged = sum(1 for p in products if p["risk_score"] >= 20 or p["flags"])
    high = sum(1 for p in products if p["risk_level"] == "High")
    pending = sum(1 for p in products if p["status"] == "Pending review")
    approved = sum(1 for p in products if p["status"] == "Approved")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Catalog listings", total)
    c2.metric("Flagged for review", flagged)
    c3.metric("High risk", high)
    c4.metric("Pending review", pending)
    c5.metric("Approved", approved)
    if not products:
        st.info("Your catalog is empty. Open **Product Catalog** to add your first listing.")
    else:
        left, right = st.columns(2)
        with left:
            st.subheader("Listings by risk level")
            chart = df["risk_level"].value_counts().rename_axis("Risk level").reset_index(name="Listings")
            st.plotly_chart(px.bar(chart, x="Risk level", y="Listings", color="Risk level"), use_container_width=True)
        with right:
            st.subheader("Moderation status")
            chart = df["status"].value_counts().rename_axis("Status").reset_index(name="Listings")
            st.plotly_chart(px.pie(chart, names="Status", values="Listings", hole=.45), use_container_width=True)
        st.subheader("Recently added listings")
        for product in products[:5]:
            product_card(product)
    st.caption("Risk scores are rule-based triage signals, not proof of a violation or a legal determination.")

elif page == "Product Catalog":
    st.subheader("Add a product listing")
    with st.form("product_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            title = st.text_input("Product title *", placeholder="e.g. Blue cotton backpack")
            category = st.selectbox("Category", ["Clothing", "Electronics", "Home & Kitchen", "Beauty & Personal Care", "Toys", "Sports", "Books", "Other", "Uncategorized"])
            seller = st.text_input("Seller / merchant")
            price = st.number_input("Price", min_value=0.0, value=0.0, step=1.0)
        with col2:
            description = st.text_area("Product description *", height=150)
            uploaded = st.file_uploader("Product image (JPG, PNG, WEBP)", type=["jpg", "jpeg", "png", "webp"])
        submitted = st.form_submit_button("Analyze and save listing", type="primary")
    if submitted:
        if not title.strip():
            st.error("Enter a product title.")
        elif not uploaded:
            st.error("Upload a product image so visual search can index the listing.")
        else:
            try:
                image_bytes = uploaded.getvalue()
                with Image.open(io.BytesIO(image_bytes)) as image:
                    image.verify()
                color, _ = image_color_and_histogram(image_bytes)
                assessment = assess_listing(title, description, color, category)
                safe_name = f"{uuid.uuid4().hex}{Path(uploaded.name).suffix.lower()}"
                image_path = UPLOAD_DIR / safe_name
                image_path.parent.mkdir(parents=True, exist_ok=True)
                image_path.write_bytes(image_bytes)
                flags = "\n".join(assessment["flags"])
                product_id = add_product({
                    "title": title.strip(), "description": description.strip(), "category": category,
                    "seller": seller.strip(), "price": float(price), "image_path": str(image_path),
                    "image_color": color, "risk_score": assessment["risk_score"],
                    "risk_level": assessment["risk_level"], "flags": flags,
                    "status": "Pending review",
                })
                st.success(f"Saved listing #{product_id}. Risk: {assessment['risk_level']} ({assessment['risk_score']}/100).")
                if assessment["flags"]:
                    for flag in assessment["flags"]:
                        st.warning(flag)
                else:
                    st.info("No configured rule was triggered. This does not guarantee policy compliance.")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not process image: {exc}")
    st.divider()
    st.subheader(f"Catalog ({len(products)} listings)")
    query = st.text_input("Filter catalog by title, description, category, or seller")
    risk_filter = st.multiselect("Risk level", ["Low", "Medium", "High"], default=["Low", "Medium", "High"])
    filtered = [p for p in products if p["risk_level"] in risk_filter and (not query or query.casefold() in f"{p['title']} {p['description']} {p['category']} {p['seller']}".casefold())]
    for product in filtered:
        product_card(product)

elif page == "Visual Search":
    st.subheader("Search by text, image, or both")
    query = st.text_input("Text query", placeholder="e.g. blue running shoes")
    reference = st.file_uploader("Reference image (optional)", type=["jpg", "jpeg", "png", "webp"], key="search_image")
    reference_path = ""
    if reference:
        st.image(reference, caption="Reference image", width=220)
        try:
            with Image.open(io.BytesIO(reference.getvalue())) as im:
                im.verify()
            ref_name = f"search-{uuid.uuid4().hex}{Path(reference.name).suffix.lower()}"
            ref_file = UPLOAD_DIR / ref_name
            ref_file.write_bytes(reference.getvalue())
            reference_path = str(ref_file)
        except Exception:
            st.error("The reference image could not be read.")
            reference_path = ""
    if st.button("Find similar listings", type="primary"):
        if not query.strip() and not reference_path:
            st.warning("Enter a text query or upload a reference image.")
        elif not products:
            st.info("Add products to the catalog before searching.")
        else:
            results = search_products(products, query=query, reference_image_path=reference_path, limit=50)
            st.caption("Text uses TF-IDF similarity. Image matching uses coarse color histograms, not semantic object recognition.")
            for item in results:
                cols = st.columns([1, 4, 1])
                with cols[0]:
                    if item.get("image_path") and Path(item["image_path"]).exists():
                        st.image(item["image_path"], use_container_width=True)
                with cols[1]:
                    st.markdown(f"**#{item['id']} · {item['title']}**")
                    st.write(item.get("description", ""))
                    st.caption(f"{item.get('category')} · {risk_badge(item.get('risk_level','Low'))}")
                with cols[2]:
                    st.metric("Similarity", f"{item['similarity_score']:.0%}")
                st.divider()

elif page == "Compliance Review":
    st.subheader("Human review queue")
    status_filter = st.multiselect("Moderation status", ["Pending review", "Needs investigation", "Approved", "Rejected"], default=["Pending review", "Needs investigation"])
    risk_filter = st.multiselect("Risk level", ["High", "Medium", "Low"], default=["High", "Medium"])
    queue = [p for p in products if p["status"] in status_filter and p["risk_level"] in risk_filter]
    st.caption(f"{len(queue)} listing(s) match the selected filters.")
    if not queue:
        st.success("No listings match this queue.")
    for product in queue:
        with st.expander(f"#{product['id']} · {product['title']} — {risk_badge(product['risk_level'])} ({product['risk_score']}/100)", expanded=product["risk_level"] == "High"):
            if product.get("image_path") and Path(product["image_path"]).exists():
                st.image(product["image_path"], width=300)
            st.write(product.get("description", ""))
            st.write(f"**Category:** {product['category']} | **Price:** {product['price']:.2f} | **Seller:** {product['seller'] or 'Not specified'}")
            flags = [f for f in product.get("flags", "").split("\n") if f]
            if flags:
                for flag in flags:
                    st.warning(flag)
            else:
                st.info("No configured rule triggered. Review the listing against your full marketplace policy.")
            with st.form(f"review-{product['id']}"):
                decision = st.selectbox("Decision", ["Needs investigation", "Approved", "Rejected", "Pending review"], key=f"decision-{product['id']}")
                note = st.text_area("Reviewer note / evidence", key=f"note-{product['id']}")
                if st.form_submit_button("Save decision"):
                    update_moderation(product["id"], decision, note, reviewer or "reviewer")
                    st.success("Decision saved.")
                    st.rerun()

elif page == "Moderation History":
    st.subheader("Moderation audit trail")
    events = list_events()
    if events:
        st.dataframe(pd.DataFrame(events), use_container_width=True, hide_index=True)
        csv = pd.DataFrame(events).to_csv(index=False).encode("utf-8")
        st.download_button("Export moderation history (CSV)", csv, "moderation_history.csv", "text/csv")
    else:
        st.info("No moderation decisions have been recorded yet.")
    st.subheader("Export catalog")
    if products:
        export_df = pd.DataFrame(products).drop(columns=["image_path"], errors="ignore")
        st.download_button("Export product catalog (CSV)", export_df.to_csv(index=False).encode("utf-8"), "product_catalog.csv", "text/csv")

elif page == "Settings":
    st.subheader("Prototype configuration")
    st.markdown("""
    **Current capabilities**
    - Catalog storage in local SQLite.
    - Coarse RGB histogram image similarity.
    - TF-IDF text similarity.
    - Transparent keyword and title-color review flags.
    - Human moderation decisions and an audit trail.

    **Before production**
    - Replace local storage with durable managed database and object storage.
    - Add authentication, role-based access, rate limiting, malware scanning, and audit retention controls.
    - Configure policy rules with marketplace legal/policy owners and validate them against labeled examples.
    - Integrate trained image/text embedding models and a calibrated classifier; evaluate precision, recall, false positives, and subgroup performance.
    - Add deletion, retention, consent, and privacy controls for seller/customer data.
    """)
    st.info("Amazon Reviews 2023 primarily provides review/product metadata; do not assume it contains a ready-to-use, fully labeled marketplace policy-violation dataset.")
    st.markdown("Dataset: [Amazon Reviews 2023](https://amazon-reviews-2023.github.io/)")
