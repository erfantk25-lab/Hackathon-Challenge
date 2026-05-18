from pydantic import BaseModel , ConfigDict


class search(BaseModel):
    query: str = None
    limit: int = None
    offset: int = None
