class MemoryService:
    async def get_memories(self, agent_id: int, user_id: str = "default"):
        return []

    async def create_memory(self, agent_id: int, key: str, value: str, memory_type: str = "preference"):
        return None

    async def delete_memory(self, memory_id: int):
        return False


memory_service = MemoryService()
