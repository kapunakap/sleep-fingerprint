from __future__ import annotations

from io import BytesIO

import pandas as pd
import requests

INFO_URL = "https://figshare.com/ndownloader/files/53303201"
SAMPLE_BCG_URL = "https://figshare.com/ndownloader/files/53303357"


def main() -> None:
    info_response = requests.get(INFO_URL, timeout=(30, 120))
    info_response.raise_for_status()
    print("info_bytes", len(info_response.content))
    workbook = pd.ExcelFile(BytesIO(info_response.content))
    print("sheet_names", workbook.sheet_names)
    for sheet in workbook.sheet_names:
        table = pd.read_excel(workbook, sheet_name=sheet)
        print("sheet", sheet, "shape", table.shape)
        print("columns", [str(column) for column in table.columns])
        print(table.head(10).to_string(index=False))
        for column in table.columns:
            values = table[column].dropna()
            unique = values.astype(str).value_counts()
            if 0 < len(unique) <= 30:
                print("value_counts", column, unique.to_dict())

    sample = requests.get(
        SAMPLE_BCG_URL,
        headers={"Range": "bytes=0-1048575"},
        timeout=(30, 120),
    )
    sample.raise_for_status()
    print("sample_status", sample.status_code, "sample_bytes", len(sample.content))
    text = sample.content[:4096].decode("utf-8-sig", errors="replace")
    print("sample_head")
    print("\n".join(text.splitlines()[:12]))


if __name__ == "__main__":
    main()
