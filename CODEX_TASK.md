# Codex Task: Commit the Documentation Foundation

Create or update the repository with the files in this package.

Then:

1. Validate all relative Markdown links.
2. Preserve the folder structure.
3. Do not invent Kirk API calls.
4. Do not convert expected benchmark behaviour into reported results.
5. Commit with:

```bash
git add .
git commit -m "Add Kirk developer guide foundation and benchmark framework"
git push origin main
```

Suggested next task:

> Implement the synthetic data generator for Benchmark 001 without adding a Kirk integration until the actual connector API is supplied.
