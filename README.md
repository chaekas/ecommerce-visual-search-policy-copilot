# E-Commerce Visual Search & Policy Compliance Copilot

A Streamlit prototype for product catalog exploration, approximate visual search, explainable policy triage, and human moderation review.

## Features

- Product image, title, description, category, seller, and price catalog.
- Product risk triage using configurable demonstration keyword rules and rough image/title color mismatch checks.
- Text search using TF-IDF.
- Image similarity using normalized RGB color histograms.
- Dashboard, review queue, moderation decisions, audit trail, and CSV exports.
- SQLite persistence for local development.

## Run locally

Python 3.11 or 3.12 is recommended.

```bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

Open the local address printed by Streamlit (usually http://localhost:8501).

## Tests

```bash
pytest -q
```

## Dataset

Amazon Reviews 2023: https://amazon-reviews-2023.github.io/

Use its license/terms and dataset documentation to select the appropriate subset. Product/review data is not, by itself, a validated ground-truth dataset of policy violations. Avoid downloading the full dataset unless you have sufficient storage and a clear data-processing plan.

## Import a sample from Amazon Reviews 2023

The app's **Settings** page includes an on-demand importer for a small category-specific sample.
Choose a category and import up to 100 listings. The importer streams metadata, downloads available
product images, skips duplicate titles, and runs the prototype's existing review heuristics.

You can also run the app from Codespaces:

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Then open **Settings** and select **Import sample into catalog**. Start with 10–25 products.
The full Amazon Reviews 2023 collection is very large; this app intentionally does not download it all.
Imported files and SQLite records are local to the running environment. Streamlit Community Cloud's
local files are not durable, so configure persistent database and object storage before relying on imports.
The dataset contains product metadata and reviews, not verified policy-violation labels.

Source documentation: https://amazon-reviews-2023.github.io/

## Streamlit Community Cloud

1. Open https://share.streamlit.io/ and sign in with GitHub.
2. Choose **Create app** and select this repository.
3. Select branch `main` and entrypoint `app.py`.
4. Deploy. Add dependencies from `requirements.txt` (automatic when the file is at repository root).

## Important limitations

This is a functional starter/prototype, not a production moderation authority.

- **Image search:** uses coarse RGB histograms. It can retrieve images with similar colors but does not understand product identity or visual semantics. A trained vision encoder (e.g., CLIP) is needed for semantic visual retrieval.
- **Text search:** uses TF-IDF, not a large language model.
- **Compliance:** heuristic keyword and color rules produce review suggestions only. They do not prove a violation and may generate false positives/negatives. Tune rules with marketplace policy owners and labeled validation data.
- **Dataset:** Amazon Reviews 2023 is not automatically a labeled policy-compliance dataset.
- **Storage:** images and SQLite database are stored locally under `data/`, which is gitignored. Ephemeral hosting may delete them on restart/rebuild. Use durable database/object storage before relying on the app.
- **Security:** the prototype has no user authentication or role-based access. Do not upload confidential seller/customer data or expose it publicly before adding access controls.
- **Uploads:** validate and scan files, set upload quotas, and implement retention controls before production use.

## Repository layout

```
app.py
core/
  analysis.py
  database.py
  search.py
tests/
  test_analysis.py
requirements.txt
```
