from aiokafka import AIOKafkaConsumer
import json
import logging
import asyncio
from typing import Callable, Awaitable
from app.core.config import settings

logger = logging.getLogger(__name__)

class KafkaConsumer:
    def __init__(self, topic: str, group_id: str, callback: Callable[[dict], Awaitable[None]]):
        self.topic = topic
        self.group_id = group_id
        self.callback = callback
        self.consumer = None
        self.running = False

    async def start(self):
        self.consumer = AIOKafkaConsumer(
            self.topic,
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            group_id=self.group_id,
            auto_offset_reset='earliest',
            max_partition_fetch_bytes=10485760,  # 10MB
            fetch_max_bytes=10485760             # 10MB
        )
        try:
            await self.consumer.start()
            self.running = True
            logger.info(f"Kafka Consumer started for topic: {self.topic}")
            
            async for msg in self.consumer:
                if not self.running:
                    break
                try:
                    data = json.loads(msg.value.decode('utf-8'))
                    await self.callback(data)
                except Exception as e:
                    logger.error(f"Error processing message from {self.topic}: {e}")
        except Exception as e:
            logger.error(f"Kafka Consumer error: {e}")
        finally:
            if self.consumer:
                await self.consumer.stop()
            logger.info(f"Kafka Consumer stopped for topic: {self.topic}")

    async def stop(self):
        self.running = False
