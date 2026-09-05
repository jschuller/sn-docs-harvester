# Example: CMDB + CSDM Harvest for CIS-DF Exam (2026-03-24)

```bash
python3 scripts/harvest.py --map-id q4dSP2Icgr1SFv5wanVXvQ \
  --subtree TWapvFkBRG6eQTu7R3FYQw -o cmdb-australia.md -v
# Result: 2.6 MB, 499 topics, ~3 min

python3 scripts/harvest.py --map-id q4dSP2Icgr1SFv5wanVXvQ \
  --subtree UM3GV9yG5VLzKkb8PTUMKQ -o csdm-australia.md -v  
# Result: 267 KB, 60 topics, ~40s
```
