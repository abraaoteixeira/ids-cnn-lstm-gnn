# 🏋️ TRAINING GUIDE — NF-UQ-NIDS-v2 Retreinament

Complete guide to retreining STGNN model with NF-UQ-NIDS-v2 dataset to fix concept drift.

---

## 1. MOTIVATION: Why Retrain?

### The Concept Drift Problem

**Current Status:**
- Training dataset: CIC-IDS2017 (offline, features calculated from closed flows)
- Production data: Per-packet eBPF capture (online, real-time, flow still open)
- Result: **Major distribution shift** → F1-Score drops from 0.9856 to 55.2%

**Solution:**
- New dataset: **NF-UQ-NIDS-v2** (NetFlow v9 format)
- NetFlow v9 uses packet-based aggregation (matches eBPF capture semantics)
- Expected result: **90%+ detection rate** in production

**Timeline:** 4-8 hours GPU time (Google Colab free tier)

---

## 2. SETUP: Google Colab Environment

### Step 1: Create Kaggle API Key

1. Go to https://www.kaggle.com/settings/account
2. Click "Create New API Token"
3. File `kaggle.json` will download
4. Keep this safe — you'll need it for authentication

### Step 2: Prepare Google Colab Notebook

Open Google Colab: https://colab.research.google.com/

Create new notebook and run this setup cell:

```python
# Install dependencies
!pip install -q torch torch-geometric kaggle pandas scikit-learn matplotlib

# Upload Kaggle credentials
from google.colab import files
print("Upload kaggle.json:")
files.upload()

# Configure Kaggle API
!mkdir -p ~/.kaggle
!cp kaggle.json ~/.kaggle/
!chmod 600 ~/.kaggle/kaggle.json

# Verify
!kaggle datasets list --sort-by hottest | head -5
```

---

## 3. DATA PREPARATION

### Step 3: Download NF-UQ-NIDS-v2

```python
# Download dataset from Kaggle
!kaggle datasets download -d nfuq-nids-v2

# Extract
!unzip -q nfuq-nids-v2.zip

# Check contents
!ls -lh NF-UQ-NIDS-v2/
```

Expected structure:
```
NF-UQ-NIDS-v2/
├── Training-Part-1.csv       (~2GB)
├── Training-Part-2.csv       (~2GB)
├── Testing.csv               (~500MB)
└── Features_Description.csv
```

### Step 4: Load and Explore Dataset

```python
import pandas as pd
import numpy as np

# Load training data (parts 1 & 2)
print("Loading NF-UQ-NIDS-v2...")
df_train1 = pd.read_csv('NF-UQ-NIDS-v2/Training-Part-1.csv')
df_train2 = pd.read_csv('NF-UQ-NIDS-v2/Training-Part-2.csv')
df_train = pd.concat([df_train1, df_train2], ignore_index=True)
df_test = pd.read_csv('NF-UQ-NIDS-v2/Testing.csv')

print(f"Training set: {df_train.shape}")
print(f"Test set: {df_test.shape}")
print(f"\nColumns: {df_train.columns.tolist()}")
print(f"\nClass distribution:\n{df_train['Label'].value_counts()}")
```

### Step 5: Feature Engineering

The key difference from CIC-IDS2017: **NetFlow v9 is packet-based aggregation**

```python
# NetFlow v9 features (already in format compatible with eBPF)
feature_names = [
    'Src Port', 'Dst Port', 'Protocol',
    'Flow Duration', 'Total Fwd Packets', 'Total Backward Packets',
    'Total Length of Fwd Packets', 'Total Length of Bwd Packets',
    'Fwd Packet Length Max', 'Fwd Packet Length Min', 'Fwd Packet Length Mean',
    'Bwd Packet Length Max', 'Bwd Packet Length Min', 'Bwd Packet Length Mean',
    'Flow IAT Mean', 'Flow IAT Std', 'Flow IAT Max', 'Flow IAT Min',
    'Fwd IAT Total', 'Fwd IAT Mean', 'Fwd IAT Std', 'Fwd IAT Max', 'Fwd IAT Min',
    'Bwd IAT Total', 'Bwd IAT Mean', 'Bwd IAT Std', 'Bwd IAT Max', 'Bwd IAT Min',
    # ... more features
]

# Select top features using Pearson correlation (like CIC-IDS2017)
from sklearn.preprocessing import StandardScaler

X = df_train[feature_names].fillna(0)
y = (df_train['Label'] != 'Benign').astype(int)  # Binary: 0=benign, 1=threat

# Standardize
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# Save scaler for production
import pickle
pickle.dump(scaler, open('scaler_nf_uq.pkl', 'wb'))

print(f"Features shape: {X_scaled.shape}")
print(f"Class balance: {np.bincount(y)}")
```

---

## 4. MODEL TRAINING

### Step 6: Train STGNN with NF-UQ-NIDS-v2

Update your `train.py` to accept NF-UQ data:

