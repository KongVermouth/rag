import asyncio
import httpx
import sys

async def verify_es_ik():
    es_url = "http://localhost:9200"
    print(f"正在验证 Elasticsearch ({es_url}) IK 分词器...")
    
    async with httpx.AsyncClient() as client:
        try:
            # 1. 检查版本
            r = await client.get(es_url)
            version = r.json()["version"]["number"]
            print(f"ES 版本: {version}")
            
            # 2. 检查插件
            r = await client.get(f"{es_url}/_cat/plugins?format=json")
            plugins = r.json()
            ik_plugin = next((p for p in plugins if "analysis-ik" in p["component"]), None)
            
            if ik_plugin:
                print(f"IK 插件已安装: {ik_plugin['version']}")
            else:
                print("错误: 未检测到 IK 分词器插件！")
                sys.exit(1)
            
            # 3. 测试分词
            test_body = {
                "analyzer": "ik_max_word",
                "text": "中华人民共和国万岁"
            }
            r = await client.post(f"{es_url}/_analyze", json=test_body)
            if r.status_code == 200:
                tokens = [t["token"] for p in [r.json()] for t in p["tokens"]]
                print(f"分词测试成功: {tokens}")
            else:
                print(f"分词测试失败: {r.text}")
                sys.exit(1)
                
            print("\n所有校验已通过！")
            
        except Exception as e:
            print(f"验证过程中发生异常: {e}")
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(verify_es_ik())
