# QRP 轉 PDF 工具

把拉伸試驗機的 `.QRP` 報告批次轉成向量 PDF。

## 開發

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
.venv/Scripts/pytest
.venv/Scripts/python -m src.main
```

## 打包

```bash
build.bat
```

產出：`dist/QRP轉PDF工具.exe`
