#!/bin/bash
# Elasticsearch IK 分词器一键安装脚本

ES_VERSION=$(curl -s http://localhost:9200 | grep number | awk -F'"' '{print $4}')

if [ -z "$ES_VERSION" ]; then
    echo "无法连接到 Elasticsearch，请确保 ES 已启动。"
    exit 1
fi

echo "检测到 Elasticsearch 版本: $ES_VERSION"

IK_PLUGIN_URL="https://github.com/medcl/elasticsearch-analysis-ik/releases/download/v${ES_VERSION}/elasticsearch-analysis-ik-${ES_VERSION}.zip"

echo "正在下载 IK 分词器插件..."
curl -L -o ik-plugin.zip $IK_PLUGIN_URL

if [ $? -ne 0 ]; then
    echo "下载失败，请检查网络或版本对应关系。"
    exit 1
fi

# 假设 ES 安装在 /usr/share/elasticsearch (Docker 默认路径)
# 如果是本地安装，请修改路径
PLUGIN_DIR="/usr/share/elasticsearch/plugins/ik"

echo "正在安装插件到 $PLUGIN_DIR ..."
# 这里需要 root 权限或者在 Docker 容器内运行
# docker exec -it elasticsearch bin/elasticsearch-plugin install $IK_PLUGIN_URL

echo "安装完成，请重启 Elasticsearch 集群。"
