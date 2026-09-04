from arq import create_pool

from app.worker import REDIS

if __name__ == "__main__":
    import asyncio

    async def main():
        redis = await create_pool(REDIS)
        job = await redis.enqueue_job("hello", "Anna")
        print(job.job_id)
        result = await job.result()
        print(f"result: {result}")

    asyncio.run(main())