```python
# train_nf_uq.py — Modified training script

import torch
import torch.nn as nn
from torch_geometric.data import Data, DataLoader
from sklearn.model_selection import train_test_split
import pandas as pd
import pickle

# Load model architecture
from model import STGNN

# Load data
print("Loading NF-UQ-NIDS-v2...")
df = pd.read_csv('NF-UQ-NIDS-v2/Training-Part-1.csv')  # Use part 1 for faster iteration

# Preprocessing
feature_cols = [col for col in df.columns if col not in ['Label', 'Flow ID', 'Timestamp']]
X = df[feature_cols].fillna(0).values
y = (df['Label'] != 'Benign').astype(int).values

# Train/val split
X_train, X_val, y_train, y_val = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# Convert to tensors
X_train = torch.FloatTensor(X_train)
y_train = torch.LongTensor(y_train)
X_val = torch.FloatTensor(X_val)
y_val = torch.LongTensor(y_val)

# Model hyperparameters (TUNED FOR NF-UQ)
model = STGNN(
    in_channels=len(feature_cols),
    hidden_cnn=128,        # Increased from 64 (more capacity for larger dataset)
    hidden_lstm=256,       # Increased from 128
    hidden_gat=128,        # Increased from 64
    num_layers=3,          # Increased from 2 (more depth)
    dropout=0.4,           # Slightly increased
    pos_weight=8.0         # Adjusted for NF-UQ class balance
)

# Training parameters
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
model = model.to(device)

optimizer = torch.optim.Adam(model.parameters(), lr=5e-4)  # Lower LR for stability
loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(8.0))
scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
    optimizer, mode='max', factor=0.5, patience=5, verbose=True
)

# Training loop
epochs = 100
best_f1 = 0

for epoch in range(epochs):
    # Training
    model.train()
    logits = model(X_train)
    loss = loss_fn(logits, y_train.float().unsqueeze(1))
    
    optimizer.zero_grad()
    loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
    optimizer.step()
    
    # Validation
    model.eval()
    with torch.no_grad():
        val_logits = model(X_val)
        val_pred = (torch.sigmoid(val_logits) > 0.5).long().squeeze()
        
        # Calculate F1
        from sklearn.metrics import f1_score, precision_score, recall_score
        f1 = f1_score(y_val.cpu(), val_pred.cpu())
        prec = precision_score(y_val.cpu(), val_pred.cpu(), zero_division=0)
        rec = recall_score(y_val.cpu(), val_pred.cpu(), zero_division=0)
    
    scheduler.step(f1)
    
    if f1 > best_f1:
        best_f1 = f1
        torch.save(model.state_dict(), 'model_nf_uq_best.pt')
    
    if (epoch + 1) % 10 == 0:
        print(f"Epoch {epoch+1:3d} | Loss: {loss:.4f} | F1: {f1:.4f} | Prec: {prec:.4f} | Rec: {rec:.4f}")

print(f"\n✅ Training complete! Best F1: {best_f1:.4f}")

# Save final model
torch.save(model.state_dict(), 'model_nf_uq_final.pt')
print("✅ Model saved to model_nf_uq_final.pt")
```

### Step 7: Evaluate on Test Set

```python
# Load test data
df_test = pd.read_csv('NF-UQ-NIDS-v2/Testing.csv')
X_test = df_test[feature_cols].fillna(0).values
y_test = (df_test['Label'] != 'Benign').astype(int).values

X_test = torch.FloatTensor(X_test)
y_test = torch.LongTensor(y_test)

# Evaluate
model.eval()
with torch.no_grad():
    test_logits = model(X_test)
    test_pred = (torch.sigmoid(test_logits) > 0.5).long().squeeze()

# Metrics
from sklearn.metrics import (
    f1_score, precision_score, recall_score, 
    roc_auc_score, confusion_matrix, classification_report
)

f1 = f1_score(y_test.cpu(), test_pred.cpu())
prec = precision_score(y_test.cpu(), test_pred.cpu())
rec = recall_score(y_test.cpu(), test_pred.cpu())
auc = roc_auc_score(y_test.cpu(), torch.sigmoid(test_logits).cpu().numpy())

print("=" * 60)
print("TEST SET RESULTS (NF-UQ-NIDS-v2)")
print("=" * 60)
print(f"F1-Score:   {f1:.4f}")
print(f"Precision:  {prec:.4f}")
print(f"Recall:     {rec:.4f}")
print(f"ROC-AUC:    {auc:.4f}")
print("\nClassification Report:")
print(classification_report(y_test.cpu(), test_pred.cpu()))

cm = confusion_matrix(y_test.cpu(), test_pred.cpu())
print(f"\nConfusion Matrix:\n{cm}")
```

---

## 5. EXPORT FOR PRODUCTION

### Step 8: Export to TorchScript

