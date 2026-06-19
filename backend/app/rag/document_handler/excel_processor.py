from typing import List
from langchain_core.documents import Document


class ExcelProcessor:
    """Excel 处理器：行→自然语言，支持多级表头和多 sheet"""

    async def process(self, file_path: str) -> List[Document]:
        import openpyxl
        wb = openpyxl.load_workbook(file_path, data_only=True)
        documents = []

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows = list(ws.iter_rows(values_only=True))
            if not rows:
                continue

            headers = [str(h) if h else "" for h in rows[0]]
            sheet_context = f"[Sheet: {sheet_name}]"

            for row_idx, row in enumerate(rows[1:], start=2):
                values = [str(v) if v is not None else "" for v in row]
                if not any(values):
                    continue

                parts = []
                for h, v in zip(headers, values):
                    if v:
                        parts.append(f"{h}{v}")
                nl_text = f"{sheet_context} " + "，".join(parts)

                documents.append(Document(
                    page_content=nl_text,
                    metadata={
                        "source": file_path,
                        "sheet": sheet_name,
                        "row": row_idx,
                    }
                ))

        return documents
