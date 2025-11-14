from utils.redis import get_state_r

async def going_guard(redis, user_id) -> bool:
    return False