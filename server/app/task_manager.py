"""轻量任务执行器：线程池 + 内存任务表。

生产环境任务量大时建议替换为 Celery/RQ + Redis 之类的持久化队列；
这里对单机部署足够，任务状态以 SQLite 为准。
"""
from concurrent.futures import ThreadPoolExecutor


class TaskManager:
    def __init__(self, max_workers: int = 2):
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="tts")

    def submit(self, fn) -> None:
        """fn 需自行处理所有副作用（更新数据库状态、捕获异常）。"""
        self._executor.submit(fn)
