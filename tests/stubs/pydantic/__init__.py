import typing
class _F:
    def __init__(self,default=...): self.default=default
def Field(default=..., **k): return _F(default)
class BaseModel:
    def __init__(self, **kw):
        ann={}
        for c in reversed(type(self).__mro__):
            ann.update(getattr(c,'__annotations__',{}))
        for name in ann:
            if name in kw: setattr(self,name,kw[name]); continue
            d=getattr(type(self),name,...)
            if isinstance(d,_F): d=d.default
            if d is ...: raise TypeError(f"missing {name}")
            setattr(self,name,d)
