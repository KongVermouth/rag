import asyncio
import httpx
import time
import uuid

async def stress_test_upload(num_concurrent=10):
    url = "http://localhost:8000/api/v1/documents/upload"
    # 模拟一个有效的 knowledge_id 和 token
    knowledge_id = 1
    token = "YOUR_TOKEN_HERE" # 实际运行时需获取有效 token
    
    async def upload_one(i):
        file_name = f"stress_test_{uuid.uuid4().hex[:8]}_!@#$%^&.txt"
        content = b"This is a stress test content. " * 1000 # 约 30KB
        
        files = {"file": (file_name, content, "text/plain")}
        data = {"knowledge_id": knowledge_id}
        headers = {"Authorization": f"Bearer {token}"}
        
        start = time.time()
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                r = await client.post(url, data=data, files=files, headers=headers)
                duration = time.time() - start
                print(f"Request {i}: Status {r.status_code}, Duration {duration:.2f}s")
                return r.status_code == 200
            except Exception as e:
                print(f"Request {i} failed: {e}")
                return False

    tasks = [upload_one(i) for i in range(num_concurrent)]
    results = await asyncio.gather(*tasks)
    
    success_rate = sum(results) / len(results) * 100
    print(f"\nSuccess Rate: {success_rate:.1f}%")

if __name__ == "__main__":
    # 实际测试前需先获取 token，此处仅为结构演示
    print("注意：运行此脚本需要有效的 JWT Token 和 Knowledge ID。")
    # asyncio.run(stress_test_upload(20))
