"""Generate blog figures from the real pipeline on the default cat image.
Run: python docs/make_figures.py   (writes PNGs into docs/)."""
import os
import sys
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import crypto_core as cc

KEY, CONF, DIFF, ROUNDS = "wheresmyfoodkaren", "perm", "inn", 3


def entropy(a):
    h = np.bincount(a.reshape(-1), minlength=256).astype(float)
    p = h / h.sum(); p = p[p > 0]
    return float(-(p * np.log2(p)).sum())


def corr_adjacent(a):
    x = a.reshape(-1).astype(float)
    return float(np.corrcoef(x[:-1], x[1:])[0, 1])


def load_cat():
    pil = Image.open(os.path.join(ROOT, "assets", "cat-meme.jpg")).convert("RGB")
    pil.thumbnail((512, 512))
    return np.array(pil, dtype=np.uint8)


def encrypt_trace(img):
    shape = img.shape
    flat = img.reshape(-1).astype(np.uint8)
    steps = [("Original", flat.copy())]
    for r in range(ROUNDS):
        flat = cc._confuse(flat, shape, KEY, CONF, False, r)
        steps.append((f"R{r+1} confusion ({CONF})", flat.copy()))
        flat = cc._diffuse(flat, KEY, DIFF, False, r)
        steps.append(("Encrypted" if r == ROUNDS - 1 else f"R{r+1} diffusion ({DIFF})", flat.copy()))
    return shape, steps


def decrypt_trace(enc):
    shape = enc.shape
    flat = enc.reshape(-1).astype(np.uint8)
    steps = [("Encrypted", flat.copy())]
    for r in reversed(range(ROUNDS)):
        flat = cc._diffuse(flat, KEY, DIFF, True, r)
        steps.append((f"R{r+1} un-diffusion ({DIFF})", flat.copy()))
        flat = cc._confuse(flat, shape, KEY, CONF, True, r)
        steps.append(("Decrypted" if r == 0 else f"R{r+1} un-confusion ({CONF})", flat.copy()))
    return shape, steps


def gallery(shape, steps, path, title):
    n = len(steps)
    cols = 4
    rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 3.0, rows * 3.0))
    axes = np.array(axes).reshape(-1)
    for ax in axes:
        ax.axis("off")
    for ax, (label, fl) in zip(axes, steps):
        ax.imshow(fl.reshape(shape))
        ax.set_title(f"{label}\nentropy {entropy(fl):.3f} | adj-corr {corr_adjacent(fl):+.3f}",
                     fontsize=9)
    fig.suptitle(title, fontsize=14, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)
    print("wrote", path)


def histograms(img, enc, path):
    fig, ax = plt.subplots(1, 2, figsize=(9, 3))
    ax[0].hist(img.reshape(-1), bins=64, color="#4C78A8")
    ax[0].set_title(f"Plaintext histogram (entropy {entropy(img):.3f})", fontsize=10)
    ax[1].hist(enc.reshape(-1), bins=64, color="#E45756")
    ax[1].set_title(f"Ciphertext histogram (entropy {entropy(enc):.3f})", fontsize=10)
    for a in ax:
        a.set_xlim(0, 255); a.tick_params(labelsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)
    print("wrote", path)


def main():
    img = load_cat()
    eshape, esteps = encrypt_trace(img)
    enc = esteps[-1][1].reshape(eshape)
    _, dsteps = decrypt_trace(enc)
    gallery(eshape, esteps, os.path.join(HERE, "encryption-steps.png"), "Encryption, step by step")
    gallery(eshape, dsteps, os.path.join(HERE, "decryption-steps.png"), "Decryption, step by step")
    histograms(img, enc, os.path.join(HERE, "histograms.png"))


if __name__ == "__main__":
    main()
