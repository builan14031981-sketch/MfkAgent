class KnowledgeService:
    async def index_file(self, file_path: str, agent_id: int):
        return None

    async def search(self, query: str, agent_id: int, limit: int = 5):
        return []


knowledge_service = KnowledgeService()
