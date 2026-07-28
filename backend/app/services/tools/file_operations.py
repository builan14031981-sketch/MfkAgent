class FileOperationsTool:
    name = "file_operations"
    description = "File system operations"

    async def read_file(self, path: str):
        return {"status": "not_implemented", "message": "File operations not available yet"}

    async def list_directory(self, path: str):
        return {"status": "not_implemented", "message": "File operations not available yet"}


file_operations_tool = FileOperationsTool()
