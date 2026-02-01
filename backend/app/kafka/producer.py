from aiokafka import AIOKafkaProducer
import json
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class KafkaProducer:
    def __init__(self):
        self.producer = None

    async def start(self):
        if self.producer:
            return
            
        try:
            self.producer = AIOKafkaProducer(
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                max_request_size=10485760  # 10MB
            )
            await self.producer.start()
            logger.info("Kafka Producer started")
        except Exception as e:
            logger.error(f"Failed to start Kafka Producer: {e}")
            self.producer = None

    async def stop(self):
        if self.producer:
            await self.producer.stop()
            self.producer = None
            logger.info("Kafka Producer stopped")

    async def send(self, topic: str, value: dict):
        if not self.producer:
            await self.start()
        
        if not self.producer:
            logger.error("Kafka Producer is not running")
            return

        try:
            await self.producer.send_and_wait(
                topic, 
                json.dumps(value).encode('utf-8')
            )
        except Exception as e:
            logger.error(f"Failed to send message to {topic}: {e}")

# Global Producer Instance
producer = KafkaProducer()
