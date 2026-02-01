class BaseAppException(Exception):
    """基础应用异常"""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

class VectorizationFailedException(BaseAppException):
    """向量化失败异常"""
    def __init__(self, message: str, detail: str = None, trace_id: str = None):
        self.detail = detail
        self.trace_id = trace_id
        super().__init__(message)

class ElasticsearchIKException(BaseAppException):
    """Elasticsearch IK分词器异常"""
    def __init__(self, message: str = "Elasticsearch IK 分词器配置错误"):
        super().__init__(message)
