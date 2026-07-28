class DocumentTool:
    name = "document"
    description = "Read and process documents"

    async def read(self, file_path: str):
        return {"status": "not_implemented", "message": "Document processing not available yet"}

    async def parse(self, file_path: str):
        return {"status": "not_implemented", "message": "Document parsing not available yet"}


document_tool = DocumentTool()
