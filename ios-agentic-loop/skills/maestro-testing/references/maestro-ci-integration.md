# Maestro CI Integration Reference

## GitHub Actions Workflow

```yaml
name: Maestro Regression Tests
on:
  pull_request:
    paths:
      - 'src/**'          # Adjust to your source paths
      - 'tests/maestro/**'
  schedule:
    - cron: '0 6 * * 1-5'  # Weekday mornings

jobs:
  maestro-test:
    runs-on: macos-15
    steps:
      - uses: actions/checkout@v4

      - name: Set up Java 21
        uses: actions/setup-java@v4
        with:
          distribution: 'temurin'
          java-version: '21'

      - name: Install Maestro
        run: curl -Ls "https://get.maestro.mobile.dev" | bash

      - name: Build app
        run: |
          # Replace with your build command
          xcodebuild -scheme YourScheme \
            -sdk iphonesimulator \
            -destination 'platform=iOS Simulator,name=iPhone 16 Pro' \
            build

      - name: Boot simulator
        run: xcrun simctl boot "iPhone 16 Pro"

      - name: Install app
        run: |
          APP_PATH=$(find ~/Library/Developer/Xcode/DerivedData \
            -name "YourApp.app" -path "*/Debug-iphonesimulator/*" \
            -maxdepth 5 | head -1)
          xcrun simctl install booted "$APP_PATH"

      - name: Run smoke tests
        run: maestro test tests/maestro/flows/smoke/

      - name: Run regression tests
        run: maestro test tests/maestro/flows/ --include-tags=regression

      - name: Upload test artifacts
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: maestro-artifacts
          path: ~/.maestro/tests/
```

## Tag-Based Filtering

Use tags to run different test subsets in different contexts:

| Context | Tags | Duration |
|---------|------|----------|
| PR check | `smoke` | < 2 min |
| Nightly | `regression` | 5-15 min |
| Release | `smoke` + `regression` + `critical` | 15-30 min |

```bash
# PR: quick smoke tests only
maestro test flows/ --include-tags=smoke

# Nightly: full regression
maestro test flows/ --include-tags=regression

# Exclude slow tests from PR checks
maestro test flows/ --exclude-tags=slow
```

## Failure Artifact Collection

Maestro saves screenshots and logs to `~/.maestro/tests/`. Upload these on failure for debugging:

```yaml
- name: Upload test artifacts
  if: failure()
  uses: actions/upload-artifact@v4
  with:
    name: maestro-failure-${{ github.run_number }}
    path: |
      ~/.maestro/tests/
      ~/Library/Logs/maestro/
    retention-days: 7
```

## Caching Strategies

Cache Maestro installation and Xcode DerivedData:

```yaml
- name: Cache Maestro
  uses: actions/cache@v4
  with:
    path: ~/.maestro
    key: maestro-${{ runner.os }}

- name: Cache DerivedData
  uses: actions/cache@v4
  with:
    path: ~/Library/Developer/Xcode/DerivedData
    key: deriveddata-${{ hashFiles('**/*.swift', '**/project.yml') }}
```

## Environment Variables

Pass test credentials and config via environment variables:

```yaml
- name: Run auth tests
  env:
    TEST_EMAIL: ${{ secrets.TEST_EMAIL }}
    TEST_PASSWORD: ${{ secrets.TEST_PASSWORD }}
  run: maestro test tests/maestro/flows/auth/
```

In Maestro flows:
```yaml
- inputText: "${TEST_EMAIL}"
```
