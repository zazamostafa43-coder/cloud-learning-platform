import json
from kafka import KafkaProducer, KafkaConsumer
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KafkaHandler:
    def __init__(self, bootstrap_servers):
        self.bootstrap_servers = bootstrap_servers
        self.producer = None

    def get_producer(self):
        if not self.producer:
            import time
            retries = 5
            while retries > 0:
                try:
                    self.producer = KafkaProducer(
                        bootstrap_servers=self.bootstrap_servers,
                        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                        request_timeout_ms=5000
                    )
                    logger.info("Successfully connected to Kafka")
                    break
                except Exception as e:
                    logger.warning(f"Failed to connect to Kafka, retrying... ({retries} left). Error: {e}")
                    retries -= 1
                    time.sleep(5)
            if not self.producer:
                logger.error("Could not connect to Kafka after multiple retries")
                # Don't raise here, allow the app to start but fail on actual usage
        return self.producer

    def send_message(self, topic, message):
        try:
            producer = self.get_producer()
            if producer:
                producer.send(topic, message)
                producer.flush()
                logger.info(f"Message sent to topic {topic}")
            else:
                logger.error(f"Cannot send message to {topic}: No producer available")
        except Exception as e:
            logger.error(f"Error sending message to Kafka: {e}")

    def get_consumer(self, topic, group_id):
        return KafkaConsumer(
            topic,
            bootstrap_servers=self.bootstrap_servers,
            auto_offset_reset='earliest',
            enable_auto_commit=True,
            group_id=group_id,
            value_deserializer=lambda x: json.loads(x.decode('utf-8'))
        )