```python
# Export model for production (no Python dependencies needed)

model.eval()

# Create example input matching your feature set
example_input = torch.randn(1, len(feature_cols))

# Trace the model
traced_model = torch.jit.trace(model, example_input)

# Save
traced_model.save('spectre_model_nf_uq_scripted.pt')
print("✅ Model exported to spectre_model_nf_uq_scripted.pt")

# Verify
loaded_model = torch.jit.load('spectre_model_nf_uq_scripted.pt')
test_output = loaded_model(example_input)
print(f"✅ Verification: output shape = {test_output.shape}")
```

### Step 9: Prepare for Deployment

```python
# Create deployment package

import shutil

# Create directory
!mkdir -p spectre_nf_uq_deployment
!cd spectre_nf_uq_deployment

# Copy files
!cp spectre_model_nf_uq_scripted.pt spectre_nf_uq_deployment/
!cp scaler_nf_uq.pkl spectre_nf_uq_deployment/
!cp Features_Description.csv spectre_nf_uq_deployment/

# Create config file
config = {
    "model_file": "spectre_model_nf_uq_scripted.pt",
    "scaler_file": "scaler_nf_uq.pkl",
    "feature_count": len(feature_cols),
    "f1_score": f1,
    "dataset": "NF-UQ-NIDS-v2",
    "created_date": "2026-06-01",
    "threshold": 0.70
}

import json
with open('spectre_nf_uq_deployment/config.json', 'w') as f:
    json.dump(config, f, indent=2)

print("✅ Deployment package ready in spectre_nf_uq_deployment/")
```

---

## 6. DEPLOYMENT TO PRODUCTION

### Step 10: Update receiver_gnn.py

```python
# In receiver_gnn.py, replace model loading:

# OLD:
# model = STGNN(in_channels=20, ...)
# model.load_state_dict(torch.load('spectre_model_scripted.pt'))

# NEW:
model_nf_uq = torch.jit.load('spectre_model_nf_uq_scripted.pt')
scaler_nf_uq = pickle.load(open('scaler_nf_uq.pkl', 'rb'))

# In feature extraction, use scaler_nf_uq instead of hardcoded normalization
```

### Step 11: A/B Testing (Optional)

Run both models in parallel for N days:

```python
# Compare STGNN-v1 (CIC-IDS2017) vs STGNN-v2 (NF-UQ)

pred_v1 = torch.sigmoid(model_v1(features)) > 0.70
pred_v2 = torch.sigmoid(model_nf_uq(features)) > 0.70

if pred_v1 != pred_v2:
    log_disagreement(src_ip, pred_v1, pred_v2)

# After N days, analyze disagreement rate
# If v2 is better, switch fully
```

---

## 7. EXPECTED IMPROVEMENTS

| Metric | STGNN-v1 (CIC-IDS2017) | STGNN-v2 (NF-UQ) | Improvement |
|--------|----------------------|------------------|-------------|
| **Lab F1-Score** | 0.9856 | 0.95-0.98 | Similar |
| **Production Detection Rate** | 55.2% | **90%+** | **35%+ gain** |
| **False Positives** | 1.2% | <2% | Stable |
| **Concept Drift** | High | **Minimal** | Eliminated |

---

## 8. TIMELINE & EFFORT

- **Setup:** 15 min
- **Data download:** 20 min (depends on internet)
- **Training:** 2-4 hours (GPU)
- **Evaluation:** 30 min
- **Export & deployment:** 30 min
- **Testing in production:** 1-2 weeks

**Total:** 4-8 hours of GPU time

---

## 9. TROUBLESHOOTING

### Out of Memory (OOM)
```python
# Reduce batch size
batch_size = 32  # instead of 64
# Or reduce model size
hidden_lstm = 128  # instead of 256
```

### Training too slow
```python
# Use GPU
device = torch.device('cuda')
model = model.to(device)

# Or reduce epochs
epochs = 50  # instead of 100
```

### Model not improving
```python
# Lower learning rate
lr = 1e-4  # instead of 5e-4

# Or increase dropout
dropout = 0.5  # instead of 0.4
```

---

## 10. VALIDATION CHECKLIST

Before deploying to production:

- [ ] F1-Score ≥ 0.95 on test set
- [ ] False positive rate < 5%
- [ ] Model can be loaded via torch.jit.load()
- [ ] Inference time < 200ms per batch
- [ ] Scaler can be loaded from pickle
- [ ] TorchScript export has correct output shape
- [ ] All feature columns match between training and inference
- [ ] Tested on subset of production data (honeypot)

---

## 11. ROLLBACK PLAN

If STGNN-v2 performs worse:

1. Keep STGNN-v1 weights backed up
2. Have rollback script ready:
```bash
# Stop new model
systemctl stop receiver_gnn_v2

# Restore old model
cp spectre_model_scripted.pt spectre_model_nf_uq_scripted.pt.bak
cp spectre_model_scripted_v1.pt spectre_model_scripted.pt

# Restart
systemctl start receiver_gnn
```

---

**Training Guide Version:** 2.0  
**Target Dataset:** NF-UQ-NIDS-v2  
**Expected Outcome:** 90%+ detection rate with no concept drift ✅  
**Timeline:** 4-8 hours GPU  
**Status:** Ready to execute
