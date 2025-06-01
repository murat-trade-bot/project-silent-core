# Code Citations

## License: bilinmiyor
https://github.com/pulical/docktesting/tree/0e117746d3c9da168dac471a2e870ef74c0ba171/.github/workflows/pipeline.yml

```
]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run:
```

