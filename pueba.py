from kafka import KafkaProducer, KafkaConsumer

# Productor
producer = KafkaProducer(bootstrap_servers='3.143.108.22:9092')
producer.send('test-topic', b'Hola desde mi PC!')
producer.flush()

# Consumidor
consumer = KafkaConsumer(
    'test-topic',
    bootstrap_servers='3.143.108.22:9092',
    auto_offset_reset='earliest',
    enable_auto_commit=True,
    group_id='mi-grupo'
)

for message in consumer:
    print(f"Mensaje recibido: {message.value.decode('utf-8')}")
