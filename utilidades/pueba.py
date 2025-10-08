from confluent_kafka import Producer, Consumer

# --- Productor ---
conf = {'bootstrap.servers': '3.143.108.22:9092'}
producer = Producer(conf)

producer.produce('test-topic', key='key1', value='Hola desde Windows con confluent-kafka!')
producer.flush()
print("✅ Mensaje enviado al topic test-topic")

# --- Consumidor ---
consumer_conf = {
    'bootstrap.servers': '3.143.108.22:9092',
    'group.id': 'mi-grupo',
    'auto.offset.reset': 'earliest'
}
consumer = Consumer(consumer_conf)
consumer.subscribe(['test-topic'])

print("📩 Escuchando mensajes...")
while True:
    msg = consumer.poll(1.0)  # espera hasta 1 segundo
    if msg is None:
        continue
    if msg.error():
        print("⚠️ Error:", msg.error())
        continue
    print(f"Mensaje recibido: {msg.value().decode('utf-8')}")
