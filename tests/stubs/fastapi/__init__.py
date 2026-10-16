class HTTPException(Exception):
    def __init__(self, status_code, detail=None):
        self.status_code=status_code; self.detail=detail
class Request: pass
def Header(default=None, **k): return default
class FastAPI:
    def __init__(self,*a,**k): pass
    def exception_handler(self,*a,**k): return lambda f:f
    def add_middleware(self,*a,**k): pass
    def get(self,*a,**k): return lambda f:f
    def post(self,*a,**k): return lambda f:f
    def api_route(self,*a,**k): return lambda f:f

class Response:
    def __init__(self, content=None, media_type=None, headers=None):
        self.body=content; self.media_type=media_type; self.headers=headers or {}
