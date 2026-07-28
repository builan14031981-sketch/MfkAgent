class WebSearchTool:
    name = "web_search"
    description = "Search the web"

    async def search(self, query: str, limit: int = 5):
        return {"status": "not_implemented", "message": "Web search not available yet"}


web_search_tool = WebSearchTool()
