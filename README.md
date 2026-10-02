---
title: Cymatic Physics Engine — CPE E2 v7.15
emoji: 🌀
colorFrom: blue
colorTo: purple
sdk: gradio
sdk_version: 5.50.0
app_file: app.py
python_version: "3.11"
pinned: false
---

# CPE E2 v7.15 — Full Platform Restoration

Full experimental interface and computational pipeline with explicit evidence gates. This release is maintained on the isolated GitHub branch \`full-app-v7.15\`.

## Run locally

Use Python 3.11 in a virtual environment:

\`\`\`powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python app.py
\`\`\`

The Gradio interface should start locally and print its URL. Do not expose a local development server publicly without a separate security review.

## Validation

The release workflow installs \`requirements.txt\`, compiles Python sources, runs the application and HFR-02 unit tests, and constructs the Gradio app as a smoke test. A successful software test does not constitute scientific or physical validation.

## Scientific claim guard

Audio STFT features are audio-domain measurements. They are not calibrated sound-pressure levels, spatial cymatic fields, plate resonances, or particle/contact measurements. The HFR-06 canonical source-hash gate remains closed for the alternate Russian «мама» recording. Physical claims require independently documented calibrated measurements and controls.

## Deployment safety

The release workflow never deploys to the production Space. Optional deployment is permitted only to a separately configured staging Space using the GitHub Actions secret \`HF_TOKEN\` and repository variable \`HF_STAGING_SPACE\`. Do not point the staging variable at the production Space.
