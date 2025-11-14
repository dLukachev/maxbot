# import os
# from redis.asyncio import Redis
# from dotenv import load_dotenv
#
# load_dotenv()
#
# def get_redis_async() -> Redis:
#     port = os.getenv("PORT", "XYZ")
#     return Redis(
#     host=os.getenv("HOST", "None"),
#     port=int(port),
#     decode_responses=bool(os.getenv("DECODE", "None")),
#     username=os.getenv("USERNAME", "None"),
#     password=os.getenv("PASSWORD", "None"),
# )
#
# async def get_state_r(redis: Redis, user_id: int):
#     state = await redis.get(str(user_id))
#     return state
#
# async def set_state_r(redis: Redis, user_id: int, state: str):
#     success_or_not = await redis.setnx(str(user_id), state)
#     if success_or_not:
#         await redis.expire(str(user_id), 57600)
#     return success_or_not
#
# async def delete_state_r(redis: Redis, user_id: int):
#     success_or_not = await redis.delete(str(user_id))
#     return success_or_not