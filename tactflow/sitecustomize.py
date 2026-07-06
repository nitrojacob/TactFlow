import google.auth

class MockCredentials:
    def __init__(self):
        self.universe_domain = "googleapis.com"
        self.token = "mock-token"
        self.valid = True
        self.expired = False

    def before_request(self, *args, **kwargs):
        # Do not inject mock objects into headers and accept any arguments
        pass

    def refresh(self, *args, **kwargs):
        pass

# Monkeypatch google.auth.default to return clean mock credentials
def mock_default(*args, **kwargs):
    return MockCredentials(), "mock-project-id"

google.auth.default = mock_default
print("[sitecustomize] Loaded robust MockCredentials with wildcard arguments to prevent gRPC/HTTP errors")
