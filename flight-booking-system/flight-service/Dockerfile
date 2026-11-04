FROM python:3.11-slim

WORKDIR /app

COPY flight-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY flight-service/app ./app
COPY proto /proto

RUN python -m grpc_tools.protoc -I/proto --python_out=app --grpc_python_out=app /proto/flight.proto \
    && sed -i 's/import flight_pb2 as flight__pb2/from . import flight_pb2 as flight__pb2/' app/flight_pb2_grpc.py

CMD ["python", "-m", "app.main"]
