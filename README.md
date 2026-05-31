# Modular Image Encryption — Confusion × Diffusion

A modular image-encryption pipeline with swappable **confusion** (permutation)
and **diffusion** (value-mixing) primitives, a Streamlit frontend, and a
security-metrics harness. Built as a comparative framework for studying novel
image-encryption building blocks.

> ⚠️ **Research / coursework tool — not a cryptographically vetted cipher.**
> Use it to study confusion–diffusion behaviour, not to protect real secrets.

## Modules

| Stage | Module | Idea |
|-------|--------|------|
| Confusion | `perm` | Keyed global pixel permutation (baseline) |
| Confusion | `spectral` | Graph-spectral block ordering via the Fiedler vector |
| Diffusion | `xor` | Keyed XOR keystream (baseline) |
| Diffusion | `latin` | Keyed Latin-square additive mixing (balanced, linear) |
| Diffusion | `inn` | Keyed integer coupling network (RealNVP-style, lossless) |

The pipeline runs `confusion → diffusion` for `R` rounds. Every combination is
exactly invertible: `decrypt(encrypt(x)) == x`.

## Quickstart

```bash
pip install -r requirements.txt
streamlit run app.py
```

Run the correctness + metrics harness:

```bash
python test_core.py
```

## Results (built-in test pattern, perm + inn, 3 rounds)

| Metric | Value | Ideal |
|--------|-------|-------|
| Cipher entropy | 7.997 | 8.0 |
| Adjacent-pixel correlation | -0.0006 | ~0 |
| NPCR | 99.63% | ~99.6 |
| UACI | 33.47% | ~33.4 |

## Files

- `crypto_core.py` — pipeline and all swappable primitives
- `app.py` — Streamlit frontend
- `test_core.py` — round-trip, key-sensitivity, and metrics tests
- `requirements.txt` — dependencies

## License

MIT
