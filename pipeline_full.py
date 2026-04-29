# ---------------------------------------------------------------------------
# 0. Argument parsing
# ---------------------------------------------------------------------------
import argparse, os, warnings, time
warnings.filterwarnings("ignore")

parser = argparse.ArgumentParser(description="Local fake-news detection pipeline")
parser.add_argument("--model_dir",    default="distilbert_finetuned",
                    help="Folder containing the model + test data")
parser.add_argument("--max_articles", type=int, default=200,
                    help="Max test articles to process (0 = all)")
parser.add_argument("--batch_size",   type=int, default=16)
parser.add_argument("--output_csv",   default="",
                    help="Output CSV path (auto-named if empty)")
args = parser.parse_args()

MODEL_DIR    = args.model_dir
MAX_ARTICLES = args.max_articles   # 0 means use all
BATCH_SIZE   = args.batch_size
MAX_LEN      = 256

# ---------------------------------------------------------------------------
# 1. Imports
# ---------------------------------------------------------------------------
import numpy as np
import pandas as pd
import torch
from datetime import datetime
from collections import defaultdict
from torch.utils.data import Dataset, DataLoader
from transformers import (
    DistilBertTokenizerFast,
    DistilBertForSequenceClassification,
)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Device: {device}")

# ---------------------------------------------------------------------------
# 2. Load model + tokenizer
# ---------------------------------------------------------------------------
print(f"\nLoading model from '{MODEL_DIR}' ...")
tokenizer        = DistilBertTokenizerFast.from_pretrained(MODEL_DIR)
distilbert_model = DistilBertForSequenceClassification.from_pretrained(MODEL_DIR)
distilbert_model = distilbert_model.to(device)
distilbert_model.eval()
print("✅  Model and tokenizer loaded")

# ---------------------------------------------------------------------------
# 3. Load test data
# ---------------------------------------------------------------------------
X_test  = np.load(os.path.join(MODEL_DIR, "test_texts.npy"),    allow_pickle=True)
y_test  = np.load(os.path.join(MODEL_DIR, "test_labels.npy"),   allow_pickle=True)
history = np.load(os.path.join(MODEL_DIR, "training_history.npy"),
                  allow_pickle=True).item()

print(f"\nTest set: {len(X_test):,} articles")
print(f"  Real (0): {(y_test == 0).sum():,}")
print(f"  Fake (1): {(y_test == 1).sum():,}")
print(f"Training history keys: {list(history.keys())}")

# Optionally cap the number of articles
if MAX_ARTICLES and MAX_ARTICLES < len(X_test):
    X_test = X_test[:MAX_ARTICLES]
    y_test = y_test[:MAX_ARTICLES]
    print(f"\n(Capped to first {MAX_ARTICLES} articles for this run)")

# ---------------------------------------------------------------------------
# 4. Risk-scoring helpers (unchanged from original notebook)
# ---------------------------------------------------------------------------
CRITICALITY_MATRIX = {
    "pandemic":         {"health": 1.0, "politics": 0.8, "science/tech": 0.7,
                         "social": 0.6, "economy": 0.5, "default": 0.4},
    "election":         {"politics": 1.0, "crime/law": 0.7, "social": 0.6,
                         "intl/war": 0.5, "default": 0.3},
    "war_conflict":     {"intl/war": 1.0, "politics": 0.9, "health": 0.7,
                         "economy": 0.6, "default": 0.5},
    "natural_disaster": {"health": 0.9, "environment": 0.8,
                         "politics": 0.6, "default": 0.4},
    "economic":         {"economy": 1.0, "politics": 0.7,
                         "social": 0.6, "default": 0.3},
    "none":             {"default": 0.2},
}

RISK_TIERS  = [
    (0.8, "CRITICAL", "Immediate intervention"),
    (0.5, "HIGH",     "Alert + log for review"),
    (0.3, "MEDIUM",   "Flag for human review"),
    (0.0, "LOW",      "No action needed"),
]
FAKE_LABELS = [
    (0.8, "High confidence fake"),
    (0.5, "Likely fake"),
    (0.3, "Uncertain"),
    (0.0, "Likely real"),
]


def get_criticality_multiplier(crisis_type, article_category):
    m = CRITICALITY_MATRIX.get(crisis_type, CRITICALITY_MATRIX["none"])
    return m.get(article_category, m["default"])


def get_risk_tier(risk_score):
    for threshold, tier, action in RISK_TIERS:
        if risk_score >= threshold:
            return tier, action
    return "LOW", "No action needed"


def get_fake_label(p):
    for threshold, label in FAKE_LABELS:
        if p >= threshold:
            return label
    return "Likely real"


def compute_risk_score(fake_probability, crisis_score, crisis_type, article_category):
    mult       = get_criticality_multiplier(crisis_type, article_category)
    risk_score = max(fake_probability * crisis_score * mult,
                     fake_probability * 0.3)
    return round(min(risk_score, 1.0), 3), round(mult, 2)


# ---------------------------------------------------------------------------
# 5. DistilBERT batch inference
# ---------------------------------------------------------------------------
class ArticleDataset(Dataset):
    def __init__(self, texts, tokenizer, max_len):
        self.texts     = texts
        self.tokenizer = tokenizer
        self.max_len   = max_len

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        enc = self.tokenizer(
            str(self.texts[idx]),
            max_length=self.max_len,
            padding="max_length",
            truncation=True,
            return_attention_mask=True,
            return_tensors="pt",
        )
        return {
            "input_ids":      enc["input_ids"].squeeze(0),
            "attention_mask": enc["attention_mask"].squeeze(0),
        }


