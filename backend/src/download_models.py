#!/usr/bin/env python3
import os
import sys
from pathlib import Path
from modelscope import snapshot_download


def download_model(model_id: str = "Qwen/Qwen3-Embedding-0.6B", 
                   revision: str | None = None) -> Path:
    """
    从ModelScope下载模型到项目的models目录
    
    Args:
        model_id: 模型ID，默认为Qwen3-Embedding-0.6B
        revision: 可选的模型版本/分支/标签
        
    Returns:
        下载的模型路径
    """
    project_root = Path(__file__).resolve().parent.parent
    models_dir = project_root / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    # 检查认证令牌[8](@ref)
    if token := os.getenv("MODELSCOPE_SDK_TOKEN"):
        print("使用MODELSCOPE_SDK_TOKEN进行认证")
    else:
        print("未设置MODELSCOPE_SDK_TOKEN，仅可下载公开模型")

    print(f"下载模型 '{model_id}' -> {models_dir}")
    
    # 使用字典推导式简化参数传递[5](@ref)
    download_args = {"model_id": model_id, "cache_dir": str(models_dir)}
    if revision:
        download_args["revision"] = revision
        
    model_path = Path(snapshot_download(**download_args))
    print(f"下载完成: {model_path}")
    
    return model_path


def main(argv: list[str] | None = None) -> int:
    """主函数，处理命令行参数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="下载ModelScope模型到本地目录")
    parser.add_argument("--model-id", default="Qwen/Qwen3-Embedding-0.6B",
                       help="模型ID (默认: Qwen/Qwen3-Embedding-0.6B)")
    parser.add_argument("--revision", help="模型版本/分支/标签")
    
    args = parser.parse_args(argv)
    
    try:
        download_model(args.model_id, args.revision)
        return 0
    except Exception as e:
        print(f"下载失败: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())