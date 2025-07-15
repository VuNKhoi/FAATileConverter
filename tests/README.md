## 🧪 Running Tests

To run all unit and integration tests:

```sh
pip install -r requirements.txt
pytest
```

- Unit tests are in `tests/`
- Integration/E2E tests are in GitHub Actions workflows (see `.github/workflows/`).

### Local Unit Test Coverage
- Chart code selection and regex date extraction logic
- Error handling for missing/invalid chart codes
- Metadata loading (valid, missing, corrupt)
- Download/extract single VFR/IFR chart (mocked)
- Redundant work avoidance, error handling, and metadata backup/restore
- Link extraction logic for VFR/IFR

### Not Covered by Local Unit Tests
- Actual network downloads
- Real FAA site scraping
- S3 upload and cache-control header verification
- Full pipeline/E2E (download, convert, upload)

### What Should Be Done by GitHub Actions
- All integration/E2E tests: real downloads, S3 upload, cache-control, and full pipeline
- See workflows in `.github/workflows/` for E2E and cache-control tests

All local tests print what is being tested and the result for clarity.