def classify_articles_distilbert(texts, model, tokenizer, device,
                                  max_len=MAX_LEN, batch_size=BATCH_SIZE):
    """Returns np.ndarray (n, 2).  Column 0 = P(fake), column 1 = P(real)."""
    if len(texts) == 0:
        return np.array([])
    loader    = DataLoader(
        ArticleDataset(texts, tokenizer, max_len),
        batch_size=batch_size,
        shuffle=False,
    )
    all_probs = []
    model.eval()
    with torch.no_grad():
        for batch in loader:
            out   = model(
                input_ids=batch["input_ids"].to(device),
                attention_mask=batch["attention_mask"].to(device),
            )
            probs = torch.softmax(out.logits, dim=-1).cpu().numpy()
            all_probs.append(probs)
    return np.vstack(all_probs)


# ---------------------------------------------------------------------------
# 6. Build mock crisis context  (no RSS fetching - local-data mode)
#    crisis_score = 0  →  risk_score is driven purely by fake_probability
# ---------------------------------------------------------------------------
MOCK_CRISIS_RESULT = {
    "crisis_score":      0.0,
    "crisis_type":       "none",
    "crisis_mode":       False,
    "adaptive_threshold": 0.5,
    "signals":           {},
    "signal_weights":    {},
    "article_count":     len(X_test),
    "classifier_used":   "local_test_data",
}

# ---------------------------------------------------------------------------
# 7. Run classifier on test texts
# ---------------------------------------------------------------------------
print(f"\n[1/3] Running DistilBERT on {len(X_test):,} test articles ...")
t0         = time.time()
probs      = classify_articles_distilbert(
    list(X_test), distilbert_model, tokenizer, device,
    max_len=MAX_LEN, batch_size=BATCH_SIZE,
)
fake_probs = probs[:, 0]
print(f"      Done in {time.time() - t0:.1f}s")

# ---------------------------------------------------------------------------
# 8. Build results DataFrame  (no zero-shot categoriser - local mode uses
#    label 'unknown' since bart-large-mnli is not required)
# ---------------------------------------------------------------------------
print("\n[2/3] Building results table ...")

crisis_score = MOCK_CRISIS_RESULT["crisis_score"]
crisis_type  = MOCK_CRISIS_RESULT["crisis_type"]

rows = []
for i in range(len(X_test)):
    fake_prob              = float(fake_probs[i])
    category               = "unknown"          # no zero-shot classifier in local mode
    cat_conf               = 0.0
    risk_score, multiplier = compute_risk_score(fake_prob, crisis_score, crisis_type, category)
    risk_tier, action      = get_risk_tier(risk_score)

    # Derive predicted label from DistilBERT (class with highest probability)
    pred_label = int(np.argmax(probs[i]))        # 0 = real, 1 = fake
    true_label = int(y_test[i])

    rows.append({
        "text_snippet":     str(X_test[i])[:120],
        "true_label":       true_label,
        "true_label_name":  "fake" if true_label == 1 else "real",
        "pred_label":       pred_label,
        "pred_label_name":  "fake" if pred_label == 1 else "real",
        "correct":          pred_label == true_label,
        "fake_probability": round(fake_prob, 4),
        "real_probability": round(float(probs[i, 1]), 4),
        "fake_label":       get_fake_label(fake_prob),
        "category":         category,
        "cat_confidence":   cat_conf,
        "crisis_score":     round(crisis_score, 3),
        "crisis_type":      crisis_type,
        "multiplier":       multiplier,
        "risk_score":       risk_score,
        "risk_tier":        risk_tier,
        "action":           action,
    })

results_df = pd.DataFrame(rows)

# ---------------------------------------------------------------------------
# 9. Summary
# ---------------------------------------------------------------------------
print("\n" + "=" * 65)
print("RESULTS SUMMARY")
print("=" * 65)

accuracy  = results_df["correct"].mean()
n_fake    = int((results_df["pred_label"] == 1).sum())
n_real    = int((results_df["pred_label"] == 0).sum())
print(f"  Articles processed  : {len(results_df):,}")
print(f"  Accuracy            : {accuracy:.4f}  ({accuracy*100:.2f}%)")
print(f"  Predicted fake      : {n_fake:,}")
print(f"  Predicted real      : {n_real:,}")

print("\n  Risk-tier distribution:")
for tier, _, _ in RISK_TIERS:
    count = int((results_df["risk_tier"] == tier).sum())
    print(f"    {tier:8} : {count:,}")

print("\n  Fake-label distribution:")
for _, label in FAKE_LABELS:
    count = int((results_df["fake_label"] == label).sum())
    print(f"    {label:25} : {count:,}")

# ---------------------------------------------------------------------------
# 10. Save to CSV
# ---------------------------------------------------------------------------
print("\n[3/3] Saving results ...")
if args.output_csv:
    out_path = args.output_csv
else:
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = f"pipeline_results_{ts}.csv"

results_df.sort_values("risk_score", ascending=False).to_csv(out_path, index=False)
print(f"✅  Results saved to '{out_path}'  ({len(results_df):,} rows)")
print(f"    Columns: {list(results_df.columns)}")