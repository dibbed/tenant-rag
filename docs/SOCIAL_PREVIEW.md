# GitHub Social Preview Card Specification

This specification defines the visual assets, layout, typography, and content for the repository's 1280×640 px OpenGraph social preview image.

---

## 1. Technical Dimensions & Canvas
- **Resolution:** 1280 × 640 px
- **Aspect Ratio:** 2:1
- **Format:** PNG / WebP
- **Background Color:** Dark slate `#0F172A` with subtle technical dot grid (`#1E293B`)
- **Accent Gradients:** Radial glow in top-right corner using `#0284C7` (Sky blue) and `#0D9488` (Teal) at 12% opacity.

---

## 2. Text & Typography

### Primary Header
- **Text:** `TenantRAG`
- **Font:** Inter / System Sans-serif, Bold (700 weight)
- **Size:** 68 px
- **Color:** White `#FFFFFF`

### Subtitle / Positioning Statement
- **Text:** `Multi-Tenant RAG Infrastructure for SaaS Backends`
- **Font:** Inter / System Sans-serif, SemiBold (600 weight)
- **Size:** 32 px
- **Color:** Teal `#2DD4BF`

### Description Line
- **Text:** `Isolated Vector Stores • Tenant Semantic Cache • SHA-256 Auth`
- **Font:** Inter / System Sans-serif, Regular (400 weight)
- **Size:** 22 px
- **Color:** Muted slate `#94A3B8`

### Technology Footer (Pill Tags)
- **Text items:** `FastAPI` • `FAISS` • `Qdrant` • `ChromaDB` • `Ollama`
- **Color:** Slate `#64748B` with subtle pill borders (`#334155`)
- **Size:** 18 px

---

## 3. Visual Graphic: Multi-Tenant Cell Isolation

The right side (approx. 450 px width) features an architectural diagram illustrating tenant separation:

```
          ┌─────────────────────────┐
          │     FastAPI Router      │
          │   [X-Tenant-ID Match]   │
          └────────────┬────────────┘
                       │
         ┌─────────────┴─────────────┐
         ▼                           ▼
┌──────────────────┐       ┌──────────────────┐
│ Tenant Cell A    │       │ Tenant Cell B    │
├──────────────────┤       ├──────────────────┤
│ • Cache A        │       │ • Cache B        │
│ • FAISS Store A  │       │ • FAISS Store B  │
│   (docs/tenant_A)│       │   (docs/tenant_B)│
└──────────────────┘       └──────────────────┘
```

- Each tenant cell is rendered as an isolated rounded container with its own color accent.
- Connecting lines from the central API router show strict, non-intersecting pathways to visually demonstrate zero cross-tenant data leakage.
- **Strict rule:** No fabricated benchmarks (e.g. no "sub-50ms" or "<500MB" text).
