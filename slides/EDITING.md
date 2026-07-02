# Marp slides

```bash
npm ci
npm run dev
```

Edit `YYYY-MM-DD/slides.md` and `theme/research.css`.

```bash
npm run build -- YYYY-MM-DD/slides.md -o YYYY-MM-DD/slides.pdf
```

Commit Markdown, CSS, deck assets, and the final PDF. Do not commit
`node_modules/` or `.render/`.
