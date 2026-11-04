import grpc
import os
import logging

logger = logging.getLogger(__name__)
VALID_API_KEY = os.getenv("GRPC_API_KEY", "secret-flight-key-123")

class AuthInterceptor(grpc.ServerInterceptor):
    def intercept_service(self, continuation, handler_call_details):
        metadata = dict(handler_call_details.invocation_metadata)
        api_key = metadata.get("api-key")
        if api_key != VALID_API_KEY:
            def abort(request, context):
                context.abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid or missing API key")
            return grpc.unary_unary_rpc_method_handler(abort)
        return continuation(handler_call_details)
