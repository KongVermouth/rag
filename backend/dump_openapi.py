import json
from app.main import app

def dump_openapi():
    with open("openapi_dump.json", "w", encoding="utf-8") as f:
        json.dump(app.openapi(), f, indent=2, ensure_ascii=False)
    print("OpenAPI spec dumped to openapi_dump.json")

if __name__ == "__main__":
    dump_openapi()
