import grpc
from concurrent import futures
import logging
from app.grpc_gen import customer_service_pb2_grpc
from app.services.customer_grpc_handler import CustomerServicer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("grpc_server")


def serve():
    # 1. Create the gRPC server
    # We use a ThreadPool to handle concurrent RPC calls
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=100))

    # 2. Add our Servicer logic to the server
    customer_service_pb2_grpc.add_CustomerServiceServicer_to_server(
        CustomerServicer(), server
    )

    # 3. Define the port (Internal only usually)
    listen_addr = "[::]:50051"
    server.add_insecure_port(listen_addr)

    logger.info(f"🚀 gRPC Server starting on {listen_addr}")
    server.start()

    # 4. Keep the process alive
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("🛑 Shutting down gRPC server...")
        server.stop(0)


if __name__ == "__main__":
    serve()
